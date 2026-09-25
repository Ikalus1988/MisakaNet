#!/usr/bin/env python3
"""Find intakes whose work is already on `main` but whose issue is still open (#2040).

On 2026-09-21 seven intakes were in exactly that state — lessons merged days earlier, issue open
with nothing said (#1472/#1473/#1635/#1574, and #1618/#1619). It was found **by hand**, which is the
point: the reciprocity rule in `docs/maintainer/intake-triage.md` §3 is an iron rule that depends on
somebody remembering, and a rule that depends on remembering is not a mechanism.

This is the mechanism. It reuses `intake_receipt.lessons_citing` rather than re-deriving the citation
shapes: the resolver already reads the shapes contributors actually write (`intake-1130`,
`"intake #1643 — …"`, `"intake #1472 + #1473"`, `provenance.issue`) and already refuses to treat a
number merely mentioned in a lesson body as a citation — so a second implementation here would be a
second set of answers to the same question.

    python3 scripts/done_but_open.py                 # needs a token: reads open issues
    python3 scripts/done_but_open.py --issue 1472    # just this one, no token needed
    python3 scripts/done_but_open.py --json
    python3 scripts/done_but_open.py --json-out /tmp/dbo.json   # one pass, both forms

The scheduled caller is `intake-salvage-digest.yml`, which folds the report into the digest issue it
already maintains — and only when the list is non-empty, so a clean backlog is silent instead of a
daily "nothing to report".

Exit code is 0 whether or not anything is found: this is a report, not a gate. Making it a gate
would block a release on a backlog-hygiene item, which is how gates become noise.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.intake_receipt import lessons_citing  # noqa: E402  (single resolver, on purpose)

REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")


def _token() -> str | None:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var].strip()
    creds = Path.home() / ".git-credentials"
    if creds.is_file():
        for line in creds.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"https://[^:]+:([^@]+)@github\.com", line.strip())
            if m:
                return m.group(1)
    return None


def open_issue_numbers(token: str | None, limit: int = 300) -> list[dict]:
    """Open issues, newest first. Returns dicts so the caller can report an age."""
    if not token:
        raise SystemExit("no GitHub token: set GITHUB_TOKEN or add a github.com entry to ~/.git-credentials")
    out: list[dict] = []
    page = 1
    while len(out) < limit:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO_SLUG}/issues?state=open&per_page=100&page={page}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                batch = json.load(resp)
        except urllib.error.HTTPError as exc:  # a report that cannot run should say why
            raise SystemExit(f"GitHub API returned {exc.code} while listing open issues") from exc
        if not batch:
            break
        for item in batch:
            if "pull_request" in item:
                continue
            out.append({"number": item["number"], "title": item.get("title", ""),
                        "created_at": item.get("created_at", "")})
        page += 1
    return out[:limit]


def _age_days(created_at: str, now: datetime | None = None) -> int | None:
    if not created_at:
        return None
    try:
        then = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ((now or datetime.now(timezone.utc)) - then).days


def findings(issues: list[dict], lessons_dir: Path | None = None) -> list[dict]:
    """The intakes whose lesson already exists. Pure: takes the issue list, returns the report."""
    kwargs = {} if lessons_dir is None else {"lessons_dir": lessons_dir}
    report = []
    for issue in issues:
        lessons = lessons_citing(issue["number"], **kwargs) if lessons_dir else lessons_citing(issue["number"])
        if not lessons:
            continue
        report.append({
            "intake": issue["number"],
            "title": issue.get("title", ""),
            "age_days": _age_days(issue.get("created_at", "")),
            "lessons": [l["path"] for l in lessons],
            "evidence_levels": [l["evidence_level"] for l in lessons],
        })
    return report


def render(report: list[dict]) -> str:
    if not report:
        return ("没有发现「已完成但未关」的 intake。这不是「没东西可看」——"
                "请确认 lessons/ 目录可读；一个永远为空的检查和一个永远为绿的检查一样可疑。")
    lines = [f"**{len(report)} 条 intake 的工作已经在 main 上，但 issue 还开着**", ""]
    lines += ["| intake | 开了多少天 | 满足它的课程 |", "|---|---|---|"]
    for r in sorted(report, key=lambda x: -(x["age_days"] or 0)):
        age = "?" if r["age_days"] is None else str(r["age_days"])
        lines.append(f"| #{r['intake']} | {age} | {', '.join(r['lessons'])} |")
    lines += ["", "每一条都该按 SOP §3 补一条回执再关闭：报料者看不到「没人理」和「已经做完但没说」的区别，"
                  "而后者是我们这边的失误。"]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="intakes that are done but still open (#2040)")
    parser.add_argument("--issue", type=int, action="append", help="check one intake (no token needed)")
    parser.add_argument("--json", action="store_true")
    # The scheduled caller needs the human report *and* a structural "how many?" answer from the
    # same API pass: deciding emptiness by grepping the rendered text for 没有发现 would break the
    # moment somebody rewords the sentence, and printing both costs a second listing of the backlog.
    parser.add_argument("--json-out", type=Path, metavar="PATH",
                        help="also write the machine-readable report here (stdout stays human-readable)")
    args = parser.parse_args(argv)

    if args.issue:
        issues = [{"number": n, "title": "", "created_at": ""} for n in args.issue]
    else:
        issues = open_issue_numbers(_token())

    report = findings(issues)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
