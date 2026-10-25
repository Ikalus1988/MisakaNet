---
title: "DSH Windows job runner exits 1 because the profile dependency closure is incomplete"
domain: "dsh"
tags:
  - "dsh"
  - "windows"
  - "subprocess"
  - "job-object"
  - "pnpm"
  - "dependency-resolution"
  - "profile"
  - "ripgrep"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "DSH 在 Windows 上派生子进程全部失败，不是 Job Object 或权限问题，而是 profile 的依赖没装齐。"
trigger: "Windows Job runner exited with exit code 1 before proving its managed range empty"
verify: "pwsh -c Write-Output alive returns text instead of the Job runner error, and importing <profile>/node_modules/@deepseek-ai/dsh-subprocess-local/lib/runner.js prints RUNNER OK"
source: "intake-3156"
provenance:
  issue: "#3156"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# DSH Windows job runner exits 1 because the profile dependency closure is incomplete

## Problem

On Windows the DSH (DeepSeek Harness) engine started normally and the GUI opened, but
**every child process the engine spawned failed**. The smallest possible probe failed
the same way as everything else:

```text
pwsh -c "Write-Output alive"
  -> subprocess-local: Windows Job runner exited with exit code 1
     before proving its managed range empty
```

At the same time the built-in `grep`/`glob` tools reported a ripgrep provider failure,
and the plugin-marketplace page could not fetch its data.

The error text names the Job runner and nothing else, so it reads like a Windows Job
Object, permission, native-module or antivirus problem. A host-side probe (opening a
URL with the host browser tool) worked, which already argued against permissions.

The decisive counter-evidence came from importing the runner module directly out of
the profile tree: loading `lib/runner-launch-*.js` failed on its first line with
`ERR_MODULE_NOT_FOUND` for `@deepseek-ai/dsh-subprocess`, i.e. Node exited 1 before
the runner produced any result. The runner's own failure paths exit with code **127**,
so `exit code 1` is the module-loader's exit code, not the runner's.

## Root Cause

The profile's dependency closure was incomplete: the core family
(`@deepseek-ai/dsh-agent`, `dsh-fs-local`, `dsh-sandbox-local`, `dsh-pwsh-sandbox`,
`dsh-session`, `dsh-credentials-local`, `dsh-tool-fs`, …) was not resolved into the
profile tree, so the seam packages the engine actually imports
(`@deepseek-ai/dsh-subprocess`, `@deepseek-ai/dsh-http-proxy`) were absent. The
profile held 36 `@deepseek-ai/*` packages against the 228 the running engine expects.

Two properties of the failure made it expensive to diagnose:

1. **`pnpm.overrides` cannot repair a missing dependency.** Overrides rewrite the
   version of an edge that already exists; they do not add an edge. With only
   overrides in place the install is a no-op and the missing peer is never installed —
   the missing bundle roots must be *declared as dependencies* so the closure grows.
2. **The runner's stderr is discarded.** `runnerStdio()` sets the runner process's
   fds 0/1/2 to `ignore`, so the `ERR_MODULE_NOT_FOUND` that actually explains the
   failure never reaches the parent or any log; the parent only reports the
   content-free "Job runner exited with exit code 1" line.

Four wrong lines of investigation were ruled out by evidence before the real one was
found:

| Hypothesis | Evidence against it |
|---|---|
| ARM64 Node running x64 koffi | `arch=x64`, `nodeVersion=v22.22.2`, and the `node-pty` / `koffi` `win32-x64` artifacts were present |
| koffi native file missing | `@koromix/koffi-win32-x64/win32_x64/koffi.node` was in the tree |
| permissions / sandbox / antivirus | host-side browser tools could spawn processes, and `probeWindowsJob()` returned `true` (a false result would only warn, it would not fail the spawn) |
| backend version broken by an update | the backend stayed at `0.2.0-rc.2` throughout |

## Solution

### Step 1 — Read the version table from the engine, not from guesswork

The truth source is the engine's own installed tree:
`%LOCALAPPDATA%\dsh-desktop\backend\node_modules\@deepseek-ai`. There,
`@deepseek-ai/dsh-base@0.2.0-rc.2` pins the whole core family by exact version in its
own `dependencies`, so the running engine defines the target versions.

### Step 2 — Declare the missing bundle roots in the profile

In the profile's `package.json` (for example `%USERPROFILE%\.dsh\profiles\web\package.json`,
referred to below as `<profile>/package.json`), add to `dependencies`:

- `@deepseek-ai/dsh-base` and `@deepseek-ai/dsh-web-app` at the engine's exact version,
- the two seams the engine imports: `@deepseek-ai/dsh-subprocess` and
  `@deepseek-ai/dsh-http-proxy`.

Declaring the roots is what makes pnpm resolve the closure; adding only `overrides`
does not.

### Step 3 — Pin everything in `pnpm.overrides` as well

Add `pnpm.overrides` mapping every `@deepseek-ai/*` to the engine version, so an alpha
cannot slip back in through a transitive range.

### Step 4 — Run the install (two execution details matter)

- Node ≥ 20.12 refuses to `spawn` a `.cmd`/`.bat` with `shell: false` (EINVAL), so run
  the pnpm entry point through the current Node binary directly:
  `node <profile>\node_modules\pnpm\bin\pnpm.cjs install` (the reporter's layout was
  `…\pnpm\node_modules\pnpm\bin\pnpm.cjs`).
- A mirror can lag behind npm, so on failure retry once with the public registry:
  `--registry https://registry.npmjs.org/`.

### Step 5 — Verify the seams, then clear the exemptions

Check the resolved version of all five seam packages (`dsh-base`, `dsh-web-app`,
`dsh-subprocess`, `dsh-http-proxy`, `dsh-subprocess-local`) and only after they all
match the runtime version reset `compatibility.json` to `{}`. Those exact-version
exemptions are what let a half-installed tree past the version guard in the first
place.

### Step 6 — Back up before `--apply`

Copy `package.json`, `pnpm-lock.yaml` and `compatibility.json` to `*.bak-<timestamp>`
first, so the whole operation is reversible.

Result reported: `@deepseek-ai/*` went from 36 to 228 packages, all at `0.2.0-rc.2`;
`pwsh`, `glob` and `grep` recovered immediately and the startup log had no warnings.

Do **not** do what was tried and rejected first: hand-writing a forwarding shim
package into the profile so the import resolves. A hand-made package impersonates an
official scope, shadows the core seam that is actually serving, and is irreversible in
a pnpm tree — the missing package family includes `cordis`, so a shim can create a
second `cordis` instance.

## Verification

1. `pwsh -c "Write-Output shell-alive"` returns text instead of the Job runner error.
2. Import-closure self-check — should print `RUNNER OK` plus the exported keys (this is
   the exact point that exited 1 before the fix):

   ```powershell
   & "<engine-node>" -e "import('file:///<profile>/node_modules/@deepseek-ai/dsh-subprocess-local/lib/runner.js').then(m=>console.log('RUNNER OK',Object.keys(m)),e=>console.log('FAIL',e.message))"
   ```

3. The tail of `%LOCALAPPDATA%\dsh-desktop\logs\desktop.log` holds only the
   `dsh web: http://…` line — no `did not activate`, no `disabling profile plugin row`,
   no `startup failed`.
4. Profile-side count goes from 36 to ~228:
   `(Get-ChildItem "$env:USERPROFILE\.dsh\profiles\web\node_modules\@deepseek-ai" -Directory).Count`,
   and `dsh-base` / `dsh-web-app` / `dsh-subprocess` / `dsh-http-proxy` /
   `dsh-subprocess-local` all report the runtime version.
5. GUI → Settings → Plugin Marketplace renders; `dshmarket`'s `/dsh-market/installed`
   returns 401 rather than 404, i.e. the route is mounted.

Boundary of the diagnosis: if check 2 still fails, the closure is still incomplete —
add the module name the error prints and do not go back to koffi, architecture or
permission theories.

## Notes

- The reported `exit code 1` is Node's module-loader exit status; the runner's own
  failure paths use 127. That difference is the cheapest way to tell "died before
  producing anything" from "the runner itself refused".
- Reproducing the swallowed stderr requires either importing the runner directly (as
  in check 2) or reading the code path that sets fds to `ignore`; the parent process
  will never show it.
- The exact Windows build, backend build 0.2.0-rc.2 date and antivirus product were not
  given by the reporter — 报料者未给出，需复现确认.
- Related: `lessons/contrib/dsh-required-plugin-missing-tools-service-hoisted-core-lib.md`
  (a core library shadowed by a plugin's own dependency) and
  `lessons/contrib/dsh-plugin-install-github-codeload-timeout.md`.
