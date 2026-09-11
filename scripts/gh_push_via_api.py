#!/usr/bin/env python3
"""Push files to GitHub via the Git Data API (fallback when `git push` is unusable).

Why this exists: from some networks/CI environments the git protocol to
github.com stalls or times out (`Failed to connect to github.com port 443`,
`GnuTLS recv error (-110)`) while the REST API stays reachable. This script
commits a set of files on top of a branch tip and creates/moves the branch —
without a local clone, a worktree, or the git wire protocol.

It is a *content* pusher, not a merge tool: it writes the exact bytes of the
files you name. Do not use it to push files that must be reviewed as a diff
from a local branch you already pushed — use it when git itself is the blocker.

Examples
--------
    # open a branch with one changed file (then open a PR in the browser/API)
    python3 scripts/gh_push_via_api.py \
        --branch fix/my-thing \
        --message-file /tmp/msg.txt \
        lessons/contrib/my-lesson.md

    # fast-forward main directly (docs-only; refuses if the tip moved mid-flight)
    python3 scripts/gh_push_via_api.py --branch main --direct --message-file /tmp/msg.txt AGENTS.md

Token resolution order: $GITHUB_TOKEN / $GH_TOKEN, then the first github.com entry
in ~/.git-credentials. The token is never printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
DEFAULT_REPO = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")


def resolve_token() -> str:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(var)
        if token:
            return token.strip()
    creds = pathlib.Path.home() / ".git-credentials"
    if creds.is_file():
        for line in creds.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = re.match(r"https://[^:]+:([^@]+)@github\.com", line.strip())
            if match:
                return match.group(1)
    sys.exit(
        "no GitHub token found: set GITHUB_TOKEN, or add a github.com entry to ~/.git-credentials"
    )


class GitHub:
    def __init__(self, repo: str, token: str) -> None:
        self.repo = repo
        self.token = token

    def __call__(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{API}/repos/{self.repo}{path}" if path else f"{API}{path}",
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "misakanet-gh-data-push",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:  # surface the API's own message
            detail = error.read().decode("utf-8", "replace")[:800]
            raise SystemExit(f"GitHub API {method} {path} -> HTTP {error.code}\n{detail}") from None


def blob_mode(path: pathlib.Path) -> str:
    return "100755" if os.access(path, os.X_OK) else "100644"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="files to write (repo-relative paths)")
    parser.add_argument("--branch", required=True, help="branch to create or move")
    parser.add_argument("--base", default="main", help="branch to commit on top of (default: main)")
    parser.add_argument("--message-file", required=True, help="file containing the commit message")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default: {DEFAULT_REPO})")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="move --branch itself (fast-forward only); without it the commit is placed on a new branch",
    )
    args = parser.parse_args()

    gh = GitHub(args.repo, resolve_token())
    message = pathlib.Path(args.message_file).read_text(encoding="utf-8")

    base_ref = gh("GET", f"/git/ref/heads/{args.base}")
    base_sha = base_ref["object"]["sha"]
    base_tree = gh("GET", f"/git/commits/{base_sha}")["tree"]["sha"]
    print(f"base {args.base} = {base_sha[:10]}")

    tree_entries = []
    for raw in args.paths:
        path = pathlib.Path(raw)
        if not path.is_file():
            sys.exit(f"not a file: {raw}")
        blob = gh(
            "POST",
            "/git/blobs",
            {
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
                "encoding": "base64",
            },
        )
        tree_entries.append(
            {
                "path": raw.replace(os.sep, "/"),
                "mode": blob_mode(path),
                "type": "blob",
                "sha": blob["sha"],
            }
        )
        print(f"  blob {blob['sha'][:10]}  {raw}")

    tree = gh("POST", "/git/trees", {"base_tree": base_tree, "tree": tree_entries})
    commit = gh(
        "POST",
        "/git/commits",
        {"message": message, "tree": tree["sha"], "parents": [base_sha]},
    )
    print(f"commit {commit['sha'][:10]}")

    ref = f"refs/heads/{args.branch}"
    existed = True
    try:
        current = gh("GET", f"/git/ref/heads/{args.branch}")["object"]["sha"]
    except SystemExit:
        existed = False
        current = None

    if args.direct:
        if current != base_sha:
            sys.exit(
                f"refusing --direct: {args.branch} is at {current and current[:10]}, "
                f"expected the base {base_sha[:10]} (the branch moved; re-run)"
            )
        gh("PATCH", f"/git/refs/heads/{args.branch}", {"sha": commit["sha"], "force": False})
    elif existed and current != base_sha:
        sys.exit(
            f"refusing to move {args.branch}: it is at {current and current[:10]}, not the base "
            f"{base_sha[:10]} (use --direct to fast-forward main, or pick another --branch)"
        )
    elif existed:
        gh("PATCH", f"/git/refs/heads/{args.branch}", {"sha": commit["sha"], "force": False})
    else:
        gh("POST", "/git/refs", {"ref": ref, "sha": commit["sha"]})

    print(f"pushed {args.branch} -> {commit['sha']}")
    compare = f"https://github.com/{args.repo}/commit/{commit['sha']}"
    print(compare)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
