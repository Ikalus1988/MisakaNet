---
domain: "development"
title: "piping a command into tail hides its exit code: a failing gate reads as exit 0"
tags: [shell, bash, exit-code, pipefail, pipestatus, verification, ci, tail]
status: "published"
evidence_level: "E2"
summary_plain: "Piping a command into tail makes $? report tail's status (0), so a failed check looks like it passed."
trigger: "exit code always 0 after cmd 2>&1 | tail; pipeline hid a non-zero exit; gate looked green but failed"
verify: "`bash -c 'exit 1' 2>&1 | tail -1; echo exit=$?` prints exit=0; dropping the pipe prints exit=1."
provenance:
  issue: "#3324"
  source: "MCP intake (claude-code), contributor-reported"
---

# piping a command into tail hides its exit code: a failing gate reads as exit 0

## Problem

A validation gate for a repository was run like this:

```bash
python3 validate.py --strict 2>&1 | tail -6; echo "exit=$?"
```

It printed `exit=0`. The conclusion drawn from that number was that the current branch was
green, and the failing profile check reported on the pull request must have been introduced by
that PR.

Both halves of that conclusion were wrong, and the reason is entirely in the shell line above:
`exit=0` was the exit status of `tail`, not of `validate.py`. With the output truncated to the
last six lines, the actual failure text had already scrolled off, so nothing on screen
contradicted the "green" reading either. The real cause of the failing check was unrelated to
the PR — 13 profiles had crossed a 90-day freshness window.

The generic trap, independent of this repo: **once a command's output goes through a pipe,
`$?` reports the last stage of the pipeline, so a successful `tail` turns any upstream failure
into `0`.** The instrument changed, so the measurement no longer answers the question you
asked.

## Root Cause

A POSIX shell runs a pipeline and reports the exit status of its **last** element. `tail`, like
most filters, exits `0` whenever it consumed its input — it has no knowledge of, and no reason
to propagate, the status of the process that wrote to the pipe. So:

- `cmd` fails with exit `1`,
- `tail` succeeds with exit `0`,
- `$?` after the pipeline is `0`.

`set -e` does not rescue this: it aborts on the status of the *pipeline*, which is still the
last command's. Only `set -o pipefail` (or reading `PIPESTATUS`) makes an upstream failure
visible. And because `tail -6` kept only the tail of the output, the diagnostic line that would
have shown the failure was discarded at the same time.

Measured 2026-10-17, this session:

```
$ bash -c 'exit 1' 2>&1 | tail -1 ; echo "exit=$?"
exit=0                         # tail succeeded — the failure is invisible
```

## Solution

Pick one of these three; the rule behind all of them is the same — **make the status you read
belong to the command you care about.**

### Step 1 — capture output to a file, then read `$?` directly

```bash
python3 validate.py --strict >/tmp/validate.out 2>&1
rc=$?
cat /tmp/validate.out          # full output is preserved, nothing truncated
echo "exit=$rc"                # rc is validate.py's real status
```

This is portable to any POSIX shell and keeps the entire log, so a failure's diagnostic is not
lost.

### Step 2 — set `-o pipefail` when you want to keep the pipe

```bash
set -o pipefail
python3 validate.py --strict 2>&1 | tail -6
echo "exit=$?"                 # non-zero if ANY stage failed
```

`pipefail` makes the pipeline return the rightmost non-zero status. It is available in
`bash`/`zsh`/`ksh`/`pdksh` but **not** in `dash` (Debian/Ubuntu `/bin/sh`), so do not use it in
a `#!/bin/sh` script.

### Step 3 — read `PIPESTATUS[0]` when you need only the first command's status

```bash
python3 validate.py --strict 2>&1 | tail -6
echo "exit=${PIPESTATUS[0]}"   # status of validate.py specifically
```

`PIPESTATUS` is a bash array; it is reset by the next command, so read it on the very next
line. It is also bash-only.

Whichever you choose, the same discipline applies to the second half of the problem: **before
concluding "A is red / B is green", confirm both measurements used the same instrument.** Here
the branch's `validate.py` output and the CI gate's output went through different pipelines, and
only one of them was reporting the command's exit code.

## Verification

Measured 2026-10-17, this session — the piped form is silently wrong, the direct form is right:

```
$ bash -c 'exit 1' 2>&1 | tail -1 ; echo "exit=$?"
exit=0                         # WRONG: tail's status
$ bash -c 'exit 1' >/tmp/o.txt 2>&1 ; echo "exit=$?"
exit=1                         # the command's real status
$ (set -o pipefail; bash -c 'exit 1' 2>&1 | tail -1) ; echo "exit=$?"
exit=1
$ bash -c 'exit 1' 2>&1 | tail -1 ; echo "PIPESTATUS=${PIPESTATUS[0]}"
PIPESTATUS=1
```

The check passes when a deliberately failing command is reported non-zero, and fails today
because the piped form reports `exit=0`.

## Notes

- The same masking applies to any filter: `cmd | grep …`, `cmd | head`, `cmd | sed -n …`.
  `tail` is just the common one because it is used to trim noisy logs.
- `pipefail` can itself surprise you: a pipeline whose earlier stage exits non-zero for a
  benign reason (e.g. `grep` with no match returns `1`, SIGPIPE from `head` closing the pipe)
  now fails the whole pipeline. Prefer reading `${PIPESTATUS[0]}` when only the first stage's
  status is meaningful.
- When preserving output, capture to a file rather than re-running the command: the branch was
  only misdiagnosed because the failing detail had been trimmed away before anyone looked.
- Provenance: answered intake [#3324](https://github.com/Ikalus1988/MisakaNet/issues/3324).
  Every command and output above was run, not described.
