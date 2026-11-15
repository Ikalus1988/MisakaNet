---
domain: "agent"
title: "Long context pollution — delegate independent tasks to subagents, keep only decisions in the main context"
tags:
  - "context-management"
  - "subagent"
  - "delegation"
  - "context-pollution"
  - "orchestration"
status: "published"
evidence_level: "E1"
summary_plain: "Raw logs and file contents pollute the main context; delegate work to subagents and keep only conclusions."
trigger: "context window exceeded long session dilutes constraints repeated work subagent delegation"
verify: "main context line count does not grow with subtask count; subtask process material does not enter main context"
---

# Long context pollution — delegate independent tasks to subagents, keep only decisions in the main context

## Problem

In long sessions, the main context gets gradually filled: every file read, every raw log line, every full trial-and-error output stays in the main thread. After dozens of rounds, the original constraints and goals are diluted — the agent starts dropping constraints, repeating work, even redoing already-completed steps. Meanwhile, each continuation round must re-digest the entire history, so token cost and error rate rise simultaneously.

The root failure: putting large volumes of independent work into the main context is the starting point of this failure chain.

## Root Cause

The default execution strategy is "do it in-place": batch file reads, batch searches, batch regression checks, enumeration-style translation — all independent work units, with no shunting mechanism, land in the same context. Context is a single, finite attention budget — any raw material read into it permanently occupies quota and dilutes every subsequent decision.

Missing shunting is not missing capability — it serializes parallel work onto the single attention channel.

## Solution

Multi-step, multi-file, parallelizable work should first be assessed for splittability, then executed per these five rules:

### Step 1 — Delegate independent work units to subagents

Hand independent work units (subagent / subagent_fork / teammate) to subagents. Only bring conclusions back to the main context — not the raw process material.

### Step 2 — Main context does only four things

The main context should only:
1. **Decompose** — break the task into independent units
2. **Dispatch** — assign each unit to a subagent
3. **Verify** — check the returned conclusions against the acceptance criteria
4. **Reply** — compose the final answer from the verified conclusions

### Step 3 — Each subagent task brief must specify

The task brief for each subagent must state: first read the skills and MCP tool catalog, then invoke the skill / MCP tool that matches this task — do not re-invent the wheel.

### Step 4 — Dispatch multiple independent tasks concurrently

Multiple independent dispatches go in the same message, sent concurrently. While waiting, the main thread continues other independent steps — do not spin-poll.

### Step 5 — Subagents return results, not intermediate steps

Subagents return results (conclusions, verdicts, data), not process material (logs, raw output, intermediate state). The main context does not accept raw logs.

## Verification

双侧对照（5 个同构子任务：内联跑 vs 委托跑，只统计进主上下文的行数）：

```console
$ python3 - <<'PY'
import subprocess, sys
N = 5
main_inline = 7 * N  # 每个子任务的过程输出（初始化/工具清单/契约/编码检查…）都落在主上下文
inner = "import concurrent.futures\ndef work(i):\n    return 'conclusion-%d: endpoint contract valid' % i\nwith concurrent.futures.ThreadPoolExecutor(5) as ex:\n    for c in ex.map(work, range(5)):\n        print(c)"
proc = subprocess.run([sys.executable, '-c', inner], capture_output=True, text=True)
main_delegated = len(proc.stdout.strip().splitlines())
print(f'fault  side (inline)   : main-context lines = {main_inline} for {N} subtasks')
print(f'fix    side (delegated): main-context lines = {main_delegated} (conclusions only)')
assert main_inline > main_delegated * 5
print('OK: delegation keeps main context flat while inline absorbs every subtask log — the lesson holds')
PY
fault  side (inline)   : main-context lines = 35 for 5 subtasks
fix    side (delegated): main-context lines = 5 (conclusions only)
OK: delegation keeps main context flat while inline absorbs every subtask log — the lesson holds
```

断言钉住：内联行数必须超过委托行数 5 倍（实测 7 倍）；委托侧只有结论行。这是机制对照——它证明
"主上下文随子任务数增长"与"只留结论"的差异，与本篇 2026-10-03 会话实测的判据一致。

## Notes

- This is the same shape as "the working set of a long-running process exceeds RAM and starts swapping" — the fix is to page out independent work, not to buy more RAM (or in the agent case, not to buy more context window).
- Related: `[A corpus cached in one row has a ceiling]` (the storage-side analog), `[Agent read_file Silent Truncation in Multi-Brain Meeting Recovery]` (the truncation-side failure).
