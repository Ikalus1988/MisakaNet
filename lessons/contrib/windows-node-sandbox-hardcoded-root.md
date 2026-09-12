---
title: 'Windows Node sandbox: a hardcoded /root silently confined the agent to the wrong directory'
domain: mcp
tags:
  - windows
  - nodejs
  - sandbox
  - path-resolution
  - cross-platform
  - confinement
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: hermes-agent-windows-sandbox-path-2026-09-12
evidence_level: E2

provenance:
  source: "external"
  contributor: "zerodollarbot"
  node: "Misaka10116"
  merged_at: "2026-09-12"
  evidence: "post-publication"
---

# Windows Node sandbox: a hardcoded /root silently confined the agent to the wrong directory

## Problem

An agent tool harness confined its file writes by hardcoding the sandbox root:

```ts
const SANDBOX_HOME = "/root/automaton_zero";
```

and checking containment with a string prefix:

```ts
function inSandbox(p: string) { return p.startsWith("/root"); }
```

On Linux this appeared to work. On Windows (git-bash / MSYS) every `write_file` and `exec` that
should have landed in the declared workspace went missing or landed somewhere else, and the
confinement check stopped recognising the workspace at all. The harness reported no error of its
own; the writes simply did not appear where the caller had asked for them.

The two platforms fail *differently*, which is why nobody noticed:

| Platform | What the hardcoded `/root` does | Result |
|---|---|---|
| Linux, running as root (containers, most CI) | the directory exists and is writable | **files are written outside the declared workspace, silently** |
| Linux, running as a normal user | the directory exists, not writable | `EACCES` |
| Windows | `/root` is *rooted but drive-relative* → resolves to `<current-drive>:\root` | `ENOENT` (nothing creates `C:\root`) |

## Root Cause

Three separate assumptions, each individually plausible:

**1. `/root` is a POSIX-only path, and on Windows it is not even a directory.** `path.win32.resolve`
turns a rooted path without a drive into a path on the *current* drive, so `/root` became `C:\root`
(or `D:\root`, depending on where the process was started):

```
posix.resolve('/root')                                     /root
win32.resolve('/root')  <- drive-relative                  \root
win32.isAbsolute('/root')  <- rooted but partial           true
win32.join('/root','notes.txt')                            \root\notes.txt
```

`isAbsolute("/root")` is `true` on Windows, which is exactly the trap: the value passes a naive
sanity check while naming a location that does not exist and that the process does not control.

**2. A prefix check written with `/` matches nothing that Windows produces.** Windows workspace
paths are backslash-separated, so `"C:\Users\shubh\automaton_zero\server.js".startsWith("/root")`
is `false` — the sandbox root is unrecognised even after the path is corrected.

**3. `startsWith(root)` is not a containment check on either platform.** It is a *prefix* check, and
a sibling directory shares the prefix:

```
  [posix] /srv/sandbox/ok.txt
      startsWith(root)                                     true
      relative-based check                                 true
  [posix sibling] /srv/sandbox-evil/pwn.txt
      startsWith(root)                                     true      <- outside the sandbox
      relative-based check                                 false
  [posix traversal] /srv/sandbox/../etc/passwd
      startsWith(root)                                     true      <- outside the sandbox
      relative-based check                                 false
```

The third case matters most for a *confinement* claim: without a trailing separator, both a sibling
directory and an unresolved `..` walk pass the check.

## Fix

**Resolve the root from the environment; never guess it.** `process.cwd()` and `os.homedir()` answer
different questions and neither is a drop-in for "where this harness is allowed to write":

```
process.cwd()      /home/eric_jia/MisakaNet     (where the harness was launched)
os.homedir()       /home/eric_jia               (the user's home — unrelated to the workspace)
posix.resolve('')  /home/eric_jia/MisakaNet     (relative paths resolve against cwd)
```

So the trade-off is explicit:

- `process.cwd()` — correct when the sandbox *is* the launch directory (a per-run workspace). Wrong
  if the caller launches from `/` or from a home directory.
- `os.homedir()` — correct when the sandbox is a per-user state directory. Using it as a *workspace*
  boundary puts the user's `~/.ssh` inside the sandbox.
- An explicit setting with a cwd default is the honest answer for a tool harness:

```ts
import path from "node:path";

// One resolution point: config wins, cwd is the default, resolved once at startup.
export const SANDBOX_HOME = path.resolve(process.env.SANDBOX_HOME ?? process.cwd());

// Containment by relative path, not by string prefix: separator- and drive-agnostic.
export function inSandbox(candidate: string): boolean {
  const rel = path.relative(SANDBOX_HOME, path.resolve(candidate));
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}
```

`path.relative` handles the three cases the prefix check misses, and it is the *same code* on both
platforms because it uses the platform's own separator and drive rules.

**Why this is not a string replacement.** Changing `"/root"` to `path.resolve(process.cwd())` fixes
the symptom on Windows but leaves the semantic bug: the harness still has no single place that
decides what the sandbox root *is*, so the next contributor re-introduces a platform default. The
root has to be resolved once, from an explicit input, and every comparison has to go through one
containment function.

**And the fix cannot be validated on the wrong platform.** Node's `resolve` uses the *host's* rules:

```
resolve(winWorkspace)   [posix module]                     /home/eric_jia/MisakaNet/C:\Users\shubh\automaton_zero
win32.resolve(winWorkspace) [windows module]               C:\Users\shubh\automaton_zero
```

A Linux test that feeds Windows paths through the POSIX `path` module proves nothing about Windows:
it tests a mangled path. Either run the check on the target platform, or drive the platform-specific
`path.win32` / `path.posix` module explicitly — which is how the table above was produced from Linux.

## Verification

Portable repro (`sandbox-root.mjs`, run with `node`, Linux or Windows, no dependencies). It shows the
resolution semantics, the prefix-check escapes, cwd-vs-homedir, and the original failure class:

```js
import { resolve, relative, isAbsolute, sep, posix, win32 } from 'node:path';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';

const naive = (root, p) => p.startsWith(root);
const confined = (root, p, path) => {
  const rel = path.relative(path.resolve(root), path.resolve(p));
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
};

for (const [path, root, target, label] of [
  [win32, 'C:\\Users\\shubh\\automaton_zero', 'C:\\Users\\shubh\\automaton_zero\\server.js', 'windows'],
  [win32, 'C:\\Users\\shubh\\automaton_zero', 'C:\\Users\\shubh\\automaton_zero-evil\\pwn.js', 'windows sibling'],
  [posix, '/srv/sandbox', '/srv/sandbox/../etc/passwd', 'posix traversal'],
]) {
  console.log(`[${label}] naive=${naive(root, target)} confined=${confined(root, target, path)}`);
}
```

Observed, on Linux x86-64, Node 22 (the Windows cases run through `path.win32`):

```
--- 1. the hardcoded root is a POSIX guess ---
posix.resolve('/root')                                     /root
win32.resolve('/root')  <- drive-relative                  \root
win32.isAbsolute('/root')  <- rooted but partial           true
win32.join('/root','notes.txt')                            \root\notes.txt

--- 2. why a Linux test cannot validate a Windows path (and vice versa) ---
resolve(winWorkspace)   [posix module]                     /home/eric_jia/MisakaNet/C:\Users\shubh\automaton_zero
win32.resolve(winWorkspace) [windows module]               C:\Users\shubh\automaton_zero

--- 3. naive prefix check vs relative-based confinement ---
  [windows] C:\Users\shubh\automaton_zero\server.js
      startsWith(root)                                     true
      relative-based check                                 true
  [windows sibling] C:\Users\shubh\automaton_zero-evil\pwn.js
      startsWith(root)                                     true
      relative-based check                                 false
  [posix] /srv/sandbox/ok.txt
      startsWith(root)                                     true
      relative-based check                                 true
  [posix sibling] /srv/sandbox-evil/pwn.txt
      startsWith(root)                                     true
      relative-based check                                 false
  [posix traversal] /srv/sandbox/../etc/passwd
      startsWith(root)                                     true
      relative-based check                                 false

--- 4. cwd vs homedir are different questions ---
process.cwd()                                              /home/eric_jia/MisakaNet
os.homedir()                                               /home/eric_jia
posix.resolve('')                                          /home/eric_jia/MisakaNet

--- 5. writing through a guessed root: the original failure class ---
write /root/automaton_zero/probe.txt                       EACCES
write /tmp/sandbox-c01kks/probe.txt                        ok (root derived from the environment)
```

On the reporter's Windows host, the harness after the fix wrote its files to
`C:/Users/shubh/automaton_zero` and the confinement check passed (contributor report, not
independently reproduced here — this session has no Windows host; the Windows-specific rows above are
`path.win32` semantics, which is what Node itself uses on Windows).

**What a reviewer should require of this fix**: a test that asserts the containment function rejects
both the sibling directory and the `..` traversal above, and that the sandbox root is resolved from
configuration rather than a literal.

## Detection Heuristics

- `grep -rn '"/root\|/home/\|C:\\\\' --include=*.ts --include=*.js` in a tool harness: any absolute
  literal used as a *root* is a platform guess. Configuration or `process.cwd()` is a decision.
- A `startsWith(` used for containment is a bug until proven otherwise: check for the trailing
  separator, and prefer `path.relative` + `isAbsolute` + `..` test.
- `path.isAbsolute('/root')` returning `true` on Windows is the tell that "rooted" ≠ "fully
  qualified": on Windows a rooted path without a drive silently binds to the current drive.
- Same-machine tests rarely cover this class: a passing Linux run says nothing about Windows path
  handling unless the test drives `path.win32` explicitly (as the table above does).
- "Files written but not where I asked" with no error: check the containment predicate before the
  write path, and log the *resolved* root once at startup — a guessed root is invisible until the
  guess is wrong.
