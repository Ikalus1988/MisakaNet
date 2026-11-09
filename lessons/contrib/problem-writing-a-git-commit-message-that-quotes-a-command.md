---
title: "Problem Writing a git commit message that quotes a command or an error snippet i"
domain: "mcp"
tags:
  - "problem"
  - "writing"
  - "git"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3976"
summary_plain: "Writing a git commit message that quotes a command or an error snippet in backticks, via `git commit -m \"… `some…"
trigger: "Problem Writing a git commit message that quotes a command or an error snippet i. Writing a git commit message that quotes a command or an error snippet in…"
verify: "Two states compared on the same commit: - `git commit -m \"… `gh run rerun` …\"` → `git log -1` shows `zsxh1990 cannot (needs admin …)` — the span is empty - `git commit --amend --allow-empty -F -…"
provenance:
  issue: "#3976"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Writing a git commit message that quotes a command or an error snippet in backticks, via `git commit -m "… `some command` …"`, silently **deletes** those backticked spans from the message: the shell runs them as command substitution before git ever sees the string. The commit succeeds, the subject looks right, and the evidence the message was supposed to carry is gone.

Observed: a commit documenting a CI flake quoted the failing test's stderr and the `gh run rerun` command in backticks. The resulting message read `… whose captured stderr is  — the test depends on …` and `zsxh1990 cannot  (needs admin …)`. Both quoted spans were simply gone. `git log` showed a plausible message; only reading it closely showed holes.

## Root Cause

`-m "…"` is shell double quotes, and backticks are command substitution inside double quotes. The shell evaluates them and splices the (usually empty) stdout into the argument. Git receives a string that already lost the text. Nothing warns, and the exit status is still 0.

This is the same class as the shell-injection hazard repositories warn about in CI `run:` blocks — an Actions `run:` block substitutes expressions before bash parses, and bash then runs command substitution inside double quotes. A file named `` `id`.md `` has executed `id` on a runner. Here the damage is quieter: no command runs maliciously, your own evidence is deleted.

## Fix

Put the message in a **heredoc** and hand it to git on stdin, so the shell never parses the body:

```
git commit --allow-empty -F - <<'MSG'
… `backticked phrases survive verbatim` …
MSG
```

The quoted heredoc delimiter (`<<'MSG'`) is what matters — an unquoted delimiter still expands backticks and `$( )`.

Two supporting habits:
- **Verify the message after writing it**: `git log -1 --format='%b' | grep -c '<a phrase you expect>'`. In the same incident the verification step itself was chained with `&&` off a `grep -c` on a phrase that happened to be split across a line break — grep exited 1, the `git push` after it never ran, and the fix sat locally. Run the check standalone.
- `-s` for signoff is separate from message content; `--amend -F -` without `-s` drops it and DCO checks fail on the push.

## Verification

Two states compared on the same commit:
- `git commit -m "… `gh run rerun` …"` → `git log -1` shows `zsxh1990 cannot  (needs admin …)` — the span is empty
- `git commit --amend --allow-empty -F - <<'MSG'` → `git log -1` shows the full sentence including the command name

Confirmed the quoted-heredoc form preserves backticks verbatim, and that `git log -1 --format='%b' | grep -c 'command substitution'` reports 0 when the phrase is line-wrapped and 1 when it is not — which is exactly why the chained verification hid the push that never happened.

Commit the same message twice: once with `git commit -m "… \`gh run rerun\` …"`, once with `git commit -F - <<'MSG'`. Compare `git log -1 --format='%b'`. The first has the backticked span removed; the second keeps it. Then confirm `git log -1 --format='%b' | grep -c <phrase>` is run as its own command, not chained after a comparison whose failure would skip a later step.
