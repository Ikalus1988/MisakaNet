#!/usr/bin/env python3
"""Intake → lesson conversion receipts (issue #1528), and the case harness that judges them.

Why this exists
---------------
Closing an intake with a receipt has been a **manual** step, and it shows: on 2026-09-21 four
intakes (#1472/#1473/#1635/#1574) had had their lessons merged days earlier and were still open
with nothing said, so from the reporter's side the report looked ignored. The maintainer's own SOP
(`docs/maintainer/intake-triage.md` §3) calls the receipt an iron rule — a rule that depends on
someone remembering is not a mechanism.

Two of #1528's three acceptance criteria are answered here:

* AC1 "track source + intake issue id through lesson-ification" — the link already exists, in the
  lesson's own frontmatter (`source: "intake-1130"`, `provenance.issue: "#1130"`). This resolves it
  tolerantly, because contributors write it in several shapes.
* AC2/AC3 "promotion → emit a receipt pointing at the lesson, including evidence_level" — that is
  `compose()` + `render()`.

The channel for a reporter *with* a GitHub thread is a comment. An anonymous MCP reporter has no
thread to be notified in, which is #1605's story: the fix shipped in 30 minutes and its reporter
could never learn that. For them the receipt travels on the channel they already use — re-submitting
the same problem text, which already returns the maintainer's answer for questions — so `compose()`
also produces the `mcp` payload `{resolved, issue, lesson, evidence_level}`.

This file is deliberately offline and read-only: it composes and prints. Posting is a separate,
explicit act (`--post` is not implemented yet; wiring it is the remaining half of #1528), and the
cases under `tests/intake_receipt_cases/` are what make that wiring judgeable — each one is a real
conversion from this repository's history, with the receipt it must produce.

    python3 scripts/intake_receipt.py --intake 1130            # the receipt, as text
    python3 scripts/intake_receipt.py --intake 1618 --json     # the structured payload
    python3 scripts/intake_receipt.py --list-cases             # what the harness covers
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
CASES_DIR = REPO / "tests" / "intake_receipt_cases"
BLOB_BASE = "https://github.com/Ikalus1988/MisakaNet/blob/main"

# A lesson cites its intake in `source:` (`intake-1130`, `intake #1553 — …`, `mcp-intake-1193`) and,
# since #1768, in `provenance.issue`. Both are authoritative; the shapes are not standardised, so
# matching on the bare number inside those fields is the reliable reading.
_CITE_FIELDS = ("source", "provenance.issue", "provenance.related", "provenance.source")


def _frontmatter(text: str) -> dict:
    """Parse the YAML block well enough for citations — never raises on a malformed lesson."""
    if not text.startswith("---"):
        return {}
    try:
        import yaml  # PyYAML is a CI dependency; the CLI degrades if it is absent

        block = text.split("---", 2)[1]
        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten(v) for v in value)
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    return str(value)


def lessons_citing(issue: int, lessons_dir: Path = LESSONS_DIR) -> list[dict]:
    """Every lesson that cites this intake, in path order.

    Reads the lesson files rather than `data/lessons.json`: that file is a generated snapshot that
    lags a merge by up to a day, and a receipt must not miss a lesson that was merged an hour ago.
    """
    pattern = re.compile(rf"#?\s*0*{issue}\b")
    found: list[dict] = []
    for path in sorted(lessons_dir.rglob("*.md")):
        if path.name.upper() == "README.MD" or "TEMPLATE" in path.name.upper():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        citations = " ".join(_flatten(fm.get(k)) for k in _CITE_FIELDS)
        # Repo-relative for real lessons; a caller may point this at another tree (the tests do),
        # so fall back to that tree instead of raising from deep inside a resolver.
        try:
            rel = path.relative_to(REPO).as_posix()
        except ValueError:
            rel = path.relative_to(lessons_dir).as_posix()
        # `source: "intake-1130"` has no `#`; `provenance.issue: "#1130"` does. Accept both, but only
        # inside a citation field — a bare number anywhere in the body would match half the corpus.
        cited = bool(pattern.search(citations)) or bool(re.search(rf"intake[- ]0*{issue}\b", citations, re.I))
        if not cited:
            continue
        found.append({
            "id": str(fm.get("id") or path.stem),
            "path": rel,
            "title": str(fm.get("title") or "").strip(),
            "evidence_level": str(fm.get("evidence_level") or "").strip(),
            "status": str(fm.get("status") or "").strip(),
            "url": f"{BLOB_BASE}/{rel}",
            "search": f'python3 search_knowledge.py "{path.stem}" --lessons',
        })
    return found


def compose(issue: int, source: str = "unknown", lessons: list[dict] | None = None) -> dict:
    """The receipt for one conversion. Pure: no I/O beyond the corpus read it is handed."""
    lessons = lessons_citing(issue) if lessons is None else lessons
    if not lessons:
        return {
            "intake": issue,
            "source": source,
            "emitted": False,
            "reason": "no lesson cites this intake — there is nothing to receipt yet",
            "lessons": [],
            "channels": [],
        }
    levels = [l["evidence_level"] for l in lessons if l["evidence_level"]]
    return {
        "intake": issue,
        "source": source,
        "emitted": True,
        "lessons": lessons,
        # AC3: the evidence level is part of the payload, not only of the prose — the source is
        # supposed to be able to see the *quality outcome*, which means reading it mechanically.
        "evidence_level": levels[0] if levels else None,
        "channels": ["github", "mcp"],
        # What the anonymous MCP channel returns when the same problem text arrives again (#1605).
        "mcp": {
            "resolved": True,
            "issue": f"#{issue}",
            "lesson": lessons[0]["id"],
            "lesson_path": lessons[0]["path"],
            "evidence_level": levels[0] if levels else None,
        },
    }


def render(receipt: dict) -> str:
    """The comment/answer text. It must be usable by the reporter without cloning anything."""
    if not receipt["emitted"]:
        return f"（不发送回执）intake #{receipt['intake']}：{receipt['reason']}"
    lines = [
        f"**回执：你的报料已经变成课程**（intake #{receipt['intake']}，来源 `{receipt['source']}`）",
        "",
        "这条报告已经转成课程并合入 main：",
        "",
    ]
    for lesson in receipt["lessons"]:
        level = lesson["evidence_level"] or "未标注"
        lines.append(f"- `{lesson['path']}` — {lesson['title']}（{lesson['id']}，evidence_level {level}）")
    lines += [
        "",
        "你可以自己确认一下，不需要 clone：",
        "",
        "```bash",
        receipt["lessons"][0]["search"],
        "```",
    ]
    if len(receipt["lessons"]) == 1 and receipt["intake"]:
        lines += [
            "",
            f"回执对应的是这一条 intake（#{receipt['intake']}）；课程正文里也写着这条来源，"
            "所以「报告 → 课程」这条链是可追溯的。",
        ]
    return "\n".join(lines)


def load_cases(cases_dir: Path = CASES_DIR) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(cases_dir.glob("*.json"))]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="intake → lesson conversion receipts (#1528)")
    parser.add_argument("--intake", type=int, help="intake issue number")
    parser.add_argument("--source", default="unknown", help="the reporter's source label, if known")
    parser.add_argument("--json", action="store_true", help="structured payload instead of text")
    parser.add_argument("--list-cases", action="store_true", help="the cases the harness covers")
    args = parser.parse_args(argv)

    if args.list_cases:
        for case in load_cases():
            exp = case.get("expected", {})
            mark = "receipt" if exp.get("emitted") else "no receipt"
            print(f"  {case['id']:38s} {mark:10s} {case.get('why', '')[:70]}")
        return 0

    if args.intake is None:
        parser.error("--intake is required (or use --list-cases)")

    receipt = compose(args.intake, args.source)
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(render(receipt))
    # Exit 2 (not 1) for "nothing to receipt": that is a legitimate answer, not a failure — and a
    # caller that treats it as success would post an empty receipt.
    return 0 if receipt["emitted"] else 2


if __name__ == "__main__":
    sys.exit(main())
