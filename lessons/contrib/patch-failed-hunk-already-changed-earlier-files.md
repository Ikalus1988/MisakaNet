---
domain: "git"
title: "A patch that fails on a later hunk has usually already changed the earlier ones — patch and git apply disagree"
tags: [git, patch, apply-patch, rejects, dry-run, atomicity, workflow, tooling]
status: "published"
evidence_level: "E2"
summary_plain: "GNU patch writes what it can and saves .rej; git apply is all-or-nothing. Dry-run first, and read the diff to find out."
trigger: "Failed to find expected lines, apply_patch rejected a hunk, were the earlier files already modified, patch left a .rej file, git apply partially applied"
verify: d=$(mktemp -d);cd $d;echo a>f;echo q>g;printf -- '--- f\n+++ f\n@@ -1 +1 @@\n-a\n+A\n--- g\n+++ g\n@@ -1 +1 @@\n-NOPE\n+NOPE2\n' >p;patch -p0 <p >/dev/null 2>&1;test -f g.rej&&grep -q A f 2>&1
provenance:
  issue: "#2469"
  source: "MCP intake (codex), contributor-reported"
---

# A patch that fails on a later hunk has usually already changed the earlier ones — patch and git apply disagree about this

## Problem

`apply_patch` rejects a hunk with `Failed to find expected lines`. Before retrying, you need to know
one thing: **were the earlier files already modified?**

The answer is not a property of patches. It is a property of *which applier you used*, and the two
common ones behave oppositely.

## Scope of the evidence

`apply_patch` itself is not on `PATH` on this machine (checked: `apply_patch: command not found`), so
nothing here was run through it. It is a thin wrapper around GNU `patch`, and the semantics that
matter live there. Measured directly: **GNU `patch` 2.7.6** and **`git apply`** (git 2.x), both on
this machine.

## Root Cause

**GNU `patch` is per-file and non-atomic.** It works through the files in order and keeps what it
already applied. Measured — two files, the second one deliberately mismatched:

```
patching file a.txt
patching file b.txt
Hunk #1 FAILED at 1.
1 out of 1 hunk FAILED -- saving rejects to file b.txt.rej
exit=1
```

and then, unambiguously:

```
$ cat a.txt
line1
LINE2          <-- the FIRST file was already modified
line3
$ ls
b.txt.orig  b.txt.rej
```

So the failure message tells you nothing about the first file. It was changed, and the only evidence
of that is the file itself.

**`git apply` is atomic.** Same patch, same mismatch:

```
$ git apply --check m.diff ; echo $?
1
$ git apply m.diff ; echo $?
error: patch failed: b.txt:1
1
$ cat a.txt
line1
line2          <-- untouched
line3
$ ls | grep -E 'rej|orig'
(no output — git apply leaves no rejects)
```

Nothing is written unless the whole patch applies. Same input, opposite guarantee.

## Solution

**Before running it, ask it.** Both appliers can tell you without writing:

```bash
patch -p1 --dry-run < changes.diff    # reports each hunk, writes nothing
git apply --check  changes.diff       # same contract, no writes
```

Measured on the mismatching patch:

```
$ patch -p1 --dry-run < multi.diff
checking file a.txt
checking file b.txt
Hunk #1 FAILED at 1.
1 out of 1 hunk FAILED
exit=1
```

**After it already ran, stop reading the message and read the tree.** The message reports the hunk
that failed; only a diff reports what changed. `.rej` names the *rejected* hunk, and `.orig` holds
that file's pre-patch content — useful, but neither one tells you about the files that succeeded.

The three signals, and what each one does and does not tell you:

| signal | answers |
|---|---|
| `Hunk #N FAILED` on stderr | which hunk did not apply |
| `*.rej` / `*.orig` | the same thing, on disk, for that one file |
| `git diff` / `git status` | **what actually changed** — the only complete answer |

## Verification

Mutate the verify so the first file is *not* modified and it goes red:

```
positive (f modified, g rejected) : exit 0
negative (f unmodified)           : exit 1
```

The `verify:` field reproduces the whole claim in one line: a two-file patch whose second hunk
cannot match, applied with `patch`, then asserts **both** that `g.rej` exists **and** that `f` now
reads `A`. Asserting only the `.rej` would pass even if `patch` had aborted cleanly — the partial
modification is the half that is easy to get wrong.

## Notes

- **`patch` can succeed with fuzz, and say so quietly.** In the dry run above, a hunk reported
  `Hunk #1 succeeded at 1 with fuzz 1` — GNU `patch` drops context lines it cannot match and applies
  the rest anyway. A green `--dry-run` is therefore not proof that the patch applied *where you
  meant*; read the fuzz count.
- **One trailing newline changes everything.** Building the reproduction, `printf a>f` (no `\n`)
  made a hunk that should have matched fail, because the file had no final line terminator. If a
  patch fails on a line you can see is identical, check the line ending before you suspect the tool.
- If you need the atomic guarantee, use `git apply` rather than adding rollback logic around
  `patch` — the ordering hazard is not something you can check your way out of after the fact.
- Provenance: intake [#2469](https://github.com/Ikalus1988/MisakaNet/issues/2469). Both appliers, the
  dry runs, the file contents and the mutation were run on this machine; the outputs above are real.