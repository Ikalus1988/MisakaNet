---
title: 'Windows CI: splitCommand backslash stripping, UnicodeEncodeError, and detached
  process failure'
domain: devops
evidence_level: E1
tags:
- windows
- ci
- nodejs
- python
- subprocess
- encoding
- backslash
- detached
status: published
created: '2026-08-23'
source: issue-1223

provenance:
  source: "external"
  contributor: "issue-1223"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Three distinct bugs surfaced in a single Windows CI session:

1. `splitCommand()` strips backslashes from Windows paths — `C:\hostedtoolcache` becomes `C:hostedtoolcache`, causing ENOENT.
2. Python subprocess with non-ASCII output (Chinese characters) fails with `UnicodeEncodeError` on Windows `cp1252` default encoding.
3. `detached: true` + `unref()` on Windows does not survive `process.exit()` — fire-and-forget child processes are killed when the parent exits.

## Root Cause

### Bug 1: splitCommand() backslash stripping

The `!isWindows` guard that prevents backslash stripping was lost during a rebase/squash. Without this guard, the command parser treats `\` as an escape character on all platforms, destroying Windows drive-letter and directory paths.

### Bug 2: Python subprocess UnicodeEncodeError

Windows defaults to `cp1252` (or the system locale codepage) for process stdout/stderr. When a Python subprocess emits Chinese characters or other non-ASCII output, the encoding fails because `cp1252` cannot represent those codepoints. Linux and macOS default to UTF-8, so this only manifests on Windows.

### Bug 3: detached process killed by parent exit

On Windows, `detached: true` with `unref()` creates a new process group, but `process.exit()` terminates the entire process tree including detached children. This differs from Unix where `unref()` truly decouples the child's lifetime from the parent. Windows requires synchronous spawning for fire-and-forget patterns.

## Solution

### Fix 1: Restore the isWindows guard in splitCommand

```javascript
function splitCommand(cmd) {
  // On Windows, do NOT strip backslashes — they are path separators
  if (process.platform === 'win32') {
    return cmd.split(/\s+/);
  }
  // On Unix, strip escape backslashes
  return cmd.replace(/\\(\s)/g, '$1').split(/\s+/);
}
```

### Fix 2: Set PYTHONIOENCODING for subprocess calls

```javascript
const { spawn } = require('child_process');

const child = spawn('python', ['script.py'], {
  env: {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
  },
});
```

Alternatively, set `PYTHONIOENCODING=utf-8` in the CI workflow environment:

```yaml
env:
  PYTHONIOENCODING: utf-8
```

### Fix 3: Use spawnSync for fire-and-forget children on Windows

```javascript
// Instead of detached + unref (does not survive process.exit on Windows):
const { spawnSync } = require('child_process');

// Blocking but reliable — child completes before parent exits
spawnSync('node', ['worker.js'], {
  stdio: 'ignore',
  detached: false,
});

// Or, if you truly need async: keep parent alive until child exits
const child = spawn('node', ['worker.js'], {
  detached: true,
  stdio: 'ignore',
});
child.unref();

// Ensure parent does not exit before child on Windows
process.on('beforeExit', () => {
  // Give detached child time to detach properly
});
```

For CI fire-and-forget scenarios, `spawnSync` is the most reliable cross-platform approach. The process completes synchronously, so there is no parent-exit race.

## Key Points

1. **Rebase/squash can silently drop platform guards.** Always verify `process.platform` conditionals survive merge operations.
2. **Windows encoding defaults differ from Unix.** `PYTHONIOENCODING=utf-8` or `encoding: 'utf-8'` on spawn options is mandatory for non-ASCII output.
3. **`detached: true` + `unref()` is not truly fire-and-forget on Windows.** Use `spawnSync` for cross-platform reliability, or keep the parent alive until the child confirms detachment.
4. **Test CI changes on Windows runners.** These three bugs only manifest on Windows; Linux/macOS CI passes would not catch them.


## Verification

```bash
python3 --version
python3 -c 'import sys; print(sys.version)'
```

**Expected Output:**
```
Python 3.
3.
```