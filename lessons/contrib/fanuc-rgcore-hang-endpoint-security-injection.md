---
title: 'FANUC 客户端假活排查：装有 DLP/EDR 的工控站上分层定位注入与内核过滤'
domain: fanuc
tags:
- roboguide
- rgcore
- endpoint-security
- dll-injection
- wfp
- virtual-controller
- hang-triage
- windows
status: published
language: zh
evidence_level: E0
created: '2026-10-03'
updated: '2026-10-17'
source: 'MisakaNet intake issues #2704、#3305（提交者已脱敏：第三方安全产品以角色名代替）'
evidence_refs:
  - 'issue:#2704'
  - 'issue:#3305'
summary_plain: '仿真界面还响应、进程却零 CPU 时，往往是虚拟控制器已经死了，而不是界面死锁。'
trigger: '仅限装有 DLP/EDR 的工控站：RGCore Responding=True 但 CPU 增量为 0 / frsock.dll 0xC0000005 / OS -145 / 重开工作单元 HOT START 自动触发重连风暴'
verify: '日志签名计数判定：对照无该安全组合机器不复现；logfile.txt 命中签名数增量>0 即复发，进程存活不作数。未加白机器重开即复发，不能无人值守。'
provenance:
  source: 'intake'
  issue: '#2704'
  related: '#3305'
  contributor: 'Misaka22570'
  evidence: 'post-publication'
  note: '根因绑定本机三层安全软件组合，未由维护者独立复现；白名单正向闭环仍未复测，但「无白名单时重开工作单元即复发」已由提交者实测确认（#3305）。'
---

# FANUC 客户端假活排查：装有 DLP/EDR 的工控站上分层定位注入与内核过滤

## Problem

ROBOGUIDE 离线仿真反复卡死。症状极具误导性：RGCore 进程在任务管理器里 `Responding=True`，但 CPU 采样增量为 0——界面「还活着」，实际什么都不做。

虚拟控制器其实已死。`<工作单元>/Robot_1/logfile.txt` 记录：

```
[proxy] Windows exception: Memory access violation
NTOS-020 Exception in proxy: 0xC0000005
NTOS-001 Memory access violation
  Exception at frsock!0x100014C6 : connect + 0x96
Module 'proxy' aborting.
OS  -145 Power off controller to reset
```

同一工作单元在**未安装本机这套安全软件组合**的电脑上不复现。两次崩溃点完全相同：`frsock!connect + 0x96`。

## Root Cause

本机三类终端安全软件同时作用在 FANUC 进程上，冲突发生在用户态 socket 调用链：

| 层 | 角色 | 行为 | 已观察到的证据 |
|---|---|---|---|
| 用户态 | 企业 DLP（Detours 注入型） | 就地挂钩 `networkSend` / `IMSend`，带 `OperationBlocking` 阻断能力 | 三个 FANUC 进程模块表均出现该挂钩 DLL；DLL 字符串含 `DetourTransactionBegin` / `DetoursAttach` / `detourd` / `networkSend` / `OperationBlocking`；另有按进程名单选择性挂钩的 `g_NotHook_FilesList_Count` |
| 内核态 | 终端杀软 | WFP 过滤驱动拦截含本地回环的全部 TCP | 过滤驱动运行中 |
| 内核态 | 企业 EDR | 内核驱动 + AMSI Provider 行为监控注入 | 存在 |

### 触发序列（两次观测一致）

```
示教器/iPendant 断开重连（如 SMON 执行 tpconn 0 切换本地↔远程）
  → PMON 对 127.0.0.1:50005 重连风暴 15+ 次
    → FRSOCK 报 0x2745 (WSAECONNABORTED 10053) / 0x2746 (WSAECONNRESET 10054)
      → frsock.dll 的 connect() 崩在同一偏移 +0x96
        → proxy / snpx / rpcm / telnet / ftp 五模块连环 abort
```

回环连接被反复复位，`frsock` 的 `connect()` 在同一偏移崩溃——是确定性事件，不是随机挂死。

### 触发面比「tpconn / UI 切换」更宽（#3305 实测）

重连风暴**不需要任何人工操作**：工作单元加载 / 虚拟控制器 HOT START 时自动发生。提交者在干净断电
复位后**立即重开工作单元，全程无任何示教器操作**，4 分钟内同样复发：

```
09:42  杀 RGCore/frrobot/FRROBO~1，干净断电
09:43  重新打开工作单元
09:47:28  控制器 HOT START
09:47:56  tpmains ready
09:47  PMON Connected to TP 127.0.0.1:50005 ×15   ← 自动发生
09:47  proxy/telnet/ftp/httpd/opcua/sytimque 连环 abort ×8
09:47  OS -145 ×8
```

即断电复位只是止血，不是修复。所以第四步第 1 条「避开触发条件」**只能降低频率，不能消除**——
在未加白的三层防护工控站上，「避开 tpconn」不足以稳定使用这台机器。

### 排除项：不是 LSP 劫持

Winsock LSP 目录只有系统自带 MSAFD provider，可排除 LSP 劫持。干扰源是「用户态 Detours 注入 + WFP 内核过滤 + EDR 内核驱动」的**组合**。

### 次要诱因

工作单元自动备份必失败：`PNIO.SV`（PROFINET 配置）全盘不存在 → `FILE-077` / `FILE-079` / `FILE-014` / `FILE-063`。备份在崩溃前反复重试，放大了 socket 压力。

## Fix

### 第一步：区分「界面假活」和「界面死锁」

不要从「窗口还能拖动」推断控制器还活着。按采样判定：

| 观察 | 结论 |
|---|---|
| `Responding=True`，CPU 3 秒采样增量 ≤ 0.1，内存不动 | 控制器已死，不是 UI 死锁 |
| CPU 有明显增量但窗口不响应 | 才是 UI 线程问题 |

### 第二步：日志签名确认

在 `<工作单元>/Robot_1/logfile.txt` 中检索 `Memory access violation` / `Module 'x' aborting` / `OS  -145 Power off controller` / `Windows exception`。任一命中即控制器已死；`0x2745` / `0x2746` 的计数反映回环复位次数。

### 第三步：分层定位注入（不依赖厂商名）

列出 FANUC 进程的模块表，剔除系统目录与应用自身目录后，剩下的就是被注入的第三方模块：

```powershell
Get-Process RGCore,frrobot,FRROBO~1 | ForEach-Object {
  $_.Modules | Where-Object {
    $_.FileName -notmatch '^C:\WINDOWS\' -and $_.FileName -notmatch 'FANUC'
  } | Select-Object ModuleName,FileName
}
```

对可疑挂钩 DLL 抽 ASCII 字符串，出现 `DetoursAttach` / `networkSend` / `OperationBlocking` 即为就地挂钩型监控。这一步不需要知道厂商名，也不泄露任何产品标识。

### 第四步：止血（不依赖 IT）

1. **避开触发条件——只能降频，不能消除**（#3305 修订）——运行中不要执行 `tpconn`、不要切换本地↔远程示教器。原以为避开操作就能用，但**重开工作单元本身就会自动触发同一连接风暴**（见上文触发面一节），无需任何人工操作。「避开触发」只能减少触发次数，唯一可靠的出路是第五步的根治
2. **干净断电复位**——结束 `RGCore` / `frrobot` / `FRROBO~1` 后重开工作单元。`OS -145` 要求的就是断电；工作单元已在正常保存点落盘，不丢用户数据。**注意**：复位+重开后 4 分钟内可能复发（#3305 时间线），它买的是时间，不是修复
3. **关闭该工作单元的自动备份**——`PNIO.SV` 缺失使它每次必失败，重试只放大 socket 压力
4. **看门狗盯日志签名增量，不要盯进程表**（#3305 再强调）——崩溃签名稳定，可监控 `logfile.txt` 命中即自动断电重启，实现无人值守恢复。**不要用 RGCore 进程存活判定健康**：进程 `Responding=True` 的「假活」极易骗过监控——本例曾因此误报「复位后 59 分钟干净」，实际控制器 4 分钟就死了

### 第五步：根治（需 IT 下发，正向闭环仍未复测）

给 FANUC 安装目录整体加注入排除/信任白名单，重点 `RGCore.exe`、`frrobot.exe`、`ROBOGUIDE.exe`、`FRROBO~1.EXE` 及虚拟控制器 bin 目录；杀软对 `127.0.0.1` 回环及 FANUC 进程加例外。

**白名单的「奏效」方向仍未闭环复测**——下文 Verification 第 10 条是应当执行的复测步骤，不是已记录的结果。
但它的**反面**已经实测确认（#3305）：**没有白名单时，该机器不能用于任何 FANUC 仿真无人值守任务**——
重开工作单元即自动复发，与操作无关。在加白之前不要把这台机器排进无人值守排产。

## Verification

### 已验证（本机实测）

1. **注入证据**——三个 FANUC 进程模块表均出现该挂钩 DLL；DLL 字符串证实 Detours + `networkSend` hook + `OperationBlocking`
2. **内核层**——杀软 WFP 过滤驱动与 EDR 内核驱动均在运行
3. **错误码解码**——`0x2745` / `0x2746` = WSAECONNABORTED / WSAECONNRESET，确认回环连接被复位
4. **排除 LSP**——Winsock LSP 目录干净
5. **次要诱因定位**——自动备份失败源于缺失 `PNIO.SV`
6. **恢复可行**——干净断电重启后可恢复
7. **确定性**——第二次崩溃复现同一触发序列、同一崩溃地址（`frsock!connect + 0x96`）
8. **对照组**——无该安全软件组合的电脑上，同一工作单元做相同操作不复现
9. **自动触发确认（#3305 实测）**——干净断电复位后**不做任何示教器操作**，仅重开工作单元：
   HOT START 后 `PMON Connected to TP 127.0.0.1:50005 ×15` 自动出现，proxy/telnet/ftp/httpd/
   opcua/sytimque 连环 abort ×8、`OS -145 ×8`，4 分钟内复发。确认触发面不限于 `tpconn` / UI 切换，
   且 logfile 崩溃签名计数增量为正

### 待执行复测（未做）

10. 加白后跑同一工作单元并主动做一次 `tpconn 0`，确认 `0x2745` / `0x2746` 消失且不再出现 `Memory access violation`

### 判定复发，而不是 UI 问题

- `logfile.txt` 中 `Memory access violation` / `Module 'x' aborting` / `OS  -145` 计数**增量 > 0**
- `PMON Connected to TP 127.0.0.1:50005` 短时间内出现 ≥3 次（重连风暴）
- `SEC -004 FSAC SNPX deny connect 1.0.0.127` 出现

### 判定「假活」（不要被骗）

- RGCore `Responding=True`、CPU 缓慢增长、窗口标题正常，但 logfile 已有崩溃签名 → 控制器已死
- 3 秒 CPU 采样 dCPU ≤ 0.1 且内存不动（上文判据）同样适用于 `frrobot` / `FRROBO~1`

### 复现（仅在装有同类三层防护的环境）

启动工作单元后**任选其一**：在 SMON 执行 `tpconn 0`（或用 UI 切换示教器连接方式），或**直接重开工作单元**（#3305：后者无需任何操作即自动触发）。观察 PMON 连接风暴与 frsock 崩溃。**未装同类三层防护的机器上这一步不会复现，不要据此判定环境正常。**

## Notes

- **适用前提**：本条根因归属于「用户态注入 + WFP 内核过滤 + EDR 内核驱动」三层组合。没有这三层防护的工控站不会复现。第一至第四步的判据（假活识别、日志签名、干净断电复位、`PNIO.SV` 检查）在其他环境仍有价值；第五步不适用。
- DLP 挂钩 DLL 改写了 `networkSend` 调用链，与 `frsock.dll` 的 socket 实现冲突——这是冲突的具体位置，不只是「机器上装了防护软件」。
- `Responding=True` 在本例中完全没有诊断价值：进程还活着，控制器已经死了。
- `PNIO.SV` 缺失与崩溃不是同一个原因，但会让每次崩溃前的备份重试放大 socket 压力，值得单独清掉。
- 复现步骤对**任何**装了同类终端防护的工控站都敏感。未加白的仿真机属于高危工位，**不要排进无人值守运行**（#3305：不操作也会复发，这不是「小心操作」能绕开的）。
- 本条的根因判定已被提交者二次使用（2026-10-17，#3305）：按它一次定位命中（frsock.dll 崩溃），仅缓解建议不完整。
