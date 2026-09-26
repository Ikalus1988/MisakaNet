---
domain: "ci"
title: "A whole-file content push silently reverts the lines another writer owns"
tags: ["git", "release-please", "content-push", "version-drift", "required-checks", "guard-design"]
status: "published"
created: "2026-09-25"
evidence_level: "E0"
evidence_refs:
  - "commit:c7eea29edc"
  - "issue:#2239"
  - "ci:https://github.com/Ikalus1988/MisakaNet/actions/runs/36134211467"
summary_plain: "Pushing whole files from a stale checkout reverts lines a release bot owns, and a marker-only gate cannot see it."
trigger: "docs-only PR fails a version consistency check; release badge or version string older than the manifest; branch built by pushing file contents through an API"
verify: "Every managed line's value equals the manifest, proven by a test that fails on an older value, and the pushed diff holds no hunk you did not write"
provenance:
  source: "MisakaNet repository, 2026-09-25: a docs-only PR went red on nine test legs, and the same shape had already reached the staging of a worker release"
---

# A whole-file content push silently reverts the lines another writer owns

## Problem

Two incidents on the same repository, in one day, from the same cause.

**First**: a documentation pull request — three files, a legend on a web page — was red on **nine**
`test` legs plus the audit job, all on one assertion:

```
tests/test_version_consistency.py::test_site_badge_matches_the_manifest
AssertionError: site badge v2.34.0 != manifest 2.35.0
1 failed, 2459 passed
```

The branch's copy of the page carried `v2.34.0`; the release manifest on `main` said `2.35.0`. The
branch had never touched that line. Nobody had noticed for two CI generations.

**Second**, hours later: preparing a worker fix, the local checkout's `workers/register-proxy-sw.js`
read `version: env.MCP_VERSION || "2.34.0"` while `main` read `2.35.0`. The plan was to push that file
as whole-file content. Nothing in the test suite objected: the string every MCP client reads as the
server version was about to be rolled back one release, and every local test was green.

## Root Cause

The push mechanism writes **exact bytes**, and the guard asked the wrong question.

### 1. A content pusher is not a patch

This repository pushes branches through the Git Data API (`scripts/gh_push_via_api.py`) because the git
wire protocol is unusable from some networks. It creates a blob per named file from the **local
working copy** and commits it on top of the base — there is no diff, no three-way merge, and no error
when the blob happens to be older than the base's:

```
base main = 436dc50c09
  blob c005c00992  .github/workflows/pr-checks.yml
  ...
commit 579b42b945
pushed fix/ocr-review-pass-4 -> 579b42b945
```

Anything the local file does not contain is deleted from the branch. Lines owned by *another writer* —
a release bot bumping a version, a formatter, a codegen step — are indistinguishable to this tool from
lines you meant to change. So the invariant is not "did I edit this line?" but "**is my local copy
current?**", and a full-blown `git pull` is not enough either: the working copy here was current for
everything except one release commit.

### 2. The gate checked presence, not value

`tests/test_version_consistency.py` had a rule for exactly this class — R8, written after a release
step interpolated an empty `VERSION` and rewrote the badge to a bare `v` — and it read:

```python
annotated = [line for line in text.splitlines()
             if "x-release-please-version" in line and re.search(pattern, line)]
if len(annotated) != 1: problems.append(f"{rel} has {len(annotated)} annotated lines")
```

It proves the *writer* exists: one line per managed file that release-please can rewrite. It never
compares the value to anything, and the value is the only thing that can be wrong. So the two files
that were a release behind in the working copy — the CLI version and the worker's MCP `version` — were
**unobservable**, while `docs/index.html` was caught only because a *separate* rule (R8's own
assertion against the manifest) happened to cover that one file.

A rule that checks "the marker is present" cannot go red on the failure it was written for. The
failure is a relation between two files, so the rule has to be a relation too.

## Solution

### 1. Make the managed value a relation, not a property

Assert every annotated line against the single source of truth, for **all** managed files (the loop is
over one registry, so a new managed file cannot be forgotten):

```python
def _annotated_value_problems(root: Path) -> list[str]:
    """Annotated version lines whose value is not the manifest's."""
    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]
    problems = []
    for rel, pattern in PINNED_VERSION_FILES.items():
        for line in (root / rel).read_text(encoding="utf-8").splitlines():
            if "x-release-please-version" not in line or not re.search(pattern, line):
                continue
            found = re.findall(r"\d+\.\d+\.\d+", line)
            if manifest not in found:
                problems.append(f"{rel} carries {found or 'no version'} on its annotated line, "
                                f"the manifest says {manifest}")
    return problems
```

Add the inverse mutation so the rule can be shown to fail: copy the managed files plus the manifest to
a scratch tree, set one of them to `0.0.1`, require a finding for that file, restore, repeat.

### 2. Diff against the base before pushing, not after

```
# byte-compare your local file with the base revision, then read the hunks
python3 scripts/cmp_remote.py <the files you are about to push>
git diff --no-index /tmp/remote/<file> <file>
```

The rule to apply to the output: **every hunk must be one you wrote**. A hunk that removes a newer
version, a newer date or a generated banner is a revert, and it is the only warning you get.

### 3. Prefer guards that run before the mutation

A check placed after a writer has already replaced the file describes the artifact you just created.
If it recomputes the same thing the writer does, it is a tautology; if it validates the *output*, the
bad output is already on disk and, in a self-merging job, already staged for a pull request.

## Verification

* The new rule fails when it should. With `docs/index.html`, `scripts/misakanet_cli.py` and
  `workers/register-proxy-sw.js` each set to `0.0.1` in a scratch copy, `_annotated_value_problems()`
  reports that file; with the tree restored it reports nothing.
* It reproduced the incident it was written for: the working copy that produced the red PR has
  `docs/index.html` at `v2.34.0` against a `2.35.0` manifest — the rule names it.
* After repair, the documentation PR carried **4** hunks against `main` (the intended legend) instead
  of 5 (legend + reverted badge), and merged green; the worker branch was verified the same way before
  it was pushed.

## Notes

* The failure mode is not specific to GitHub's API. `git add -A` in a job whose checkout moved (say a
  release action that commits into the workspace), a template sync, a config-file generator, or any
  "write the whole file because diffing is hard" step has the same property: **what the local copy
  lacks, the destination loses**.
* Repeated damage came from the same root in a different costume the same day: a squash-merged branch
  that kept being pushed to (`mergeable_state: dirty`), and an older queued deployment that would have
  shipped the pre-repair revision if its approval had arrived first. Whole-artifact workflows need
  "which revision is this?" answered explicitly, every time.
* Related: `tests/test_version_consistency.py` (the relation rule), `scripts/gh_push_via_api.py`
  (the content pusher), `docs/maintainer/automation-lands-via-pr.md` (the lander path, which checks out
  and pushes with git rather than by content).
