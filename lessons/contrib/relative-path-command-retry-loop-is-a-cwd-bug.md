---
title: "Relative-path command retry loop — No such file or directory means the shell is in the wrong directory"
domain: development
tags:
  - cwd
  - working-directory
  - relative-path
  - retry-loop
  - bash-tool
  - python
  - lesson-gate
status: published
evidence_level: E2
created: '2026-10-03'
updated: '2026-10-03'
source: "intake-issue-2572"
summary_plain: "A script that works in one shell fails in the next because that shell started elsewhere, so re-sending it never helps."
trigger: "No such file or directory on a script that used to work / same command retried and fails identically / can't open file [Errno 2]"
verify: "pwd shows the directory the command was resolved against; re-running with an absolute script path or an explicit cd succeeds where the relative form failed."
provenance:
  issue: "#2572"
  source: "anonymous MCP intake (source: claude-code)"
  evidence: "reproduced locally against scripts/lesson_gate.py"
---

## Problem

A command that has always worked starts failing with a path error, and the failure does not
change no matter how many times it is re-sent:

```text
python3: can't open file '/home/<user>/scripts/lesson_gate.py': [Errno 2] No such file or directory
```

The reported symptom was an agent sending the **identical** command
`python3 scripts/lesson_gate.py lessons/contrib/foo.md` roughly twenty times, each one
returning the same `[Errno 2] No such file or directory`, because the shell's working directory
was not the repository root.

What makes this expensive is that the two readings of the message feel equally plausible —
*"the script is missing / not checked out"* or *"the shell is somewhere else"* — and re-running
is the reflex that costs the most while resolving neither. The file was there the whole time.

## Root Cause

`No such file or directory` from `[Errno 2]` describes **the path that was resolved**, not
whether the target exists in the repository. `python3 scripts/lesson_gate.py` has a relative
script path, and Python resolves it against the *process* working directory. Nothing in the
command carries the repository root.

Two properties of the Bash tool turn this into a loop rather than a one-off error:

- **The working directory persists across calls.** A shell that starts at `~` — or at whatever
  directory the session opened in — is still there on the next call. It does not reset to the
  repository root on its own, so a session that never issues `cd` stays put for its whole life.
- **Retry is a no-op on a deterministic failure.** The exit code and message are a pure function
  of the working directory, so attempt *n+1* is bit-identical to attempt *n*. Repeating the
  command cannot change the input it depends on.

The trap is that `git` masks the problem. `git -C /path/to/repo status` works from any
directory, so a git command issued right before the failing one succeeds and makes the working
directory look correct. It is not — the two commands read the working directory differently.
That is why the whole suite can look healthy right up to the point of failure.

The generalization beyond this one script: **any** relative path in an agent command is resolved
against a session-level directory that nothing in the command establishes. `python3 foo.py`,
`bash scripts/x.sh`, and `./gradlew` all fail identically when it is wrong, and all succeed
identically when it is right.

## Fix

Establish the working directory in the command text, or remove the dependency on it.

**Option 1 — put the `cd` in the command.** The `cd` must appear literally inside the command
string, not be assumed from an earlier call:

```bash
cd /path/to/repo && python3 scripts/lesson_gate.py lessons/contrib/foo.md
```

**Option 2 — absolute paths, no `cd` required.** Preferred when several calls are involved,
because it removes the directory from the set of things that can be wrong:

```bash
python3 /path/to/repo/scripts/lesson_gate.py /path/to/repo/lessons/contrib/foo.md
```

**Option 3 — `PYTHONPATH` for imports, not for the script path.** This fixes module resolution;
it does **not** fix which file gets executed:

```bash
PYTHONPATH=/path/to/repo python3 -m pytest /path/to/repo/tests/
```

**Option 4 — `git -C` for git only.** Correct for git, and a common source of the false
confidence described above. There is no Python equivalent:

```bash
git -C /path/to/repo status
```

**The rule:** when a command fails with `No such file or directory` on a relative path, treat it
as a working-directory question, not a missing-file question. Check the directory **once**:

```bash
pwd && ls scripts/lesson_gate.py
```

and if `ls` finds the file, the directory was wrong — do not retry the original command.

## Verification

Reproduced end to end on this repository, running from a deliberately wrong working directory
(`/home/<user>`) rather than the checkout root (`/tmp/mn-lessons`):

```text
$ cd ~ && pwd
/home/<user>

$ python3 scripts/lesson_gate.py lessons/contrib/foo.md
python3: can't open file '/home/<user>/scripts/lesson_gate.py': [Errno 2] No such file or directory
```

The path in the error is the resolved one — it is prefixed with the *wrong* directory, which is
what distinguishes this from a genuinely missing file.

Both fixes hold from that same wrong directory:

```text
$ git -C /tmp/mn-lessons status --porcelain
?? lessons/contrib/…                       # exit 0 — git -C does not depend on cwd

$ /home/<user>/MisakaNet/.venv/bin/python \
    /tmp/mn-lessons/scripts/lesson_gate.py --help
Lesson Quality Gate — structural validation for new lesson contributions (issue #889).
…
# exit 0 — absolute script path runs from any directory
```

Pass criteria, both halves required:

1. `pwd` reports the directory your paths were resolved against, so the `[Errno 2]` message is
   explainable rather than mysterious.
2. The same logical command succeeds when re-run with an explicit `cd` or an absolute script
   path. If it still fails under both forms, the failure was not the working directory.
