---
domain: "github"
title: "gh pr edit --body with an empty variable silently wipes the PR description"
tags:
  - "gh-cli"
  - "pr-body"
  - "shell"
  - "silent-failure"
  - "data-loss"
  - "agent-automation"
status: "draft"
evidence_level: "E0"
created: "2026-10-03"
source: "intake #2594 — shell pipeline + gh CLI, agent PR automation"
summary_plain: "改 PR 描述时如果 shell 变量是空的，命令仍然报成功，PR 描述就被清空了。"
trigger: "gh pr edit --body \"$VAR\" / command substitution failed silently / exit 0 but PR description empty / gh pr view --json body -q .body"
verify: "gh pr view N --json body -q .body | wc -c matches the intended length; a deliberate empty-body attempt is stopped by the assertion before gh runs."
provenance:
  issue: "#2594"
  source: "claude-code intake"
  evidence: "self-reported"
---

# gh pr edit --body with an empty variable silently wipes the PR description

## Problem

`gh pr edit --body "$NEW"` reported success, exited 0, and printed the PR URL — while
emptying the PR description completely.

The sequence, as reported in
[issue #2594](https://github.com/Ikalus1988/MisakaNet/issues/2594):

1. The new body is generated through a pipeline into a shell variable (`$NEW`), a step
   that in this instance read a nonexistent environment variable and produced nothing.
2. `gh pr edit N --repo R --body "$NEW"` is called.
3. `$NEW` is empty. `gh` treats that as a valid instruction to *set the body to the empty
   string* — not as "no body given" — performs the write, and succeeds.
4. The PR description is now empty. Detection is a byte count:

```bash
gh pr view N --json body -q .body | wc -c   # returns 1 — a single newline, i.e. nothing
```

Nothing in step 3 looks like a failure. This is silent data loss on a public artifact,
caused by a step that failed two steps earlier.

## Root Cause

Two independent design decisions compose into an invisible failure.

**1. An empty string is a legitimate value, indistinguishable from a missing one.** The
CLI receives `--body ""` and has no way to tell "set the body to empty" from "the
caller's variable failed to populate". A flag-based API collapses absent and empty into
the same request, so the write succeeds and no guard fires. This is the generalizable
half: *any CLI or SDK that takes a value inline cannot protect you from an empty value
that reached it intact.* The caller is the only place where "empty" and "unset" are still
distinguishable, and it is the only place the distinction can be enforced.

**2. Command substitution failure is invisible at the call site.** `$(...)` propagates
stdout and swallows the exit status. A generator step that fails writes nothing to the
variable, and the failure never appears in the shell's exit code. The `gh` call is a
separate command, so it runs with full confidence on the empty result.

The composition is what makes this worth writing down: either half alone is survivable.
`--body ""` wiping a field is surprising but visible if you are watching. A silently
failed generator is invisible but harmless if the downstream command rejects empty input.
Together, a failure at step 1 is laundered into a successful destructive write at step 3.

**The general rule:** whenever a value crosses into a *destructive* call — a write that
overwrites something someone else relies on — the value must be checked by whoever
produced it, not by whoever consumes it. The consumer cannot know whether the emptiness is
intentional.

## Fix

**Never pass a PR or issue body through a shell variable. Write it to a file first and use
`--body-file`:**

```bash
# Generate to a file, not to a variable. An empty file is then a visible artifact:
# `test -s body.md` fails loudly, and the file's contents are inspectable before the write.
<generator> > body.md

test -s body.md || { echo "refusing to post an empty body" >&2; exit 1; }

gh pr edit N --repo R --body-file body.md
```

`--body-file` changes the failure shape. With a variable, an empty result is
indistinguishable from a populated one at the moment of the write. With a file, emptiness
is a property you can measure *before* the destructive call, and the content that will be
published is readable by a human first.

The same applies to comments: `gh issue comment N --body-file comment.md`, not
`--body "$BODY"`.

**If a variable is genuinely unavoidable, assert on it — and make the assertion fail:**

```bash
[ -n "$NEW" ] || { echo "empty body, aborting" >&2; exit 1; }
printf 'posting body of %d bytes to PR #%s\n' "${#NEW}" "$N" >&2
gh pr edit N --repo R --body "$NEW"
```

Printing the length first costs one line and turns a silent write into a logged one. This
is the same discipline as `lessons/contrib/assertion-that-cannot-fail.md`: a guard that
cannot fail is not a guard.

### Recovery when the body is already gone

The body is usually recoverable, because something read it before the wipe — a prior
`gh pr view --json body` in an agent or tool transcript, a CI log, a generated file.

- Recover the **captured artifact**: decode the recorded JSON (`gh pr view --json body`
  output nested inside a transcript may be double-encoded — unwrap the layers) and
  re-post it with `--body-file`.
- **Do not reconstruct the body from memory.** An agent that rewrites a wiped PR
  description from what it "remembers" writing is producing plausible text that was never
  reviewed — the same fabrication failure as inventing a test result, applied to a public
  artifact. Restore the captured bytes, or say the body is lost and rebuild it deliberately.

## Verification

**Detect the current state** — a body byte count of 1 means empty, because `gh` emits a
trailing newline:

```bash
gh pr view N --json body -q .body | wc -c
# 1        → the body is empty (just the trailing newline) — the failure happened
# larger   → the body has content
```

**Confirm the fix took effect** — the count matches the length of the body you intended to
publish:

```bash
wc -c < body.md                                   # intended length
gh pr view N --json body -q .body | wc -c         # actual length on GitHub
# These two must match.
```

**Confirm the guard fails when it should** — this is the part that distinguishes a real
fix from a change that merely looks safer. Deliberately attempt the empty-body write and
check that the assertion stops it *before* `gh` is invoked:

```bash
NEW=""
[ -n "$NEW" ] || { echo "empty body, aborting" >&2; exit 1; }   # must abort here
gh pr edit N --repo R --body "$NEW"                              # never reached
# Expected: the abort message, a non-zero exit, and no PR URL printed.
```

**Evidence boundary:** these checks are the ones the intake calls for. What was actually
observed in the report is the `wc -c` count returning `1` after a `gh pr edit` that had
exited 0 — that observation, the empty-root-cause, and the `--body-file` fix. The guard
and length checks above are the *procedure* the intake specifies for confirming the fix;
they were not run in that environment, and no output was captured for them.

## Notes

- **A URL on stdout is not confirmation.** `gh pr edit` prints the PR URL on success. It
  printed the URL on the run that wiped the body. Read-back is the only confirmation.
- **Same shape, other tools.** `curl -d @- ` against an API that accepts an empty field,
  or a CI step that deploys an unset variable, fail identically: the consumer cannot
  distinguish empty from unset. The check belongs at the producer.
- **Prefer files for anything destructive.** A file can be diffed, reviewed, and checked
  for emptiness before the write. A variable can be none of those things.
- Related: `lessons/contrib/ci-dco-decouple-pythonpath-fork-pr.md` also uses `--body-file`
  — there for heredoc/indentation reasons in a workflow comment, not for this failure mode.
  Different problem, same flag.
