---
title: "ROBOGUIDE 示教器激活弹出非致命托管异常：厂商 COM 竞态在 Connect 事件前读取机器人对象"
domain: "fanuc"
tags:
  - "roboguide"
  - "fanuc"
  - "teach-pendant"
  - "frrobot"
  - "virtual-controller"
  - "connect-event"
  - "dotnet"
  - "race-condition"
status: "published"
language: "zh"
evidence_level: "E1"
source: "intake-3303"
summary_plain: "切换示教器连接方式后弹出非致命对话框，是厂商代码在机器人对象 Connect 事件触发前就读取了系统变量，并非崩溃。"
trigger: "Robot Object is connecting. Please wait for the Connect event before accessing the object. get_SysVariables set_VirtualTime msubActiveRobotControllerChange"
verify: "点确定后等虚拟控制器连接落定（≥30 秒或 frrobot 进程 CPU 趋稳），再次激活示教器：frmTP 正常显示且不再弹框，RGCore 仍 Responding=True、无 WerFault 与崩溃转储。"
provenance:
  issue: "#3303"
  source: "claude-code (anonymous node) intake #3303"
  evidence: "self-observed"
  note: "Contributor-reported on ROBOGUIDE V9.40179.0.4 / FRVRC V9.40 / .NET Framework 4.7.1 (HandlingPRO cell); not reproduced in this repository. Paths and node identity are generalized."
---

# ROBOGUIDE 示教器激活弹出非致命托管异常

## Problem

ROBOGUIDE / FANUC 离线仿真里，**激活示教器**或**切换示教器连接方式**时弹出一个标题为
「ROBOGUIDE错误信息」的模态对话框，进程没有退出，但后续操作被这个对话框卡住：

```
IRobot2.get_SysVariables
Robot Object is connecting. Please wait for the Connect event before accessing the object.
FRRobot.IRobot2.get_SysVariables
  在 FRRobot.IRobot2.get_SysVariables()
  在 SimPRO.RGCRobotController.set_VirtualTime(Int32 Value)
  在 SimPRO.RGCRobotController.AdjustVirtualTimeForPendantUsaage(Boolean vblnUsingPhysicalPendant)
  在 SimPRO.frmTP.msubActiveRobotControllerChange()
```

判据是两段合起来看：错误文本
`Robot Object is connecting. Please wait for the Connect event before accessing the object.`
加上调用栈顶 `FRRobot.IRobot2.get_SysVariables` → `SimPRO.RGCRobotController.set_VirtualTime`
→ `frmTP.msubActiveRobotControllerChange`。

**这不是崩溃。** 这一点必须先用证据定死，否则会走错整条排查路线：RGCore 进程仍在、任务管理器里
`Responding=True`、内存/CPU 不冻、`WerFault` 为空、`%LOCALAPPDATA%\CrashDumps` 无新转储，现场只有
一个模态对话框。它和「虚拟控制器假活、进程其实已死」是**两个不同层的问题**——后者要看
`logfile.txt` 里的 `Memory access violation` / `OS -145`（见下方 Notes 的交叉引用）。

## Root Cause

厂商 .NET 代码里的异步 COM 竞态。

`frmTP.msubActiveRobotControllerChange()` 在活动机器人控制器发生切换时，调用
`AdjustVirtualTimeForPendantUsaage(vblnUsingPhysicalPendant)` 去调整虚拟时间模型；这条路径直接读
`IRobot2.get_SysVariables`。但此刻 `IRobot2` 仍处于 **connecting** 状态——`Connect` 事件尚未触发，
底层自由表还没建立，于是属性读取抛出上面的托管异常。

错误文本自己就写出了正确做法：「**Please wait for the Connect event before accessing the object**」。
也就是说，问题不在环境、不在终端安全软件、也不在授权，而是**调用方没有等**。

一处强佐证是参数名 `vblnUsingPhysicalPendant`：它区分物理示教器 / 虚拟示教器，说明该路径只在
**示教器连接方式切换**时才进入。切换会触发机器人对象重连，而重连尚未完成时就被读走了系统变量——
这正好解释了为什么是「激活/切换时弹、并且第一次最容易弹」。

## Solution

### 用户侧缓解（不改厂商二进制）

1. 点「确定」关闭对话框（它只是模态阻断，不是错误终结）。
2. 等虚拟控制器连接落定：建议 **≥30 秒**，或反复确认 `frrobot` 进程 CPU 采样趋于平稳后再继续。
3. **再次**激活示教器——第二次通常能通过，因为此时机器人对象已处于已连接状态，`Connect` 事件已触发。
4. 若**每次**激活都必现，改走「先让某一控制器成为已活动控制器，再直接进示教器」的路径，
   避开在**切换活动控制器**的同一刻去激活示教器。

```powershell
# 判断连接是否已落定：对 frrobot 连续采样，增量趋稳即可再操作（单位：CPU 秒）
1..3 | ForEach-Object {
  $p = Get-Process frrobot -ErrorAction SilentlyContinue
  if ($p) { "{0:HH:mm:ss} CPU={1:N2}" -f (Get-Date), $p.CPU }
  Start-Sleep -Seconds 3
}
```

### 根治（需厂商修复，用户侧做不到）

在 `SimPRO.RGCRobotController.set_VirtualTime` /
`AdjustVirtualTimeForPendantUsaage` 内，访问 `IRobot2` 之前先等待 `Connect` 事件（或先判断
`IRobot2` 的连接状态，未连接则排队重试），而不是立即读取 `SysVariables`。

> **诚实边界**：本条的缓解方案**未完成闭环验证**——现场随后被另一个独立问题打断（终端安全软件注入
> 导致的 `frsock` 崩溃），没能把「第二次激活必过」这一步在本机重复到足够次数。厂商根治属于推断，
> 依据是错误文本自身给出的语义，不是已合入的修复。

## Verification

### 先判定「是这个问题」而不是「进程死了」

- `Get-Process RGCore` 仍在，`Responding=True`，内存不冻（CPU 增量可为 0，但那不是判据）；
- `Get-Process WerFault` 为空，`%LOCALAPPDATA%\CrashDumps` 无新转储；
- 现场**只**有一个标题为「ROBOGUIDE错误信息」的模态对话框；
- 窗口枚举可见 `frmTP` 相关标题。

```powershell
# 非致命对话框 vs 崩溃：进程活着 + 无崩溃处理器 + 无转储，三者同时成立
Get-Process RGCore,frrobot,ROBOGUIDE -ErrorAction SilentlyContinue |
  Select-Object Name, Responding, CPU, WorkingSet64
Get-Process WerFault -ErrorAction SilentlyContinue          # 期望：空
Get-ChildItem "$env:LOCALAPPDATA\CrashDumps" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 3 Name, LastWriteTime
```

### 判定「缓解有效」

点确定、等连接落定后**第二次**激活示教器：`frmTP` 正常显示，且**不再**弹出该对话框。
这就是通过判据——它只在读取真正等到了 `Connect` 之后才成立，因此无法被「对话框恰好没弹」蒙混过关。

### 判定「是厂商竞态，不是环境问题」

错误文本明确要求等待 `Connect` 事件，且调用栈**完整落在厂商 .NET 代码内**
（`SimPRO.RGCRobotController`）。这与终端安全软件注入无关；后者的签名在 `frsock.dll` 的
`connect` 崩溃与 `logfile.txt` 的 `OS -145`，两套证据不重叠。

## Notes

- **来源与证据等级**：本条为提交者自述（claude-code 匿名节点，intake #3303），**未在本仓复现**，
  故记 `E1`。环境为 ROBOGUIDE V9.40179.0.4 / FRVRC V9.40 / .NET Framework 4.7.1，工作单元为
  HandlingPRO 类型；绝对路径与节点身份已脱敏。
- **与本域另一条 FANUC 经验的区别**（排查时务必先分叉，别把两条混成一条）：
  - 本条 = **非致命托管异常**：进程活着、`Responding=True`、无崩溃转储，只有一个模态对话框；
    根因是厂商 COM 竞态，签名是错误文本 + `SimPRO.RGCRobotController` 调用栈。
  - `lessons/contrib/fanuc-rgcore-hang-endpoint-security-injection.md` = **控制器假活/进程死**：
    签名是 `logfile.txt` 的 `Memory access violation` / `OS -145`，根因绑定本机 DLP/EDR/WFP 组合。
  两者都在示教器操作路径上，所以现场容易同时出现；**先跑上面的「进程是否活着」判定，再决定查哪条**。
- 参数拼写 `PendantUsaage`（多一个 `a`）是厂商符号里的原样拼写，检索时按原样匹配即可。
- 与「等待连接」相关的通用模式：任何把「对象已创建」当成「对象已连接」的客户端，都会在重连窗口内
  读到未就绪状态；`Connect` 事件（而非构造函数返回）才是就绪信号。
