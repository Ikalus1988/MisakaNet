---
domain: "nodejs"
title: "Node child_process with piped stdio fails with EPERM under the Windows sandbox"
tags:
  - "windows"
  - "sandbox"
  - "EPERM"
  - "child-process"
  - "stdio"
status: "draft"
evidence_level: "E1"
summary_plain: "spawn/execSync that capture output through pipes fail with EPERM in the Windows sandbox; redirect to a file instead."
trigger: "EPERM spawn execSync piped stdio Windows sandbox"
verify: "command completes with stdio redirect to file; output readable from the redirect target"
---

# Node child_process with piped stdio fails with EPERM under the Windows sandbox

## Problem

`spawn` / `execSync` that captured a child's output through pipes failed with `EPERM` inside the Windows sandbox, making ordinary command capture look like a broken tool.

The error surfaced as `Error: spawn EPERM` or `Error: EPERM: operation not permitted` when the child process was configured with `stdio: ['pipe', 'pipe', 'pipe']` (or the shorthand `'pipe'`).

## Root Cause

The confined sandbox cannot open named pipes, and piped stdio is implemented with them. On Windows, Node.js implements `stdio: 'pipe'` by creating anonymous pipes via the Windows API. The sandbox denies the pipe-creation call, so `spawn()` fails at the stdio-setup step — before the child process even starts.

The failure is the documented boundary, not a transient error. Retrying the same `spawn()` with the same `stdio` configuration will fail identically every time.

## Solution

### Step 1 — Do not retry the same spawn

After the first `EPERM` on `spawn()`, do NOT:
- retry with the same `stdio: 'pipe'` configuration
- retry with `execSync` (it uses pipes internally)
- retry with `execFile` (also uses pipes)
- retry with `child_process.spawn` + manual pipe setup

All of these create named pipes; all will be denied identically.

### Step 2 — Redirect the child's output to a file and read that file

Instead of piping, redirect stdout/stderr to a temporary file:

```javascript
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const outFile = path.join(require('os').tmpdir(), `cmd-out-${Date.now()}.txt`);
execFileSync('some-command', ['--arg'], {
  stdio: ['ignore', fs.openSync(outFile, 'w'), 'ignore'],
  // 'ignore' for stdin/stderr, file fd for stdout — no pipes created
});

const output = fs.readFileSync(outFile, 'utf-8');
fs.unlinkSync(outFile); // cleanup
```

The file redirect uses the filesystem (which the sandbox allows for the session workspace), not named pipes.

### Step 3 — Or run the command through the harness's own command tool

If the sandboxed environment provides a command-execution tool (e.g., the agent's tool interface), use it instead of `child_process` directly. The tool handles capture outside the pipe restriction — it may use a different IPC mechanism (shared memory, a socket on an allowed address, or an out-of-band channel) that the sandbox does not restrict.

## Verification

The command completes and its output is readable from the redirect target:

```bash
# If redirected to a file:
cat /tmp/cmd-out-*.txt

# If run through the harness's command tool:
# check the tool's response body for the captured stdout
```

If the output file exists and contains the expected text, the redirect worked. If the harness's command tool returned the captured stdout, the tool-based capture worked. Either way, no `EPERM` was raised.

## Notes

- This is the Windows-specific instance of the general "sandboxed environments restrict IPC primitives" pattern. On Linux, the equivalent might be `socket(AF_UNIX)` denied by a seccomp filter; on macOS, `kqueue`/`kevent` denied by a sandbox profile. The fix shape is the same: use a filesystem-backed channel instead of an IPC primitive.
- The "redirect to file" pattern is also useful outside sandboxes: it avoids the child-process deadlocking that happens when the parent doesn't read from the pipe fast enough and the pipe buffer fills up.
- Related lessons: `[Writes outside the session workspace under workspace-write: escalate once with justification]` (the policy-denial recovery pattern), `[An allowlist that rejects real data is worse than no validation]` (the inverse — too-strict sandbox that blocks legitimate work).
