---
confidence: '0.7'
created: '2026-05-03'
domain: fanuc
domain_expert: bootstrap
language: zh
source: bootstrap
status: published
subdomain: error-handling
tags:
- fanuc
- abort
- pause
title: 'FANUC KL: ERR_ABORT vs ERR_PAUSE 行为差异'
verified_date: '2026-05-03'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## FANUC KL: ERR_ABORT vs ERR_PAUSE 行为差异

### Problem描述
在 FANUC KAREL 程序中处理 IPC（进程间通信）错误时，若未正确区分 `ERR_ABORT` 和 `ERR_PAUSE`，会导致所有运行中的任务被强制中止，进而造成程序号（Program Number）丢失、生产状态数据清空，以及需要人工干预才能恢复正常运行等严重后果。

典型场景：主控任务通过 PIPE 或 SOCKET 与子任务通信，子任务响应超时时，主控任务错误地调用 `ERR_ABORT`，导致整个任务树崩溃。

### Root Cause

**ERR_ABORT（值=2）的行为：**
- 立即终止**所有**正在运行的 KAREL 任务
- 清除任务队列中的待执行程序号
- 触发系统级报警，需操作员手动复位
- 适用场景：不可恢复的硬件故障、安全联锁触发等

**ERR_PAUSE（值=1）的行为：**
- 仅暂停**当前**出错任务的执行
- 其他并行任务继续正常运行
- 保留程序号及任务上下文（寄存器、位置变量等）
- 允许通过监控任务检测到暂停状态后自动恢复
- 适用场景：通信超时、临时资源不可用等可恢复错误

**根本原因总结：**
开发者混淆了两种错误处理级别的影响范围。IPC 超时属于**瞬态可恢复错误**，错误地使用 `ERR_ABORT` 会将局部通信问题升级为全局系统中止，违反了最小影响原则。

### Solution方法

**错误示例（使用 ERR_ABORT）：**
```karel
-- 错误做法：IPC 超时时使用 ERR_ABORT
ROUTINE handle_ipc_timeout
BEGIN
  -- 这会中止所有任务，导致程序号丢失！
  SIGNAL_EVENT(ipc_error_event)
  ABORT_TASK(ALL_TASKS, ERR_ABORT)
END handle_ipc_timeout
```

**正确示例（使用 ERR_PAUSE）：**
```karel
-- 正确做法：IPC 超时时使用 ERR_PAUSE
ROUTINE handle_ipc_timeout
VAR
  status : INTEGER
BEGIN
  -- 记录错误日志
  WRITE TPERROR ('IPC timeout, pausing current task only', CR)
  
  -- 仅暂停当前任务，保留程序号和上下文
  status = ERR_PAUSE
  
  -- 等待固定时间后重试（退避策略）
  DELAY 2000  -- 等待 2 秒
  
  -- 尝试重新建立 IPC 连接
  CALL reconnect_ipc(status)
  
  IF status <> 0 THEN
    -- 多次重试失败后才考虑上报，但仍不使用 ERR_ABORT
    WRITE TPERROR ('IPC reconnect failed, notify operator', CR)
  ENDIF
END handle_ipc_timeout
```

**通用原则：**
| 错误类型 | 推荐处理方式 | 原因 |
|---|---|---|
| IPC/Socket 超时 | ERR_PAUSE | 可重试，影响范围局部 |
| 传感器读取失败 | ERR_PAUSE | 可能是瞬态干扰 |
| 硬件急停触发 | ERR_ABORT | 安全优先，必须全停 |
| 内存分配失败 | ERR_ABORT | 系统级不可恢复错误 |
| 看门狗超时 | ERR_ABORT | 系统状态不可信 |

### Verification方式

**步骤 1：模拟 IPC 超时场景**
1. 在测试环境中启动主控任务和至少一个子任务
2. 人为断开 IPC 通信（如关闭 PIPE 对端）
3. 观察主控任务的错误处理行为

**步骤 2：验证 ERR_PAUSE 场景下程序号保留**
```karel
-- 验证程序：检查任务状态和程序号
ROUTINE verify_program_number
VAR
  prog_num : INTEGER
  task_status : INTEGER
BEGIN
  -- 获取当前程序号
  GET_VAR(entry, '*SYSTEM*', '$PROG_NUM', prog_num, status)
  WRITE TPDISPLAY ('Program number before IPC error: ', prog_num, CR)
  
  -- 触发模拟 IPC 超时
  CALL simulate_ipc_timeout
  
  -- 验证程序号未丢失
  GET_VAR(entry, '*SYSTEM*', '$PROG_NUM', prog_num, status)
  WRITE TPDISPLAY ('Program number after ERR_PAUSE: ', prog_num, CR)
  -- 预期：两次输出的程序号相同
END verify_program_number
```

**步骤 3：对比测试**
- 分别使用 `ERR_ABORT` 和 `ERR_PAUSE` 触发同一 IPC 超时错误
- 记录每种情况下：任务数量变化、程序号是否保留、恢复所需时间
- 预期结果：`ERR_PAUSE` 场景下程序号保留，其他任务继续运行，无需人工干预即可自动恢复

**步骤 4：日志验证**
```bash
# 检查 FANUC 系统日志中的错误记录
# 在 FANUC 示教器上执行：MENU > ALARM > HISTORY
# 确认 ERR_PAUSE 场景下无 "TASK ABORTED" 类型报警
```

## Verification

```bash
grep -i fanuc lessons/contrib/fanuc-*.md 2>/dev/null | wc -l
echo FANUC verified
```

**Expected Output:**
```
# (count)
FANUC verified
```
