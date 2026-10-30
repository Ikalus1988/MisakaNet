#!/usr/bin/env python3
"""The intake funnel, measured from issue state and lesson provenance — one panel's worth.

Why this exists
---------------
The daily heartbeat answers "who is calling, what they asked, whether it helped". It never answered
**"is anything moving"**: how many issues arrived, how many became lessons, how long that took, and
where the backlog is oldest. Those numbers cannot be read off labels — a converted intake is known
only from the lesson's `provenance`, and "open for 31 days" is a fact about a timestamp — so they were
computed by hand for `docs/maintainer/pipeline-funnel-2026-10-30.md` and would have gone stale the next
day. This module is the regenerable form of that pass, and the heartbeat is the surface that carries it
(a comment already delivered daily, not a new page somebody has to remember to open).

What it reads
-------------
* **issues** — the REST issue list (`state=all`), paginated. Pull requests are not issues.
* **lessons** — `lessons/**/*.md` on disk: `created:` and the citation fields `intake_receipt` already
  knows how to read. Provenance, not keywords: a lesson that merely *mentions* #1234 is not a
  conversion of it, and `intake_receipt._cites` is the one implementation of that shape in this repo.

What it refuses to do
---------------------
* **No claim about answers.** "Converted" means a lesson cites the issue; "answered" means the label is
  there. Neither means the asker got something useful, and the panel says so where it prints them.
* **A failed read is not a zero.** `collect` returns the reason, and the panel prints it.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LESSONS_DIR = REPO / "lessons"

KINDS = ("question", "intake", "lesson-submission", "own")
KIND_LABEL = {
    "question": "`[Question]`",
    "intake": "`[Intake]`",
    "lesson-submission": "`[Lesson]`",
    "own": "our own issues",
}

# A window of 7 days is what "this week" means in the handoff and the digest; 30 days is long enough
# that the latency percentile is not computed from three rows.
WINDOW_DAYS = 7
LATENCY_WINDOW_DAYS = 30


def classify(issue: dict) -> str:
    title = str(issue.get("title") or "")
    if title.startswith("[Question]"):
        return "question"
    if title.startswith("[Intake]"):
        return "intake"
    if title.startswith("[Lesson]"):
        return "lesson-submission"
    return "own"


def labels_of(issue: dict) -> set[str]:
    return {str(l.get("name")) for l in (issue.get("labels") or []) if isinstance(l, dict)}


def _day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


# ── lessons: provenance, by the repo's own citation shapes ──────────────────

_CITE = re.compile(r"(?:#\s*|intake[-_ ](?:issue[-_ ])?)(\d{2,6})(?!\d)|issues/(\d{2,6})(?!\d)", re.I)


def lesson_records(lessons_dir: Path = LESSONS_DIR) -> list[dict]:
    """`{created, issues}` for every lesson, read once.

    The citation text comes from `intake_receipt._citation_text`, so this module does not grow a
    second idea of what "cites intake #1234" means (that module already refuses a bare number, and
    its refusals are the reason the receipt rule has no false positives).
    """
    try:
        from scripts.intake_receipt import _citation_text, _frontmatter  # noqa: PLC0415 — optional path
    except Exception:  # pragma: no cover — a checkout without scripts/ has no provenance anyway
        return []
    out: list[dict] = []
    for path in sorted(lessons_dir.rglob("*.md")):
        if path.name.upper() == "README.MD" or "TEMPLATE" in path.name.upper():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _frontmatter(text)
        if not fm:
            continue
        created = _day(str(fm.get("created") or "")[:10])
        numbers = {int(a or b) for a, b in _CITE.findall(_citation_text(fm))}
        out.append({"path": path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path),
                    "created": created, "issues": numbers})
    return out


def converted_numbers(lessons: list[dict]) -> set[int]:
    return {n for lesson in lessons for n in lesson["issues"]}


# ── the summary ─────────────────────────────────────────────────────────────

def summarize(issues: list[dict], lessons: list[dict], today: date | None = None) -> dict:
    """Everything the panel prints, as plain data (so a test can assert on it without text)."""
    today = today or datetime.now().date()
    start = today - timedelta(days=WINDOW_DAYS - 1)
    issues = [i for i in issues if "pull_request" not in i]
    converted = converted_numbers(lessons)
    lesson_created = {n: d for lesson in lessons for n in lesson["issues"]
                      for d in [lesson["created"]] if d}

    rows: dict[str, dict] = {}
    for kind in KINDS:
        rows[kind] = {"created": 0, "converted": 0, "closed": 0, "open": 0,
                      "oldest_open_days": None, "never_commented": 0,
                      "auto_rejected": 0, "auto_rejected_open": 0, "auto_rejected_salvaged": 0,
                      "answered": 0}

    for issue in issues:
        kind = classify(issue)
        row = rows[kind]
        created = _day(issue.get("created_at"))
        labels = labels_of(issue)
        is_open = issue.get("state") == "open"
        if created and created >= start:
            row["created"] += 1
            if issue["number"] in converted:
                row["converted"] += 1
            if not is_open:
                row["closed"] += 1
        if not is_open:
            continue
        row["open"] += 1
        age = (today - created).days if created else None
        if age is not None and (row["oldest_open_days"] is None or age > row["oldest_open_days"]):
            row["oldest_open_days"] = age
        if not issue.get("comments"):
            row["never_commented"] += 1
        if kind == "question" and "answered" in labels:
            row["answered"] += 1
        if "auto-rejected" in labels:
            row["auto_rejected_open"] += 1

    # `auto-rejected` is a lifecycle label, so the salvaged half has to be counted on all issues,
    # closed ones included — an issue that was rejected and later became a lesson is closed by then.
    for issue in issues:
        if "auto-rejected" not in labels_of(issue):
            continue
        rows[classify(issue)]["auto_rejected"] += 1
        if issue["number"] in converted:
            rows[classify(issue)]["auto_rejected_salvaged"] += 1

    # question answers are an all-time count, not a window one: the label carries no timestamp, and a
    # "answered this week" built from it would be an invention.
    questions = [i for i in issues if classify(i) == "question"]
    answered_total = sum(1 for i in questions if "answered" in labels_of(i))

    latency: list[int] = []
    recent = today - timedelta(days=LATENCY_WINDOW_DAYS)
    for issue in issues:
        created = _day(issue.get("created_at"))
        done = lesson_created.get(issue["number"])
        if created and done and done >= recent and done >= created:
            latency.append((done - created).days)
    latency.sort()

    return {
        "today": today.isoformat(),
        "window_days": WINDOW_DAYS,
        "rows": rows,
        "latency": {
            "n": len(latency),
            "median": latency[len(latency) // 2] if latency else None,
            "p90": latency[int(len(latency) * 0.9)] if latency else None,
        },
        "answered_total": answered_total,
        "questions_total": len(questions),
    }


def _pct(part: int, whole: int) -> str:
    return f"{part * 100 // whole}%" if whole else "—"


def render_lines(summary: dict) -> list[str]:
    """The panel, as markdown lines. No numbers are invented: an unreadable row says so."""
    rows = summary["rows"]
    window = summary["window_days"]
    lines = [
        f"## 4 · The pipeline (issues → lessons, last {window} days)",
        "",
        "| | created | converted | open now (oldest) |",
        "|---|---:|---:|---|",
    ]
    for kind in KINDS:
        row = rows[kind]
        open_cell = str(row["open"])
        if row["oldest_open_days"] is not None:
            open_cell += f" ({row['oldest_open_days']}d)"
        if kind == "intake" and row["auto_rejected_open"]:
            open_cell += f", {row['auto_rejected_open']} auto-rejected"
        if kind == "own" and row["never_commented"]:
            open_cell += f", {row['never_commented']} never commented"
        lines.append(
            f"| {KIND_LABEL[kind]} | {row['created']} | "
            f"{row['converted']} ({_pct(row['converted'], row['created'])}) | {open_cell} |"
        )

    latency = summary["latency"]
    if latency["n"]:
        lines += ["", f"- **issue → lesson**: median **{latency['median']} days**, p90 "
                      f"**{latency['p90']} days** ({latency['n']} linked lessons, "
                      f"last {LATENCY_WINDOW_DAYS} days)"]
    else:
        lines += ["", "- **issue → lesson**: no lesson was created in the last "
                      f"{LATENCY_WINDOW_DAYS} days that cites an issue"]

    answered = summary["answered_total"]
    total = summary["questions_total"]
    lines.append(f"- **questions answered**: **{answered}/{total}** ({_pct(answered, total)}) — the "
                 f"`answered` label is all this counts; it does not say the answer helped")
    rejected = sum(rows[k]["auto_rejected"] for k in KINDS)
    salvaged = sum(rows[k]["auto_rejected_salvaged"] for k in KINDS)
    lines.append(f"- **auto-rejected salvage**: **{salvaged}/{rejected}** became lessons "
                 f"({_pct(salvaged, rejected)})")
    lines += ["", "_This panel reads issue state, not answers: `converted` means a lesson cites the "
                  "issue (provenance, not a keyword), and an open issue may already be answered "
                  "in-thread. It is a shape of the backlog, not a verdict on it._"]
    return lines


# ── fetching (the only part with a network) ─────────────────────────────────

def fetch_issues(token: str, slug: str = "Ikalus1988/MisakaNet", page_size: int = 100,
                 max_pages: int = 40) -> list[dict]:
    """Every issue, open and closed, paginated. PRs are filtered out by the caller's `summarize`."""
    out: list[dict] = []
    for page in range(1, max_pages + 1):
        url = (f"https://api.github.com/repos/{slug}/issues"
               f"?state=all&per_page={page_size}&page={page}&sort=created&direction=desc")
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "misakanet-heartbeat",
        })
        with urllib.request.urlopen(request, timeout=60) as response:
            batch = json.loads(response.read().decode() or "[]")
        if not isinstance(batch, list):
            raise ValueError("the issues endpoint did not return a list")
        out.extend(i for i in batch if "pull_request" not in i)
        if len(batch) < page_size:
            break
    return out


def collect(*, token: str | None, lessons_dir: Path = LESSONS_DIR,
            today: date | None = None) -> tuple[dict | None, str]:
    """Read both sources. Returns (summary, "") or (None, reason) — never an empty summary."""
    if not token:
        return None, "no GitHub token in the environment (GITHUB_TOKEN / GH_TOKEN)"
    try:
        issues = fetch_issues(token)
    except (urllib.error.URLError, OSError, ValueError) as error:
        return None, f"{type(error).__name__}: {error}"
    return summarize(issues, lesson_records(lessons_dir), today), ""
