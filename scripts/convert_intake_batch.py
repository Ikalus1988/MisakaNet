#!/usr/bin/env python3
"""Try to convert every open intake into a lesson, and say why the ones that fail do.

This is the batch half of `docs/maintainer/intake-flywheel.md`. It exists so the flywheel can be
turned on **after** the intake form starts emitting a shape `intake_lesson_to_file.convert()` can
read — not before, because a scheduled job that opens an empty pull request every night is noise in
the one place (the Actions list) where noise hides real failures.

It is deliberately report-first:

* ``--report`` (default) prints what it *would* convert and the skip histogram. Run this first; if
  ``converted`` is 0, the form is the problem and no workflow will fix it.
* ``--write`` writes the lesson files (and nothing else — no branch, no PR, no issue). The caller
  decides whether that is worth a pull request.

The skip histogram is the point. A single number ("3 of 172") says nothing; "162 missing Problem/
Root Cause/Fix, 7 unknown domain, 2 single tag" says which lever to pull.
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import intake_lesson_to_file as conv  # noqa: E402
import lesson_gate  # noqa: E402  — the same gate CI runs, so a candidate it would reject is not written

#: Domain guesses by topic keyword. Kept in one place and deliberately crude: a wrong domain is
#: correctable in the pull request, while a converter that refuses everything converts nothing.
DOMAIN_RULES = (
    ("fanuc", ("fanuc", "karel", "maketp", "反编译", "反汇编", "pc 字节码", "报警")),
    # There is no `macos` domain in `data/domains.json` — a guess that names one is a skip, not a
    # conversion. macOS-specific lessons live under `development`/`devops`.
    ("development", ("macos", "homebrew", "brew ", "p7zip", "bsd grep", "launchd", "appkit")),
    ("windows", ("windows", "powershell", "win32", "wsl", "cmd.exe", ".cmd", "注册表", "盘符")),
    ("dsh", ("dsh", "cordis", "bundle patch", "plugin_manager", "dsh.profile", "superagent")),
    ("feishu", ("feishu", "飞书", "lark-cli", "bitable", "多维表格")),
    ("mcp", ("mcp", "json-rpc", "streamable", "tool call")),
    ("cloudflare-worker", ("wrangler", "cloudflare worker", "workers kv", "isolate")),
    ("docker", ("docker", "dockerfile")),
    ("python", ("python", "pip ", "pytest", "traceback")),
    ("mobile", ("ios", "android", "xcode", "ipa ")),
    ("rag", ("rag ", "embedding", "chroma", "向量")),
    ("devops", ("git ", " ci ", "workflow", "pnpm", "npm ", "gitleaks", "curl")),
    ("agent", ("agent", "prompt", "llm")),
)


def infer_domain(text: str) -> str:
    lowered = text.lower()
    for domain, keys in DOMAIN_RULES:
        if any(key in lowered for key in keys):
            return domain
    return ""


def open_intakes(limit: int = 300) -> list[dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", "Ikalus1988/MisakaNet", "--state", "open",
         "--label", "mcp-intake", "--limit", str(limit),
         "--json", "number,title,body"],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"gh issue list failed: {out.stderr[:300]}")
    return [row for row in json.loads(out.stdout or "[]") if str(row.get("title", "")).startswith("[Intake]")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="write the lesson files")
    ap.add_argument("--limit", type=int, default=300, help="how many open intakes to scan")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    canonical = set(json.loads((REPO / "data" / "domains.json").read_text(encoding="utf-8"))["canonical"])
    issues = open_intakes(args.limit)
    overrides: dict[str, dict] = {}
    writable: list[dict] = []
    skips: collections.Counter = collections.Counter()

    for issue in issues:
        domain = infer_domain(f"{issue['body']} {issue['title']}")
        record, notes = conv.convert(issue, canonical, {"domain": domain} if domain else None)
        if record is None:
            skips[notes[0].split("(")[0][:60]] += 1
            continue
        # Gate **before** writing. The converter's own floors are looser than the gate's (120 vs 400
        # characters of body), so a batch that skipped this step opened a pull request carrying a
        # lesson CI would refuse — measured 2026-11-02, the same ASAR report was dropped by hand in
        # batch 5 and re-added by the first automated batch. `convert()` cannot know the gate's rules;
        # this module can, so it asks.
        gate_problems = []
        if not lesson_gate.validate_content_len(record["content"], lesson_gate.MIN_NEW_LESSON_CHARS):
            gate_problems.append(
                f"body too short for the gate (< {lesson_gate.MIN_NEW_LESSON_CHARS} chars)")
        gate_problems += [f"missing section: {name}" for name in lesson_gate.validate_sections(record["content"])]
        gate_problems += [f"empty section: {name}" for name in lesson_gate.validate_section_content(record["content"])]
        if gate_problems:
            skips["would fail the lesson gate"] += 1
            continue
        overrides[str(issue["number"])] = {"domain": record["domain"]}
        writable.append(issue)

    written = 0
    if args.write and writable:
        queue = Path("/tmp/intake-batch-issues.json")
        queue.write_text(json.dumps(writable, ensure_ascii=False), encoding="utf-8")
        ov = Path("/tmp/intake-batch-overrides.json")
        ov.write_text(json.dumps(overrides, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "intake_lesson_to_file.py"),
             "--issues-json", str(queue), "--overrides", str(ov), "--write"],
            cwd=REPO, capture_output=True, text=True)
        print(result.stdout[-2000:], file=sys.stderr)
        written = result.stdout.count("   ")

    report = {
        "scanned": len(issues),
        "converted": len(writable),
        "written": written,
        "skipped": sum(skips.values()),
        "by_reason": dict(skips.most_common()),
        "numbers": [row["number"] for row in writable],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"scanned {report['scanned']} open intake(s) — convertible {report['converted']}, "
              f"skipped {report['skipped']}")
        for reason, count in skips.most_common():
            print(f"  {count:4d}  {reason}")
        if report["converted"] == 0:
            print("\n0 convertible is the form's answer, not the converter's: see "
                  "docs/maintainer/intake-flywheel.md §4 L1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
