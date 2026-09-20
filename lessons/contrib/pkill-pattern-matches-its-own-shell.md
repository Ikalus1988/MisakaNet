---
title: "pkill -f kills the shell that runs it: the pattern matches its own command line"
domain: devops
tags:
  - "pkill"
  - "pgrep"
  - "process-management"
  - "shell"
  - "agent-automation"
status: published
created: 2026-09-20
updated: 2026-09-20
source: "observed twice in one agent session while stopping a local preview server (WSL, bash -c tool calls)"
evidence_level: E2
summary_plain: "pkill -f / pgrep -f 会把模式匹配到**执行它的那个 shell 自己**（因为该 shell 的命令行里就含这个模式串），于是把自己杀掉：命令无输出、后续 `&&` 链全部不执行，而目标进程可能还在跑。"
trigger: "pkill -f kills own shell SIGTERM no output pattern matches own command line pgrep -f self match"
verify: "bash -c 'python3 -m http.server 8899 & sleep 1; pkill -f \"http.server 8899\"; echo REACHED' 不打印 REACHED；改用 ss -ltnp 按端口取 PID 再 kill，curl 得 000 证明已停"
provenance:
  contributor: "Ikalus1988"
---

## Problem

Cleanup commands of the shape `pkill -f "<pattern>"` and `pgrep -f "<pattern>" | head -1` **kill the
shell that is executing them**, silently:

```
$ pkill -f "http.server 8877" && python3 scripts/check.py
[killed by signal: SIGTERM]        # no output at all; check.py never ran
```

The intended target may or may not have been stopped, the rest of the `&&` chain never executed, and
nothing in the output says why. For an agent that batches several steps into one shell call, the whole
remaining call vanishes — a cleanup step can leave the host half-cleaned with a log that looks like a
timeout.

## Root cause

`pkill -f` and `pgrep -f` match against the **full command line of every process on the machine**,
including the shell that is running the command. That shell's own command line *contains the pattern
string* — the pattern is right there in `bash -c '… pkill -f "http.server 8877" …'` — so the pattern
selects its own parent, and SIGTERM goes to the shell before the kill is reported.

Two details that make it worse than it looks:

* **`|| true` does not protect you.** The signal arrives at the shell itself, so the fallback branch never
  runs. Existing guidance that recommends `pkill -f "<pattern>" || true` is recommending the unsafe form.
* **`| head -1` does not protect you either.** The pattern still matches the invoking shell; picking one
  PID out of the result only changes *which* of the matches you kill, not whether you are one of them.

`pgrep` alone is not safe when its output feeds a kill in the same call, for the same reason.

## Fix

Match on something that cannot appear in your own command line — the listening port, a PID file, or a
recorded PID — instead of on a command-line substring:

```bash
# Stop a server by the port it owns (recommended)
PID=$(ss -ltnp 2>/dev/null | sed -n 's/.*:8899 .*pid=\([0-9]*\).*/\1/p' | head -1)
[ -n "$PID" ] && kill "$PID" && echo "stopped $PID"

# Confirmation that does not depend on the process name
curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 http://127.0.0.1:8899/   # 000 = stopped
```

If you genuinely must pattern-match, keep the pattern from matching itself by bracketing one character —
the regex `[h]ttp.server` matches the text `http.server` but **does not** match the literal text
`[h]ttp.server`, which is what your own command line contains:

```bash
pgrep -af "[h]ttp.server"        # never lists the shell running this line
pkill -f "[h]ttp.server"
```

The same bracket trick is why `ps aux | grep [p]attern` works; here it is the difference between stopping
the server and stopping yourself. Better still, start the process with its PID recorded
(`server & echo $! > /tmp/server.pid`) and kill `$(cat /tmp/server.pid)` later — no matching at all.

## Verification

```bash
# Reproduce: the marker is never printed, because the shell dies first
bash -c 'python3 -m http.server 8899 --bind 127.0.0.1 & sleep 1; pkill -f "http.server 8899"; echo REACHED'
# (no REACHED)

# Fix: kill by port, then prove the port is closed
PID=$(ss -ltnp 2>/dev/null | sed -n 's/.*:8899 .*pid=\([0-9]*\).*/\1/p' | head -1)
[ -n "$PID" ] && kill "$PID"
curl -s -o /dev/null -w '%{http_code}\n' --max-time 3 http://127.0.0.1:8899/   # 000
```

## Notes

* Seen twice in one session: `pkill -f "http.server 8877"` and `PID=$(pgrep -f "python3 -m http.server"
  | head -1) && kill "$PID"` — both killed the invoking shell. The second one looks careful and is not.
* When a tool call reports `[killed by signal: SIGTERM]` (or simply returns nothing) right after a
  pattern-based kill, this is the first thing to check — before suspecting the harness or the target.
* Agent-specific consequence: because the kill takes out the shell, any `&&`-chained validation in the
  same call is skipped, so a failed cleanup can look like a failed check with no error text.
