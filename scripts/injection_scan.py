#!/usr/bin/env python3
"""Prompt-injection scanner for MisakaNet content surfaces.

MisakaNet text is *read by agents*: lessons come back through
``misakanet_search`` / ``misakanet_get_lesson``, intakes arrive anonymously through
the MCP endpoint or by email, and answered questions are replayed to whoever asks.
Any of those channels can carry instructions aimed at the reading agent rather than
knowledge for its human operator — the failure mode that makes a shared knowledge
base actively dangerous.

This scanner flags *injection-shaped* content. It is deliberately advisory:
- it never rewrites or blocks by itself (callers decide: label, annotate, review),
- it distinguishes content found inside fenced code blocks (where a lesson may
  legitimately *quote* an attack) from prose,
- it prefers a small set of high-precision patterns over broad "sounds bossy"
  heuristics, because security lessons discuss these phrases on purpose.

Usage:
    python3 scripts/injection_scan.py <path> [<path> ...] [--json]
    python3 scripts/injection_scan.py --text "..." [--json]
    python3 scripts/injection_scan.py --dir lessons/ --json

Exit codes:
    0 — no high-severity finding
    1 — at least one high-severity finding (for CI use)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── Patterns ────────────────────────────────────────────────────────────────
# severity: "high" escalates the exit code; "medium" is reported only.
_PATTERNS: tuple[tuple[str, str, str], ...] = (
    # instruction override — the canonical injection opener
    ("instruction_override", "high",
     r"(?i)\b(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+)?"
     r"(previous|prior|above|earlier|preceding)\s+"
     r"(instruction|instructions|prompt|prompts|rule|rules|context)"),
    # chat-template / role markers: model-turn spoofing
    ("role_marker", "high",
     r"(?i)<\|(im_start|im_end|system|assistant|user|endoftext)\|>"
     r"|\[\s*(system|assistant)\s*\]"
     r"|^\s*#{0,3}\s*(system|assistant)\s*:\s*$"),
    # hidden instructions in HTML comments (markdown renders them invisibly)
    ("hidden_html_comment", "high",
     r"<!--(?:(?!-->).){0,400}?"
     r"(ignore|instruction|prompt|execute|run |curl|token|password|secret)"
     r"(?:(?!-->).){0,400}?-->"),
    # zero-width / bidi control characters used to smuggle text past review
    ("invisible_characters", "high",
     r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"),
    # "you are now …" role hijack
    ("role_hijack", "medium",
     r"(?i)\b(you\s+are\s+now|from\s+now\s+on\s+you\s+(are|will)|"
     r"act\s+as\s+(a|an|the)\s+(system|admin|root|administrator))"),
    # direct tool/command directive aimed at the reader
    ("tool_directive", "medium",
     r"(?i)\b(run|execute|eval)\s+(this|the\s+following)\s+"
     r"(command|script|code|snippet|payload)"),
    # credential exfiltration shape: fetch/post + secret-ish target
    ("credential_exfil", "medium",
     r"(?i)\b(curl|wget|fetch|http\.post|requests\.post|Invoke-WebRequest)\b"
     r"[^\n]{0,100}(?<![A-Za-z0-9_])"
     r"(env|environment|token|secret|credential|api[_-]?key|\.ssh|\.aws|\.npmrc|id_rsa)\b"),
    # long base64 blob — payload smuggling
    ("base64_blob", "medium", r"\b[A-Za-z0-9+/]{160,}={0,2}\b"),
)

_COMPILED = tuple(
    (name, severity, re.compile(pattern, re.MULTILINE))
    for name, severity, pattern in _PATTERNS
)

_CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code_blocks(text: str) -> str:
    """Return text with quoted code removed.

    Removes fenced blocks *and* inline code spans: both are the conventions for
    quoting a payload, and prose that *discusses* injection (like this scanner's own
    documentation, or a lesson explaining the cleanup of a polluted file) must not be
    flagged as the attack itself. This mirrors the inline-code stripping already used
    by .github/workflows/lesson-security.yml.
    """
    out, in_block = [], False
    for line in text.splitlines():
        if _CODE_FENCE_RE.match(line):
            in_block = not in_block
            out.append("")
            continue
        out.append("" if in_block else line)
    return _INLINE_CODE_RE.sub("", "\n".join(out))


def scan_text(text: str, *, source: str = "<text>", include_code_blocks: bool = False) -> list[dict]:
    """Scan one document; returns findings sorted by severity then position."""
    haystack = text if include_code_blocks else strip_code_blocks(text)
    findings = []
    for name, severity, rx in _COMPILED:
        for m in rx.finditer(haystack):
            findings.append({
                "rule": name,
                "severity": severity,
                "source": source,
                "line": haystack.count("\n", 0, m.start()) + 1,
                "excerpt": re.sub(r"\s+", " ", m.group(0))[:120],
            })
    findings.sort(key=lambda f: (f["severity"] != "high", f["line"]))
    return findings


def scan_file(path: Path, *, include_code_blocks: bool = False) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:  # unreadable file should not fail a scan
        return [{"rule": "read_error", "severity": "medium", "source": str(path),
                 "line": 0, "excerpt": str(e)[:120]}]
    return scan_text(text, source=str(path), include_code_blocks=include_code_blocks)


def has_high(findings: list[dict]) -> bool:
    return any(f["severity"] == "high" for f in findings)


def summarize(findings: list[dict]) -> dict:
    from collections import Counter
    return {
        "total": len(findings),
        "high": sum(1 for f in findings if f["severity"] == "high"),
        "by_rule": dict(Counter(f["rule"] for f in findings)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files to scan")
    ap.add_argument("--text", help="scan a literal string instead of files")
    ap.add_argument("--dir", help="scan every .md/.json/.txt file under a directory")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--include-code-blocks", action="store_true",
                    help="also flag patterns inside fenced code blocks (noisy; off by default)")
    args = ap.parse_args()

    targets: list[Path] = [Path(p) for p in args.paths]
    if args.dir:
        root = Path(args.dir)
        targets += [p for p in sorted(root.rglob("*"))
                    if p.is_file() and p.suffix.lower() in (".md", ".json", ".txt", ".html")]

    findings: list[dict] = []
    if args.text is not None:
        findings += scan_text(args.text, source="<text>",
                              include_code_blocks=args.include_code_blocks)
    for t in targets:
        findings += scan_file(t, include_code_blocks=args.include_code_blocks)

    if args.json:
        print(json.dumps({"summary": summarize(findings), "findings": findings}, indent=2))
    else:
        s = summarize(findings)
        print(f"injection scan: {s['total']} finding(s) — high={s['high']} {s['by_rule']}")
        for f in findings:
            print(f"  [{f['severity']:>6}] {f['rule']:<22} {f['source']}:{f['line']}  {f['excerpt'][:80]}")
    return 1 if has_high(findings) else 0


if __name__ == "__main__":
    sys.exit(main())
