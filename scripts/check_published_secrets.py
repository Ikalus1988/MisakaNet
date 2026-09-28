#!/usr/bin/env python3
"""Scan published prose for credentials — the surface no scanner covered (#1982).

Why this exists
---------------
On 2026-09-25 a docs-only PR (#1982) was one step from merging two **live-looking node tokens**: its
two smoke reports quoted `"Authorization": "Bearer mcp_…"` verbatim, 32 random characters each. Nothing
in CI objected, and the reasons were structural rather than accidental:

* `scripts/check_worker_secrets.py` scans `workers/**` only — the auditor's `Secret Scan` step runs that
  script and nothing else;
* that step was also gated on `steps.scope.outputs.scope == 'full'`, so a **docs-only PR never ran it**;
* the audit's test suite (which would at least have run *something*) was aborting during collection on
  the Python version the job pinned (fixed the same day in #2183);
* HOL Guard's continuous scan covers `lessons/`, `scripts/` and `workers/` — not `docs/`.

So "a token pasted into a published field report" had no reader. This is that reader.

Telling a token from a placeholder
----------------------------------
`mcp_` appears all over this repository as something other than a secret: tool names
(`mcp__misakanet__search`) and placeholder examples. Three things keep those out, and it is worth
saying which one is doing the work, because the first draft of this scanner claimed all three were
necessary and measurement disagreed:

1. **A leading underscore is excluded** — the `mcp__misakanet__…` tool-name family, by construction.
   (Measured: those bodies also fall under rule 3, because a tool name repeats a small alphabet — the
   redundancy is deliberate, and `tests/test_published_secrets_scan.py` pins rule 1 on its own with a
   high-entropy `mcp__…` fixture, which is the only shape where it does anything by itself.)
2. **The body must be exactly 32 characters** — the length `misakanet_register` issues
   (`workers/register-proxy-sw.js:2510-2515`).
3. **The body must look random.** Threshold measured, not guessed: the two strings that leaked in #1982
   have **25 and 26** distinct characters, and every other `mcp_`-ish string in the tree is a tool name
   or an example that does not even reach the shape test. Measured on 2026-09-25: with rule 3 switched
   off, the repository's own prose produces **0** findings — so rule 3 is not what keeps this gate
   green today. It is there for the placeholder somebody will write tomorrow (`mcp_` + 32 identical
   characters), which rule 1 and 2 would happily flag. `tests/test_published_secrets_scan.py` pins both
   directions: the leaked shape is caught, and a 32-character placeholder is not.

So this scanner is quiet on the current corpus because the corpus is clean, not because the test is
weak — which is exactly the distinction the rest of this repository keeps getting wrong.

Output is metadata only — path, line, kind — never the matched string, so a finding does not copy the
credential into a public build log.

Usage:
    python3 scripts/check_published_secrets.py            # exit 1 on any finding
    python3 scripts/check_published_secrets.py --verbose  # also print what was scanned
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Prose surfaces that get published. `.md`/`.txt` under docs/ and lessons/ plus the root documentation.
# Deliberately NOT covered, and known to be uncovered: `docs/**/*.html` and `docs/**/*.json` (generated
# pages and data snapshots) and `data/**`. A credential there would still be a leak; it is a different
# reader's job, and claiming coverage this scanner does not have would be worse than the gap.
SCAN_DIRS = ("docs", "lessons")
SCAN_SUFFIXES = {".md", ".txt"}
ROOT_FILES = (
    "README.md", "README.zh-CN.md", "README.ja.md", "ARCHITECTURE.md", "AGENTS.md", "CLAUDE.md",
    "CONTRIBUTING.md", "JOIN.md", "ROADMAP.md", "CONCEPTS.md", "API.md", "SKILL.md",
)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pnpm-store"}

MIN_DISTINCT = 20


@dataclass(frozen=True)
class Rule:
    kind: str
    pattern: re.Pattern[str]
    distinct_after: int      # how many of the leading characters to measure for randomness
    min_distinct: int


RULES = (
    # First two characters after the prefix are `_`-heavy in tool names (`mcp__misakanet__search`), so a
    # leading underscore is excluded before the entropy test rather than after it.
    Rule("misakanet node token", re.compile(r"\bmcp_([A-Za-z0-9_-]{32})\b"), 32, MIN_DISTINCT),
    Rule("GitHub PAT (classic)", re.compile(r"\bghp_([A-Za-z0-9]{36})\b"), 36, MIN_DISTINCT),
    Rule("GitHub PAT (fine-grained)", re.compile(r"\bgithub_pat_([A-Za-z0-9_]{82})\b"), 82, 35),
    Rule("OpenAI-style key", re.compile(r"\bsk-([A-Za-z0-9]{48})\b"), 48, MIN_DISTINCT),
)


def looks_like_a_credential(kind: str, body: str, rule: Rule) -> bool:
    """Shape alone is not enough — see the module docstring for the measurement."""
    if body.startswith("_"):        # `mcp__misakanet__search` — a tool name, not a token
        return False
    return len(set(body[: rule.distinct_after])) >= rule.min_distinct


def candidate_files() -> list[Path]:
    files: list[Path] = []
    for name in ROOT_FILES:
        path = REPO / name
        if path.is_file():
            files.append(path)
    for directory in SCAN_DIRS:
        root = REPO / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if SKIP_DIRS & set(path.parts):
                continue
            files.append(path)
    return files


def scan_file(path: Path) -> list[tuple[int, str]]:
    """(line number, kind) for each finding. The matched text is deliberately not returned."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                if looks_like_a_credential(rule.kind, match.group(1), rule):
                    findings.append((number, rule.kind))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="published-prose credential scan (#1982)")
    parser.add_argument("--verbose", action="store_true", help="print every file scanned")
    args = parser.parse_args(argv)

    files = candidate_files()
    if not files:
        # A scanner that finds no files is not a scanner that found nothing.
        print("  ❌ no published prose files found — check SCAN_DIRS/ROOT_FILES", file=sys.stderr)
        return 2

    total = 0
    for path in files:
        findings = scan_file(path)
        try:
            shown = path.relative_to(REPO)
        except ValueError:          # a caller pointed us outside the checkout (tests do)
            shown = path
        if args.verbose and not findings:
            print(f"  ✅ {shown}")
        for number, kind in findings:
            # Metadata only: never echo the credential into a log that may itself be public.
            print(f"  ❌ {shown}:{number} — {kind}")
            total += 1

    if total:
        print(f"\n{total} credential-shaped string(s) in published prose. A token belongs only in the "
              "`Authorization` header (AGENTS.md §3.3), and a field report is published: redact it, and "
              "treat the value as compromised — a fork PR's diff is public immediately, so removing the "
              "line does not un-expose it.")
        return 1
    print(f"  ✅ no credential-shaped strings in {len(files)} published prose files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
