---
title: "schtasks /Create returns exit code 4294967295 with no output when the task path has non-ASCII characters"
domain: "windows"
tags:
  - "windows"
  - "powershell"
  - "schtasks"
  - "task-scheduler"
  - "non-ascii"
  - "scheduled-tasks"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "中文路径让 schtasks /Create 一声不吭地返回 4294967295、任务也没建；换成 Register-ScheduledTask 一次就成功。"
trigger: "schtasks /Create exit code 4294967295 with empty stdout and stderr, task not created, non-ASCII path"
verify: "Get-ScheduledTask -TaskName <name> returns the task with the expected State, and at the trigger time the script actually runs and leaves a log entry."
source: "intake-3842"
provenance:
  issue: "#3842"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# schtasks /Create returns exit code 4294967295 with no output when the task path has non-ASCII characters

## Problem

On Windows, creating a scheduled task from the command line failed whenever the arguments pointed at
a script under a directory whose name contains Chinese characters:

```
exit code 4294967295 (0xFFFFFFFF)，stdout/stderr 均为空
```

Nothing was printed on either stream, and the task was not created — so the only evidence that
anything had happened was the exit code and the absence of the task. The same command pointed at a
script under a pure-ASCII path worked.

What the reporter tried, all of it ineffective:

- re-checking the quote/escape nesting in the command line;
- rewriting the `/TR` value with a single layer of quotes;
- wrapping the path in an extra pair of double quotes.

`Register-ScheduledTask` (PowerShell) created the task on the **first** attempt, with the same
non-ASCII path.

## Root Cause

**The report does not establish a root cause — 报料者未给出，需复现确认.** The intake contains no
`schtasks` message (there was none), no command line, no task name and no Windows build, so the
mechanism below is a hypothesis consistent with the observation, not a verified finding.

Two facts are solid regardless of the mechanism:

1. **`4294967295` is `0xFFFFFFFF`, which is `-1` reinterpreted as unsigned 32-bit.** It is the
   generic failure return of the tool, not a coded diagnosis: it says "the operation failed" and
   nothing about why. Treating it as an error code to look up sends you nowhere.
2. **The only variable that changed the outcome was the character set of the path.** The identical
   shape of command succeeded on an ASCII path and failed on a non-ASCII one, and a different API
   (`Register-ScheduledTask`, which passes the path to the Task Scheduler service rather than
   through a native console command line) succeeded with the non-ASCII path.

The mechanism usually offered for this family is argument/code-page mangling: a native console tool
receives its command line through the console code page, and multi-byte characters can be split or
mis-decoded before the task definition is written, which can fail before any message is emitted.
The report does not test this, so it stays a hypothesis. What the report *does* establish is that the
failure mode is **silent**: no output, no event, only an exit code — which is why any fix has to end
with a positive check that the task really exists.

## Solution

**Preferred: create the task through the Task Scheduler PowerShell cmdlets,** which took the
non-ASCII path on the first try. The reporter names the combination but does not paste the script, so
the skeleton below is reconstructed from those cmdlet names — 报料者未给出完整命令，需复现确认:

```powershell
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
             -Argument '-NoProfile -ExecutionPolicy Bypass -File "<path-to-script>"'
$trigger = New-ScheduledTaskTrigger -Daily -At 03:00

Register-ScheduledTask -TaskName '<task-name>' -Action $action `
  -Trigger $trigger -Description '<what this job does>' -Force
```

**Alternative: move the script to a pure-ASCII path** and keep using `schtasks`. The reporter
confirms this also works, and it is the smaller change when the task already exists in a deployment
script — but it moves the problem to whoever names directories, so it is a workaround, not a fix.

**Either way, verify before depending on the task.** `schtasks` gave no message at all, so its exit
code alone must never be treated as success:

```powershell
$t = Get-ScheduledTask -TaskName '<task-name>' -ErrorAction Stop
$t.State      # Ready / Running / Disabled — not the exit code
```

## Verification

The reporter's stated criterion, plus the discriminator that tells you whether the path was really
the cause:

1. `Get-ScheduledTask -TaskName <name>` finds the task and its `State` is what the schedule implies.
2. After the trigger time passes, the script actually runs and leaves its log entry — a task that
   exists but never fires passes check 1 and fails the job.
3. **Discriminator:** build the identical task from a pure-ASCII path. If that also fails, the
   non-ASCII path was not the cause and the quoting, the principal/credentials or the trigger
   definition needs looking at instead.

## Notes

- Evidence E1: one reporter, one Windows host; not reproduced in this repository. No Windows build,
  task name, trigger or full command line is recorded in the intake.
- `4294967295` in a `schtasks` log will also appear as `-1` in some wrappers: it is the same value
  under a signed type, not a second failure mode.
- The failure was silent on both streams. Any automation around `schtasks` should assert the task
  exists afterwards rather than trusting the exit code — this is the same "absence of error output is
  not success" trap that shows up across Windows command-line tooling.
- Siblings on the non-ASCII-path axis: `lessons/contrib/windows-non-ascii-username-pg0-initdb-utf8.md`
  (non-ASCII user path breaking `initdb`) and `lessons/contrib/tts-chinese-encoding-powershell.md`
  (Chinese text destroyed by a PowerShell pipeline).
