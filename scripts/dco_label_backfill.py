#!/usr/bin/env python3
"""Backfill: remove stale `needs-dco` labels from PRs whose commits are all signed.

Semantics (aligned with .github/actions/dco-audit): merge commits (2+ parents)
do not require Signed-off-by. Only non-merge commits are checked.

Usage:
  python3 scripts/dco_label_backfill.py [--dry-run] [--state all|open|closed]
"""
import json
import os
import subprocess
import sys
import time

REPO = "Ikalus1988/MisakaNet"
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    # fall back to the Ikalus1988 PAT in ~/.git-credentials (maintainer runs)
    cred = os.path.expanduser("~/.git-credentials")
    if os.path.exists(cred):
        for line in open(cred):
            parts = line.strip().split("://")[1].split("@")[0].split(":")
            if len(parts) == 2 and parts[0] == "Ikalus1988":
                TOKEN = parts[1]
                break
if not TOKEN:
    sys.exit("No GH_TOKEN found (set GH_TOKEN or ~/.git-credentials)")

DRY = "--dry-run" in sys.argv
STATE = "all"
for a in sys.argv[1:]:
    if a.startswith("--state="):
        STATE = a.split("=", 1)[1]

HDRS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}


def api(path, method="GET", **kw):
    url = f"https://api.github.com{path}"
    cmd = ["curl", "-sS", "--max-time", "30", "-X", method, "-H", f"Authorization: Bearer {TOKEN}",
           "-H", "Accept: application/vnd.github+json"]
    if kw.get("data") is not None:
        cmd += ["-d", json.dumps(kw["data"])]
    for _ in range(3):
        r = subprocess.run(cmd + [url], capture_output=True, text=True)
        if r.returncode == 0:
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                return r.stdout
        time.sleep(2)
    return None


def iter_prs_with_label():
    """Yield PR numbers currently carrying the needs-dco label."""
    page = 1
    while True:
        items = api(f"/repos/{REPO}/issues?state={STATE}&labels=needs-dco&per_page=100&page={page}")
        if not items:
            break
        prs = [i for i in items if "pull_request" in i and not i.get("pull_request", {}).get("draft")]
        if not prs and len(items) < 100:
            # also break if nothing on this page at all
            break
        for i in prs:
            yield i["number"]
        if len(items) < 100:
            break
        page += 1


def pr_unsigned_commits(n):
    """Count non-merge commits lacking Signed-off-by in PR n."""
    unsigned = []
    page = 1
    while True:
        commits = api(f"/repos/{REPO}/pulls/{n}/commits?per_page=100&page={page}")
        if not commits:
            break
        for c in commits:
            parents = len(c.get("parents", []))
            if parents > 1:
                continue  # merge commit — no sign-off required
            msg = c["commit"]["message"] or ""
            if "Signed-off-by:" not in msg:
                unsigned.append(c["sha"][:10])
        if len(commits) < 100:
            break
        page += 1
        time.sleep(0.05)
    return unsigned


def main():
    removed, kept, errors = [], [], []
    for n in iter_prs_with_label():
        unsigned = pr_unsigned_commits(n)
        if unsigned:
            kept.append((n, unsigned))
            print(f"KEEP   #{n}: {len(unsigned)} unsigned commits {unsigned}")
        else:
            removed.append(n)
            print(f"REMOVE #{n}: all commits signed")
            if not DRY:
                api(f"/repos/{REPO}/issues/{n}/labels/needs-dco", method="DELETE")
        time.sleep(0.05)
    print("\n=== summary ===")
    print(f"mode={DRY and 'DRY-RUN' or 'WRITE'} state={STATE}")
    print(f"removed: {len(removed)}  {removed}")
    print(f"kept (genuinely unsigned): {len(kept)}")
    for n, u in kept:
        print(f"  #{n}: {u}")
    print(f"errors: {len(errors)}")


if __name__ == "__main__":
    main()
