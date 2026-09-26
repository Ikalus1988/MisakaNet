#!/usr/bin/env python3
"""What would this push actually change — and what would it silently revert?

Why this exists. `scripts/gh_push_via_api.py` is a **content** pusher: it writes the local bytes of
the files you name onto a branch based on the current remote tip. That is the right tool when the git
wire protocol is unusable (it usually is from this network), and it has one failure mode that has now
bitten this repository twice:

    if your working copy of a file is older than the remote's, every line the remote gained since is
    silently reverted — and no test on the branch can see it, because the branch is internally
    consistent.

Both incidents are recorded. A release branch carried `docs/index.html` from *before* the release, so
the badge reverted from 2.35.0 to 2.34.0 and only `test_version_consistency.py` noticed. Separately,
`workers/register-proxy-sw.js` was one release behind on a line carrying an `x-release-please-version`
annotation, and **nothing** reddened: the test asserted the annotation was present, not that its value
was current. The team's answer was a manual ritual — "diff every file you are about to push against
`main` first" — which is a good rule and a bad mechanism, because it is exactly the kind of step that
is skipped when the network is flaky and the push is urgent.

So this script is that ritual, with the judgement left where it belongs. It does **not** try to decide
whether a removal is intended; it cannot know. It shows you the removals, marks the ones that look like
a tracked artifact's managed line, and fails only on the things that are unambiguous:

  * a file you named is **identical** to `main`  -> you are about to push nothing (stale branch, wrong
    file); exit 1
  * a file you named is **absent locally**       -> the push would delete it from main; exit 1
  * a **value behind main** (same wording, main's number larger) -> the push reverts main's value; exit 1
  * a **value ahead of main** (same wording, local number larger) -> reported, **not** failed: that is
    either a legitimate bump travelling with whatever the number describes, or a count whose corpus did
    not come along, and the tool cannot see the rest of the push. Issue #2274 is what happens when this
    distinction is missing: a correct section-count bump was reported as `VALUE REVERTED`.
  * `--all`: something on `main` is **missing from this checkout** -> the checkout is behind, and every
    push from it risks a revert; exit 1
  * `--branch <name>`: that branch's PR is **already merged** -> the commit would land on the branch and
    nowhere else; exit 1. This is not hypothetical: `--base <branch> --branch <branch>` is the documented
    way to add a commit to an open PR, auto-merge is fast here, and two follow-up commits were lost this
    way on 2026-09-26.

Usage
-----
    python3 scripts/push_preflight.py <path> [<path> ...]     # the files you intend to push
    python3 scripts/push_preflight.py --all                   # whole-tree drift map vs main
    python3 scripts/push_preflight.py --all --json            # machine-readable
    python3 scripts/push_preflight.py --branch my/branch <path>   # also refuse an already-merged branch

Two costs, deliberately: the remote tree arrives in **one** API call for `--all` (2 with the commit
lookup), and one more per *named* file for the reverse diff. `--all` never fetches file contents.

Token resolution matches `gh_push_via_api.py`: `$GITHUB_TOKEN` / `$GH_TOKEN`, then the first
`github.com` entry in `~/.git-credentials`. The token is never printed.

`git ls-files` is read with `-c core.quotepath=false`. Without it git escapes non-ASCII paths as octal
inside quotes, and every CJK lesson filename in this repository turns into a fabricated "only local"
finding — a mistake worth naming, because it was made while writing this script.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_REPO = os.environ.get("GITHUB_REPOSITORY", "Ikalus1988/MisakaNet")
API = "https://api.github.com"

# Lines whose value is owned by a *writer* other than the file's last human editor: a release bot, the
# lesson-count SSOT, a version-aligner. Reverting one of these is the incident class this script is
# about, so they are called out by name rather than left in a wall of diff. These are a *highlight*
# only — see `value_reverts` for what actually fails, and why a bare pattern match must not.
MANAGED_LINE_PATTERNS = (
    ("lesson count", re.compile(r"\b\d[\d,]*\+?\b[^\n]{0,60}?\blessons?\b", re.IGNORECASE)),
    # A "registered-node count" row was retired here on 2026-09-26 with the number itself: no surface
    # publishes one any more (tests/test_lesson_count_ssot.py asserts that, in the same change), so the
    # row could only ever have flagged historical text in handoff documents.
    ("release-please annotated version", re.compile(r"x-release-please-version")),
    ("package/manifest version", re.compile(r'"(?:version|\.release-please-manifest)"\s*:')),
    ("badge version", re.compile(r"badge/version|img\.shields\.io/badge/version")),
    ("live counter mirror", re.compile(r'"current"\s*:\s*\d{4,}')),
)


def credentials_token(path: pathlib.Path) -> str | None:
    """The password for **exactly** `github.com` out of a `~/.git-credentials` file, or None.

    The host is compared after parsing, not by substring. `"github.com" in line` also accepts
    `https://user:pw@notgithub.com/` and `https://user:pw@github.com.example.net/`, and this function's
    entire job is deciding which credential to send where — a credential file is exactly where a
    second host is likely to appear. CodeQL raised this as
    `py/incomplete-url-substring-sanitization` on the substring version (alert #285); the neighbouring
    `scripts/gh_push_via_api.py` was never affected because it anchors a regex to `github\\.com`.
    """
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = urllib.parse.urlsplit(line)
        except ValueError:                      # not a URL at all — skip it rather than guess
            continue
        if parsed.hostname != "github.com":
            continue
        if not parsed.username or parsed.password is None:
            continue
        return urllib.parse.unquote(parsed.password)
    return None


def resolve_token() -> str:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key]
    credentials = pathlib.Path.home() / ".git-credentials"
    if credentials.is_file():
        token = credentials_token(credentials)
        if token:
            return token
    raise SystemExit("no GitHub token: set $GITHUB_TOKEN or put github.com credentials in ~/.git-credentials")


def _get(url: str, token: str, accept: str = "application/vnd.github+json", attempts: int = 3) -> bytes:
    """One GET, retried. The network here loses roughly one connection in four.

    Retrying is not defensive padding: this script exists to be run **before every push**, and a
    preflight that fails spuriously on a flaky link is a preflight that gets skipped — which is exactly
    how the manual ritual it replaces was abandoned. `IncompleteRead` is caught by name because that is
    what this network actually does (a truncated body on an otherwise successful response, measured
    while fetching this repository's own tree on the first run of this script).
    """
    last: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "User-Agent": "misakanet-push-preflight",
        })
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError:
            raise                              # a real answer from the API; retrying would not change it
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError,
                OSError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    raise SystemExit(f"GitHub unreachable after {attempts} attempts: {type(last).__name__}: {last}")


def remote_tree(repo: str, ref: str, token: str) -> tuple[str, dict[str, str]]:
    """`(commit_sha, {path: blob_sha})` for the whole tree — one API call for the tree itself."""
    head = json.loads(_get(f"https://api.github.com/repos/{repo}/commits/{ref}", token))
    sha = head["sha"]
    tree = json.loads(_get(f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1", token))
    if tree.get("truncated"):
        raise SystemExit(f"remote tree for {sha[:10]} is truncated; results would be incomplete")
    return sha, {e["path"]: e["sha"] for e in tree["tree"] if e["type"] == "blob"}


def remote_bytes(repo: str, ref: str, path: str, token: str) -> bytes:
    import base64
    payload = json.loads(_get(f"https://api.github.com/repos/{repo}/contents/{path}?ref={ref}", token))
    return base64.b64decode(payload["content"])


def local_blob_hashes(paths: list[str]) -> dict[str, str | None]:
    """Blob hashes of the *working tree* (not the index): git hash-object reads files as they are.

    One subprocess for all paths. A path that does not exist hashes to `None` rather than raising,
    because "absent locally" is itself a finding.
    """
    if not paths:
        return {}
    existing = [p for p in paths if (REPO / p).is_file()]
    result: dict[str, str | None] = {p: None for p in paths}
    if not existing:
        return result
    proc = subprocess.run(["git", "hash-object", "--stdin-paths"], input="\n".join(existing),
                          capture_output=True, text=True, cwd=REPO)
    if proc.returncode != 0:
        raise SystemExit(f"git hash-object failed: {proc.stderr.strip()}")
    for path, sha in zip(existing, proc.stdout.split()):
        result[path] = sha
    return result


def tracked_paths() -> list[str]:
    proc = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"],
                          capture_output=True, text=True, cwd=REPO)
    if proc.returncode != 0:
        raise SystemExit(f"git ls-files failed: {proc.stderr.strip()}")
    return [p for p in proc.stdout.split("\n") if p]


def classify(remote: dict[str, str], local: dict[str, str | None]) -> dict[str, str]:
    """`path -> SAME | DIFF | NEW | ABSENT` for every remote path, plus local-only keys.

    Pure: no network, no git. The whole classification is testable with two dicts.
    """
    out: dict[str, str] = {}
    for path, sha in remote.items():
        mine = local.get(path)
        if mine is None:
            out[path] = "ABSENT"          # in main, not in this working tree
        elif mine == sha:
            out[path] = "SAME"
        else:
            out[path] = "DIFF"
    return out


def removals(remote_text: str, local_text: str) -> list[str]:
    """The lines `main` has and the local copy does not — i.e. what a whole-file push reverts.

    Multiset difference rather than a line diff: the question is "which content would be lost", and a
    line that appears twice on main and once locally is one line of loss, not a hunk boundary problem.
    """
    from collections import Counter
    have = Counter(remote_text.splitlines())
    mine = Counter(local_text.splitlines())
    lost = have - mine
    return [line for line, count in lost.items() for _ in range(count)]


def managed(lines: list[str]) -> list[str]:
    """The subset of `lines` that looks like another writer's value. A highlight, never a verdict."""
    hits = []
    for line in lines:
        for label, pattern in MANAGED_LINE_PATTERNS:
            if pattern.search(line):
                hits.append(f"{label}: {line.strip()[:100]}")
                break
    return hits


_NUMBER = re.compile(r"\d[\d,]*")


def _wording(line: str) -> str:
    """The line with its numbers blanked — "same sentence, different value" becomes comparable.

    This is what makes the difference between a value revert and an edit. A reworded count sentence
    (which `scripts/sync_lesson_count.py`'s SITES registry exists to do) has a *different* wording on
    each side and must not be reported as a loss; a sentence whose wording survives locally while its
    number moves is one thing only — the remote's value was dropped.
    """
    return _NUMBER.sub("#", line).strip()


def _numbers(line: str) -> list[float]:
    return [float(n.replace(",", "")) for n in _NUMBER.findall(line)]


def value_changes(lost: list[str], local_text: str) -> list[tuple[str, str]]:
    """`(line, direction)` for removals that are a *value* changing, not a rewording.

    Deliberately narrower than `managed()`. Failing on every managed-shaped removal would block the
    documented workflow of rewording a count sentence and re-registering it in
    `sync_lesson_count.py` — the sentence is removed, the replacement is not a loss, and a gate that
    cannot tell those apart is a gate that gets switched off. Requiring the *wording* to be unchanged on
    both sides isolates the case the two recorded incidents were: same sentence, different number.

    **Direction is reported, because the two directions are different hazards** (issue #2274, found by this
    tool flagging a correct edit of its own author):

    * `behind` — main's number is larger, so pushing reverts main's value. A definite loss;
    * `ahead` — the local number is larger. That is either a legitimate bump *accompanied by whatever the
      number describes* (adding a workflow row and its section count, say) or a count whose corpus did not
      come along. The tool cannot see which, because it cannot see the rest of the push — so it says so
      instead of guessing, and does not fail.

    The first version reported both as "VALUE REVERTED", which was both a mislabel and a false alarm on a
    routine operation.
    """
    here: dict[str, str] = {}
    for line in local_text.splitlines():
        here.setdefault(_wording(line), line)
    out: list[tuple[str, str]] = []
    for line in lost:
        wording = _wording(line)
        if not wording or wording == line.strip() or wording not in here:
            continue
        mine = here[wording]
        remote_numbers, local_numbers = _numbers(line), _numbers(mine)
        if not remote_numbers or not local_numbers:
            continue                       # wording differs only in a non-numeric way
        remote_sum, local_sum = sum(remote_numbers), sum(local_numbers)
        if remote_sum == local_sum:
            # Same numbers, so there is no value change to judge — the wording match came from whitespace
            # alone (`_wording` strips it). Reported as "ahead" before this check, which made a trailing
            # space look like a bump (found by its own test; trailing whitespace is a real shape here).
            continue
        out.append((line, "behind" if remote_sum > local_sum else "ahead"))
    return out


def merged_branch_problem(repo: str, branch: str, token: str) -> str | None:
    """Why pushing to `branch` is pointless, or None.

    `gh_push_via_api.py --base <branch> --branch <branch>` is the documented way to add a commit to an open
    PR (§7.6). Auto-merge here is fast, so the branch is often merged already, and the new commit then
    **exists only on the branch**: not on the PR (closed), not on main, and locally everything looks fine.
    That happened twice in one session (2026-09-26) — a review fix and a default flip were both lost, and the
    second was found by reading main's file, not by any tool. The cost is two extra PRs and a period where
    the fix is believed to be live.
    """
    owner = repo.split("/")[0]
    payload = _get(f"{API}/repos/{repo}/pulls?state=closed&head={owner}:{branch}&per_page=100",
                   token, accept="application/vnd.github+json")
    pulls = json.loads(payload)
    merged = [p for p in pulls if p.get("merged_at")]
    if not merged:
        return None
    newest = max(merged, key=lambda p: p["merged_at"])
    return (f"branch {branch!r} was already merged into {newest['base']['ref']} "
            f"({newest['merge_commit_sha'][:10]}, {newest['merged_at']}); a commit pushed now lands on the "
            f"branch only. Open a new branch from the current main instead "
            f"(the repo rule: after a squash merge, do not push to the same branch).")


def report_named(args, token: str, ref: str, paths: list[str]) -> int:
    _, remote = remote_tree(args.repo, ref, token)
    local = local_blob_hashes(paths)
    problems: list[tuple[str, str]] = []          # (path, kind) — the closing advice depends on the kind
    for path in paths:
        state = classify(remote, {path: local[path]}).get(path, "NEW")
        if state == "ABSENT":
            print(f"  ❌ {path}: not present in the working tree — pushing this would DELETE it from {ref}")
            problems.append((path, "absent"))
            continue
        if state == "SAME":
            print(f"  ❌ {path}: identical to {ref} — nothing to push (stale branch, or the wrong file?)")
            problems.append((path, "identical"))
            continue
        if state == "NEW":
            print(f"  ✅ {path}: not on {ref} yet (new file — nothing to revert)")
            continue
        remote_text = remote_bytes(args.repo, ref, path, token).decode("utf-8", errors="replace")
        local_text = (REPO / path).read_text(encoding="utf-8", errors="replace")
        lost = removals(remote_text, local_text)
        changes = value_changes(lost, local_text)
        reverts = [line for line, direction in changes if direction == "behind"]
        ahead = [line for line, direction in changes if direction == "ahead"]
        hit = managed(lost)
        print(f"  {'⚠️ ' if lost else '✅ '}{path}: {len(lost)} line(s) {ref} has that your copy lacks")
        for line in lost[: args.max_removals]:
            print(f"       - {line.strip()[:120]}")
        if len(lost) > args.max_removals:
            print(f"       … {len(lost) - args.max_removals} more")
        for line in hit:
            print(f"       ⚠️  managed line — {line}")
        for line in reverts:
            print(f"       ❌ VALUE BEHIND main — pushing this reverts main's value: {line.strip()[:100]}")
        for line in ahead:
            print(f"       ⚠️  VALUE AHEAD of main — {line.strip()[:100]}")
        if ahead:
            print("           (ahead is not automatically wrong: confirm the files that *describe* this "
                  "number are in the same push — e.g. a section count bump must travel with its new row. "
                  "If they are not, you are about to advertise a value the repository does not support.)")
        if reverts:
            problems.append((path, "behind"))
        elif hit:
            print("       (managed-shaped removals above, but the wording also differs — read as an edit, "
                  "not a revert; confirm by eye before pushing)")
    if problems:
        print(f"\n❌ {len(problems)} problem(s): {', '.join(f'{path} ({kind})' for path, kind in problems)}")
        # The advice is per kind, and saying the wrong one is its own defect: the first version printed the
        # number-and-wording explanation for every kind, including "identical to main", which has nothing to
        # do with numbers (found by running it on a file that had just been merged).
        advice = {
            "identical": "nothing to push: re-check that you edited the file, and that this branch is not "
                         "already merged.",
            "absent": "restore the file from main before pushing, or the push deletes it.",
            "behind": "a sentence is the same on both sides while main's number is larger, so pushing "
                      "reverts it: re-read the file from main and re-apply your change on top of it.",
        }
        for kind in ("absent", "identical", "behind"):
            if any(k == kind for _, k in problems):
                print(f"   * {advice[kind]}")
        return 1
    print(f"\n✅ every named file differs from {ref}; review the ⚠️ lines above before pushing")
    return 0


def report_all(args, token: str, ref: str) -> int:
    sha, remote = remote_tree(args.repo, ref, token)
    local = local_blob_hashes(sorted(remote))
    state = classify(remote, local)
    tracked = set(tracked_paths())
    diffs = sorted(p for p, s in state.items() if s == "DIFF")
    absent = sorted(p for p, s in state.items() if s == "ABSENT")
    only_local = sorted(p for p in tracked if p not in remote)
    print(f"{ref} = {sha[:10]} · {len(remote)} blobs · DIFF {len(diffs)} · in-{ref}-not-here {len(absent)} "
          f"· here-not-in-{ref} {len(only_local)}")
    for label, rows in (("DIFF", diffs), ("ONLY-REMOTE (checkout is behind)", absent),
                        ("ONLY-LOCAL (deleted on main)", only_local)):
        for path in rows[: args.max_list]:
            print(f"  {label:34} {path}")
        if len(rows) > args.max_list:
            print(f"  {label:34} … {len(rows) - args.max_list} more")
    if args.json:
        (REPO / args.json).write_text(json.dumps(
            {"ref": ref, "commit": sha, "diff": diffs, "only_remote": absent, "only_local": only_local},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  (wrote {args.json})")
    if absent:
        print(f"\n❌ {len(absent)} path(s) exist on {ref} and not in this checkout. Every push from here "
              "risks reverting whatever they carry — sync first (`git fetch`, or restore those paths from "
              "the API) rather than pushing from this tree.")
        return 1
    print(f"\n✅ this checkout contains everything on {ref}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show what a content push would change, and what it would silently revert.")
    parser.add_argument("paths", nargs="*", help="files you intend to push (repo-relative)")
    parser.add_argument("--all", action="store_true", help="whole-tree drift map instead of named files")
    parser.add_argument("--ref", default="main", help="branch to compare against (default: main)")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default: {DEFAULT_REPO})")
    parser.add_argument("--max-removals", type=int, default=12, help="removed lines to print per file")
    parser.add_argument("--max-list", type=int, default=60, help="paths to print per class with --all")
    parser.add_argument("--json", metavar="PATH", help="with --all: also write the drift map here")
    parser.add_argument("--branch", help="the branch you intend to push to: refuses if its PR already merged")
    args = parser.parse_args(argv)

    if not args.all and not args.paths:
        parser.error("name the files you intend to push, or pass --all")

    try:
        token = resolve_token()
    except SystemExit as exc:
        print(f"  ❌ {exc}", file=sys.stderr)
        return 2

    try:
        if args.branch:
            problem = merged_branch_problem(args.repo, args.branch, token)
            if problem:
                print(f"  ❌ {problem}")
                return 1
        if args.all:
            return report_all(args, token, args.ref)
        return report_named(args, token, args.ref, args.paths)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"  ❌ GitHub API {exc.code}: {body}", file=sys.stderr)
        return 2
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError, OSError) as exc:
        print(f"  ❌ GitHub API unreachable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
