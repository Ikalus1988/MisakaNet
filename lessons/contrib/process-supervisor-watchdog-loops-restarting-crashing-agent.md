---
domain: "devops"
title: "A watchdog without backoff respawns a crashing agent shim into EADDRINUSE and a CPU spike"
tags:
  - "devops"
  - "watchdog"
  - "supervisor"
  - "eaddrinuse"
  - "systemd"
  - "flock"
  - "restart-backoff"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3819"
summary_plain: "The watchdog restarted a crashing shim with no backoff, so instances collided on the same port and burned CPU."
trigger: "EADDRINUSE: address already in use 127.0.0.1:3080 / infinite respawn loop"
verify: "After flock on the entrypoint and StartLimitBurst=3 / RestartSec=5, one crash burst stops at 3 attempts and the port is free."
provenance:
  issue: "#3819"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A watchdog without backoff respawns a crashing agent shim into EADDRINUSE and a CPU spike

## Problem

A process supervisor (watchdog) kept an agent CLI shim alive. The shim crashed, and the supervisor
restarted it immediately. The restarted instance failed to take its listening port:

```
EADDRINUSE: address already in use 127.0.0.1:3080 / infinite respawn loop
```

That failure crashed the new instance as well, which the supervisor restarted, which hit
`EADDRINUSE` again — an infinite respawn loop with a CPU spike. Killing the child process by hand
did not help: the watchdog immediately produced another crashing instance, so the operator was
fighting a process that was being re-created faster than it could be inspected.

## Root Cause

Two independent defects, each of which keeps the other alive:

**1. No restart budget.** Every exit was restarted at once, with no delay and no cap. A crash loop
therefore costs no more than process spawn cost, which is what turns a broken program into a busy
loop and a CPU spike. The supervisor also never reaches a terminal state: the unit stays
"restarting" instead of "failed", so the failure is invisible to anyone reading status rather than
logs.

**2. No single-instance guarantee.** The shim's entrypoint did not exclude a second copy, and nothing
made the new instance wait for the previous one to exit and release the listening socket. A restarted
instance that binds before the old process is gone gets `EADDRINUSE` — the new process dies of the
old process, which feeds defect 1.

**Why manual killing does not break the cycle:** the supervisor's job is to start an instance, so
killing the visible child just triggers the replacement. If the kill was not a clean exit (a
`SIGKILL`, or another instance still holding the port), the socket is still held when the
replacement binds — `EADDRINUSE` again. The port collision is a *symptom of overlapping instances*,
not of a stray process, which is why the same error keeps appearing after every cleanup attempt.

**The third cost is diagnostic:** the original crash's log is buried under N restarts, so the reason
the shim was failing in the first place is the hardest thing to find afterwards.

## Solution

### Step 1: one instance, enforced at the entrypoint

Mutual exclusion belongs in the shim itself, not in the supervisor, because every start path has to
respect it:

```bash
#!/usr/bin/env bash
set -euo pipefail

exec 9>"/run/agent-shim.lock" || exit 75
if ! flock -n 9; then
  echo "shim already running; exiting without binding" >&2
  exit 75
fi

exec node shim.js
```

`flock -n` is non-blocking: if another instance holds the lock, this one exits **before** binding the
port, with a message that says why. The file descriptor stays open for the process lifetime, so the
lock is released when the process dies. A pidfile works only if the stale-pid case is handled; `flock`
does not have that problem, because the kernel drops the lock with the process.

The exit code matters: it must be distinguishable from a crash, or the supervisor will treat
"another instance is running" as a failure and restart it.

### Step 2: give the supervisor a restart budget

The intake's knobs are systemd's:

```ini
# /etc/systemd/system/agent-shim.service
[Unit]
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Restart=on-failure
RestartSec=5
```

```bash
systemctl daemon-reload
systemctl restart agent-shim.service
```

- `RestartSec=5` spaces attempts out, so a crash loop is no longer a busy loop.
- `StartLimitBurst=3` inside `StartLimitIntervalSec=60` caps the burst: the third start inside the
  window is the last one, and the unit enters the failed state instead of respawning forever.
- `StartLimitIntervalSec` and `StartLimitBurst` belong in `[Unit]`, not `[Service]`; systemd logs a
  warning and ignores them in the wrong section.
- After manual repair, `systemctl reset-failed agent-shim.service` clears the start counter, otherwise
  the unit stays rate-limited.

### Step 3: identify the port holder before blaming the shim

```bash
ss -ltnp | grep 127.0.0.1:3080
```

If this prints a process, the port is held by a live listener — a real overlap, and the fix is Step 1
(the lock prevents the second instance). If it prints nothing and the shim still fails with
`EADDRINUSE`, the listener is in `TIME_WAIT` or in another network namespace, and the retry needs to
wait rather than bind immediately.

### Step 4: make the crash record survive the restarts

Log the first crash before the supervisor can spawn the next instance, and keep the unit's exit
status. With `Restart=on-failure`, the number of restarts and the last exit code are in
`systemctl status`; without them the operator sees N identical respawn lines and no cause.

## Verification

The reporter's criterion: terminating the shim gracefully ends the supervisor's respawn burst and
releases the listening port cleanly. Reporter-reported, not reproduced here.

Concrete checks:

1. Kill the shim once. The supervisor performs **one** restart (or none, once the burst limit is
   reached), not a stream of them; CPU returns to idle.
2. After the burst, `ss -ltnp | grep 127.0.0.1:3080` prints nothing, and `systemctl status
   agent-shim.service` reports the unit as failed rather than activating.
3. Start a second shim by hand while the first is running: it exits with the lock message and the
   port stays held by the first. Before the fix, this produced `EADDRINUSE` in the new instance.

The third check is the one that distinguishes "the loop stopped" from "the collision was fixed".

## Notes

- The reporter's knobs are systemd's. If the supervisor is supervisord instead, the equivalents are
  `startretries`, `startsecs` and a stop grace period — the intake does not give those values, so they
  need to be confirmed against that supervisor's documentation rather than copied from above.
- If the supervisor counts the lock-refusal exit (`75`) as a crash, add
  `RestartPreventExitStatus=75` to `[Service]` so a refused duplicate does not consume the restart
  budget. This is not part of the reporter's fix; it is the follow-on the fix implies.
- `EADDRINUSE` with a live holder is not fixed by `SO_REUSEADDR`; that option helps with `TIME_WAIT`
  rebinding, not with a second process trying to listen on the same address.
- Evidence level E1: one operator's report of the loop and the configuration they applied; not
  independently reproduced in this repository, and the supervisor's full unit file was not provided.
