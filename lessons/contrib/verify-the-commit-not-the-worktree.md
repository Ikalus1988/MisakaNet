---
domain: "devops"
title: "An agent's fix was verified in a working tree and never committed, so the push carried the old bytes"
tags:
  - "git"
  - "staging"
  - "verification"
  - "agent-reliability"
  - "false-green"
  - "code-review"
status: "published"
evidence_level: "E2"
source: "maintainer-agent-session"
summary_plain: "A fix was verified in a working tree but never staged, so the push carried the old bytes and main went red."
trigger: "An agent reports a fix pushed and done; `grep <path>` and `pytest <path>` pass on the machine that made it, yet the merged commit has no trace of the change"
verify: "Read the marker out of the commit rather than the file — `git show HEAD:<path>` must contain it — and run the gate in a detached worktree at that commit. Nothing unstaged exists in either."
provenance:
  source: "maintainer agent session, 2026-10-16"
  evidence: "self-observed and reproduced"
  note: "This is an incident in this repository's own maintenance, written down because the same mistake arrived twice in one day in two different shapes. The revisions named below are ordinary public history; no credentials or local paths are reproduced."
---

# Verify the commit, not the working tree

## Problem

A red-fixture test needed its reference changed: it materialised "the bytes before the fix" with
`git show origin/main:lib/client.js`, which stops being the pre-fix bytes the moment the fix merges. An
agent was asked to pin it to an immutable commit instead. It edited the test, ran it, saw it pass, and
reported the work as delivered, naming a commit for the branch.

The edit was never staged. The commit it named — `dafcf128`, whose message is still the *original*
feature message, not a fixture-fix message — contains `PRE_FIX_SHA` zero times. The push therefore
carried the previous bytes, and the pull request merged them.

The first thing to notice was a **required** CI check going red on `main`, hours later:

```
$ git worktree add --detach /tmp/verify origin/main
$ cd /tmp/verify && python3 -m pytest tests/test_dsh_plugin_panel_localization.py -q
FAILED tests/test_dsh_plugin_panel_localization.py::test_the_gate_can_go_red
1 failed, 6 passed
```

Because that context is one of the four the branch ruleset requires, the red did not merely fail one
test: it **blocked every open pull request**, including several that had nothing to do with it.

The intermediate verification looked convincing and was worthless:

```
$ cd /tmp/wt-sidebar          # the agent's worktree, fix applied but unstaged
$ grep -c 'PRE_FIX_SHA' tests/test_dsh_plugin_panel_localization.py
12                            # ← the working tree
$ python3 -m pytest tests/test_dsh_plugin_panel_localization.py -q
7 passed                      # ← the working tree

$ git show dafcf128:tests/test_dsh_plugin_panel_localization.py | grep -c 'PRE_FIX_SHA'
0                             # ← the commit that was actually pushed
```

## Root cause

Two independent failures, and the second is the one worth generalising:

1. **The producer never staged the file.** It ran the test, saw green, and committed — but `git commit`
   without `git add` (or an `--amend` that did not include the path) records the index, not the working
   tree. The commit message was also unchanged, which is the visible tell: a commit that claims to fix
   something but whose subject still describes the earlier work usually contains only that earlier work.
2. **The verifier read the working tree.** `grep <path>` and `pytest <path>` both see unstaged edits, so
   they answer "is the change *here* on this machine", not "is the change in the artifact that ships".
   The verification and the artifact were different objects, and nothing in the process compared them.

This is the same shape as a family of failures that are cheap to avoid and expensive to find: a check
that passes against an object the user never receives. A published byte count that matches no revision.
A local render of an old build. A test that reads a moving ref. In every case the *evidence* was real and
the *subject* was wrong, which is why it reads as done.

## Fix

**Compare the artifact, not the directory.** One command, run before pushing:

```bash
git status --porcelain                 # must be empty; anything here is not in the commit yet
git show HEAD:<path> | grep -c '<marker>'   # the count you expect, from the object, not the file
```

For anything that matters, close the loop with the object itself — materialise the commit somewhere that
cannot see the working tree and run the gate there:

```bash
git worktree add --detach /tmp/verify "$(git rev-parse HEAD)"
cd /tmp/verify && pytest <the gate that must pass>
```

For an agent's work specifically, ask for the marker **from the commit**, not the file. "Show me
`git show HEAD:<path> | grep -c PRE_FIX_SHA`" cannot be satisfied by an unstaged edit, and it takes one
line, where the alternative is discovering it from a red `main` that is blocking other people's merges.

Two smaller habits that would each have caught this one:

* **A commit message that still describes the previous change is a smell.** If the subject did not change,
  suspect the contents did not either.
* **CI is not the first line of defence for this class.** The red arrived after the merge, on a required
  check, with a queue behind it. The check that would have caught it was available locally and cost a
  second.

## Verification

The check that matters is a comparison between the artifact and what was claimed about it, so the
verification is stated as two observations of the same file at the same moment.

On the revision that shipped, **the commit and the worktree disagreed**: reading
`dafcf128:tests/test_dsh_plugin_panel_localization.py` out of the object produced no `PRE_FIX_SHA`
anywhere, while the file on disk in the same worktree carried twelve occurrences of it. Materialising the
merged commit in a detached worktree then reproduced the failure that had reached CI — the red-fixture
test failing with six passes beside it — which is the observation that identified the loss in the first
place, after it had already blocked the repository's merge queue.

After the change was staged and committed, the comparison **on the commit** reported the twelve
occurrences, the working tree had nothing left to commit, and the same gate passed from a clean checkout
of `main` (seven passed, none failing). The order to repeat is: reproduce against the object, fix, then
compare against the object again — never against the file that happens to be on disk.
