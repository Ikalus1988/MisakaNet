#!/usr/bin/env python3
"""Find the decisions that are waiting for a person, and say how long they have waited.

Why this exists (2026-10-28)
----------------------------
Measured on 2026-10-27: **94 non-corpus issues open, 41 never commented on**, and of the six
`decision`-labelled issues, five had sat at zero comments since 2026-09-30. The technical half of
that backlog moves — 30 non-corpus issues were closed in October, all of them P1/P2 bugs and docs —
while the decision half does not, because nothing in this repository ever asks about it.

The intake side already has that machinery (`issue-intake-triage.yml`, `intake-salvage-digest.yml`);
this is the same shape for the class that has no automation: a list, produced on a schedule, of
issues that are **labelled as needing a decision and that no person has replied to**.

What it deliberately does not do:

* **It does not close or label anything.** The repository has one rule about automated decisions —
  don't — and this script is a reading list, not a judge.
* **It does not guess who should decide.** Assignees exist; if an issue has one, the digest says so
  rather than inventing an owner.

Usage
-----
    python3 scripts/decision_queue.py                      # human table
    python3 scripts/decision_queue.py --json               # machine summary
    python3 scripts/decision_queue.py --min-age-days 30    # only the long-waiting ones
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# Labels that mean "this is waiting for a decision, not for work". A `decision` issue and a
# `product-design` issue are the same thing to a reader: something has to be chosen.
DECISION_LABELS = ("decision", "product-design")
# No reply from a *person* is the signal: someone has spoken about it, so it is not waiting on
# silence. A comment is a weak proxy, and it is the one that was measured (41 of 94 never got one).
#
# Bots do not count. Every issue that arrives through `misakanet_submit_intake` gets a triage comment
# from `github-actions` within seconds, so "zero comments" kept every automated proposal out of this
# queue forever — measured 2026-11-04 on #4413/#4414. The queue is about a person having replied.
DEFAULT_MIN_AGE_DAYS = 14

BOT_LOGINS = {
    "github-actions", "github-actions[bot]",
    "dependabot", "dependabot[bot]",
    "renovate", "renovate[bot]",
}


def human_comments(issue: dict) -> list[dict]:
    """The comments a person wrote. A bot's triage note is not a reply about the decision."""
    out = []
    for comment in issue.get("comments") or []:
        login = ((comment.get("author") or {}).get("login") or "").strip().lower()
        if login in BOT_LOGINS or login.endswith("[bot]"):
            continue
        out.append(comment)
    return out


def recent_human_reply(issue: dict, now: datetime, within_days: int) -> dict | None:
    """A person's comment newer than the window, or None.

    The exit rule used to be "any comment ever", which is wrong in both directions: an agent's
    recommendation, posted under the owner's login, cleared the row forever (#4399 will never
    return to the list), while a decision that got one reply and then stalled never came back
    either. Engagement is recency, not existence — the window is the same age gate the queue uses
    for the issue itself.
    """
    cutoff = now - timedelta(days=within_days)
    for comment in human_comments(issue):
        raw = comment.get("createdAt")
        if not raw:
            continue
        try:
            created = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if created >= cutoff:
            return comment
    return None


def fetch(repo: str, limit: int = 300) -> list[dict]:
    out = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "open", "--limit", str(limit),
         "--json", "number,title,labels,comments,createdAt,assignees,url"],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"error: gh failed: {out.stderr[:300]}")
    return json.loads(out.stdout or "[]")


def age_days(issue: dict, now: datetime) -> int:
    created = datetime.fromisoformat(issue["createdAt"].replace("Z", "+00:00"))
    return (now - created).days


def select(issues: list[dict], now: datetime, min_age_days: int = DEFAULT_MIN_AGE_DAYS) -> list[dict]:
    """Open, decision-labelled, nobody has commented, and older than the threshold.

    Sorted oldest first: the cost of a decision grows with how long it has been avoided, and the
    one at the top of the list is the one that has been avoided longest.
    """
    picked = []
    for issue in issues:
        labels = {l["name"] for l in issue.get("labels", [])}
        if not (labels & set(DECISION_LABELS)):
            continue
        if recent_human_reply(issue, now, min_age_days):
            continue
        age = age_days(issue, now)
        if age < min_age_days:
            continue
        picked.append({**issue, "age_days": age, "waiting_labels": sorted(labels & set(DECISION_LABELS))})
    return sorted(picked, key=lambda i: (-i["age_days"], i["number"]))


def render(rows: list[dict], repo: str, now: datetime, min_age_days: int) -> str:
    if not rows:
        return (f"No decision has been waiting more than {min_age_days} days without a comment. "
                f"Checked {len(rows)} matching issue(s) at {now.strftime('%Y-%m-%d %H:%M UTC')}.")
    lines = [
        f"# Decision queue — {len(rows)} waiting",
        "",
        f"Open issues labelled `{'`/`'.join(DECISION_LABELS)}`, **no reply from a person in the last "
        f"{min_age_days} days**, at least "
        f"{min_age_days} days old. As of {now.strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        "| # | age | issue | label |",
        "|---|---|---|---|",
    ]
    for row in rows:
        assignee = row.get("assignees") or []
        owner = f" (assigned: {assignee[0]['login']})" if assignee else ""
        title = row["title"].replace("|", "\\|")[:90]
        lines.append(f"| [#{row['number']}]({row['url']}) | {row['age_days']}d | {title}{owner} "
                     f"| {', '.join(row['waiting_labels'])} |")
    lines += [
        "",
        "Nothing here is closed automatically. A row leaves this list while a person is replying on the "
        "issue — a decision, a deferral with a trigger, or a rejection all count; silence does not. "
        "A bot's triage comment does not count, and an old reply does not keep an undecided issue off "
        "the list forever.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default="Ikalus1988/MisakaNet")
    ap.add_argument("--min-age-days", type=int, default=DEFAULT_MIN_AGE_DAYS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    rows = select(fetch(args.repo), now, args.min_age_days)
    if args.json:
        print(json.dumps({"repo": args.repo, "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "min_age_days": args.min_age_days, "count": len(rows),
                          "issues": [{k: r[k] for k in ("number", "title", "url", "age_days",
                                                        "waiting_labels")} for r in rows]},
                         ensure_ascii=False, indent=1))
    else:
        print(render(rows, args.repo, now, args.min_age_days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
