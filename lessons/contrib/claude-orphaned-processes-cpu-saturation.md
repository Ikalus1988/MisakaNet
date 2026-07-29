---
title: "Orphaned Agent Processes: Finding and Killing CPU-Spinning Children Left Behind"
domain: ai-agents
tags: [coding, debugging, claude, devops]
source: https://dev.to/sidhantpanda/claude-might-be-saturating-your-machine-3h07
source_type: blog
created: 2026-07-16
confidence: 80
---

## Problem

A laptop was sitting idle with the fan at full speed. Investigation revealed ten orphaned `while :; do :; done` busy-loops left behind by a Claude Code session two days earlier. Load average was 122.91 on a 10-core machine. The test processes (vitest, pnpm) were long gone — only the spinners survived, consuming ~700% CPU.

## Root Cause

The agent spawned CPU-spinning background processes for a stress test, then failed to clean them up due to two compounding failures:

1. **`jobs -p` returns nothing in non-interactive shells.** The script used `LOADPIDS=$(jobs -p)` to collect background PIDs, but job control is disabled in non-interactive shells, so the `kill` command had no targets.

2. **No trap — cleanup only on happy path.** The parent shell died before reaching the `kill` line. Since cleanup was linear (no `trap`), the children were orphaned and reparented to PID 1 (launchd), where they ran unattended.

## Diagnosis

```bash
# Check load average against core count
uptime

# Find top CPU consumers with their parent PIDs
ps -Ao pcpu,pid,ppid,user,comm -r | head -15

# Look for high-CPU processes with PPID 1 and long elapsed times
ps -o pid,lstart,etime,pcpu,args -p <pid1>,<pid2>,...
```

High-CPU processes with PPID 1 and elapsed time of hours/days are almost certainly orphaned.

## Solution

```bash
# Kill the orphaned processes (no -9 needed, SIGTERM suffices)
kill <pid1> <pid2> ...
```

Verify:
```bash
# Confirm processes are gone
ps -o pid= -p <pid1>,<pid2>,... | wc -l   # should be 0

# Check CPU usage returned to normal
ps -Ao pcpu,pid,comm -r | head -4
```

Note: load average is a decaying rolling average — it lags behind reality. Judge the fix by the process list, not the load number.

## Prevention

Collect `$!` after each background spawn instead of using `jobs -p`:

```bash
LOADPIDS=""
for i in $(seq 1 $NCPU); do
  (while :; do :; done) &
  LOADPIDS="$LOADPIDS $!"
done
trap 'kill $LOADPIDS 2>/dev/null' EXIT INT TERM
```

Caveat: traps won't fire on SIGKILL. For extra safety on Linux, use `PR_SET_PDEATHSIG` in children. On macOS, children can poll `getppid()` and exit if it becomes 1.

## Verification

After killing orphaned processes, confirm they are gone:

```bash
ps -o pid= -p <pid1>,<pid2>,... | wc -l   # should return 0
ps -Ao pcpu,pid,comm -r | head -4          # CPU usage back to normal
```

Load average is a decaying rolling average — judge the fix by the process list, not the load number.

## Notes

- Agents run real commands that consume real resources. A crashed or cancelled agent session does not necessarily clean up its child processes.
- SIGKILL cannot be caught by traps. For extra robustness, use process groups or have children poll `getppid()`.

## Source

Based on Sidhant Panda's Dev.to article "Claude might be saturating your machine" (Jul 2026). Commenter Vinicius Pereira added the SIGKILL/process-group caveats.
