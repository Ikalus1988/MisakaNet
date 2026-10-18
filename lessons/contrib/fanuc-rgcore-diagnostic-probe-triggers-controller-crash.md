---
title: 'FANUC 虚拟控制器诊断纪律：对回环端口的 TCP 探测会亲手把控制器弄崩'
domain: fanuc
tags:
- roboguide
- rgcore
- frvrc
- diagnostic-discipline
- tcp-probe
- loopback
- crash-triage
- endpoint-security
- virtual-controller
- windows
status: published
language: zh
evidence_level: E1
created: '2026-10-17'
updated: '2026-10-17'
source: 'MisakaNet intake issue #3316'
summary_plain: '控制器还健康时，从本机对它的回环服务做一次普通 TCP 探测，就会在数秒内把它弄崩；排查这类故障要先做只读观测。'
trigger: 'FANUC ROBOGUIDE 虚拟控制器在本地 TCP 探测后崩溃 / frsock connect +0x96 / PMON Connected to TP 127.0.0.1:50005 / OS -145'
verify: '只做只读观测（读 services.txt、logfile.txt、Get-NetTCPConnection -State Listen）时崩溃签名零增量；一旦对 FTP/Telnet 端口发起连接，数秒内出现 OS -145 与 15 次以上 PMON 重连。'
provenance:
  source: 'intake'
  issue: '#3316'
  evidence: 'self-reported'
  note: '触发面由提交者在 FRVRC V9.40 / ROBOGUIDE V9.40179.0.4 实测；根因（用户态注入 + WFP + EDR 三层组合）绑定本机环境，未由维护者独立复现。'
---

# FANUC 虚拟控制器诊断纪律：对回环端口的 TCP 探测会亲手把控制器弄崩

## Problem

排查 ROBOGUIDE / FRVRC 虚拟控制器故障时，**诊断动作本身把被诊断对象弄崩**。

在控制器健康运行期间（RGCore 内存正常增长、CPU 持续爬升、`logfile.txt` 无崩溃签名），从本机对虚拟控制器的网络服务做一次普通 TCP 探测——例如连 `127.0.0.1:21`（FTP）发送 `USER`/`PASS`——数秒内 `<工作单元>/Robot_1/logfile.txt` 即出现：

```
Memory access violation +2
Module 'x' aborting +1
OS  -145 Power off controller to reset
PXPMON PMON Connected to TP 127.0.0.1:50005  +15
```

随后连环 abort 持续累积（`+2` → `+3`），控制器死亡。触发点与故障点时间上紧邻，容易被误读成"控制器自己坏了"。

**判据（诊断触发而非自然崩溃）：**

- 崩溃时间戳与某次本地 TCP 连接时间戳相差数秒
- 崩溃前 logfile 无新增签名、进程 CPU/内存正常
- 崩溃后 `PMON Connected to TP 127.0.0.1:50005` 短时出现 ≥15 次，并伴随 `OS  -145`

## Root Cause

根因见 [`fanuc-rgcore-hang-endpoint-security-injection`](fanuc-rgcore-hang-endpoint-security-injection.md)：用户态 DLP（Detours 挂钩 `networkSend`）+ WFP 内核过滤 + EDR 内核驱动的三层组合，使 `frsock.dll` 的 `connect()` 在偏移 `+0x96` 处确定性崩溃。

本条要补充的是**触发面比"示教器断开重连"宽得多**：

> **任何从本机到虚拟控制器服务的回环 TCP 连接都可能触发**，包括诊断工具的端口探测。

`<工作单元>/Robot_1/services.txt` 列出的监听端口：

```
FTP 21 | Telnet 23 | Teach Pendant 9099 | RPCMAIN 3002 | Console/SMON 9101
```

控制器侧已有 `SEC -004 FSAC SNPX deny connect 1.0.0.127`（安全配置拒绝回环连接）与 `HRTL-050 Network is down`：回环连接被反复复位，正是 `frsock` 的确定性崩溃路径。**一次诊断连接等于人为制造了一次连接复位**——观察者成了触发器。

## Solution

排查时的硬性纪律：

1. **不要在控制器运行期间，从本机对上述任何端口做 TCP 连接 / 扫描 / 探测**——包括看似无害的 banner 抓取、匿名登录尝试、`USER`/`PASS` 探测。
2. 需要确认服务状态时，用**被动观测**——只读文件、只看监听表，不建连：

   ```powershell
   # 读控制器自述的服务清单（端口 + PID），不建连
   Get-Content '.\Robot_1\services.txt'

   # 只看监听，不建连
   Get-NetTCPConnection -State Listen |
     Where-Object { $_.LocalPort -in 21,23,9099,3002,9101 }

   # 周期读 logfile，统计崩溃签名是否新增
   Select-String -Path '.\Robot_1\logfile.txt' -Pattern 'Memory access violation','OS  -145'
   ```

3. 需要**登录**控制器时（SMON 等），只在已知不会触发崩溃的环境操作；本环境 SMON 需口令，口令不写入任何记录。
4. 真正的根治仍是给 FANUC 目录加注入排除白名单（原 lesson 第五步）。

**诊断伦理（额外教训）**：在"观测会改变系统状态"的故障上，先做只读观测，再决定是否交互；一旦发现交互会致崩，立即停止并记录，不要继续试其他端口。把"排除端口 22 没崩"当成"环境正常"会掩盖真正的结论——本例所有回环端口共享同一条崩溃路径。

## Verification

**判定是诊断动作触发而非自然崩溃：**

- 崩溃时间戳紧随某次本地 TCP 连接（秒级）
- 崩溃前 logfile 无新增签名、进程 CPU/内存正常增长
- 崩溃后立即出现 `PMON Connected to TP 127.0.0.1:50005` ×≥15 与 `OS  -145`

**判定已停止触发：**

- 仅做只读观测（读文件、查监听表）时，logfile 签名计数长时间零增量

**实测对照**：15:06 启动后仅只读观测，11 分钟零签名；15:17:4x 发起 FTP 探测，15:17:51 崩溃（间隔 <15 秒）。

Source: FRVRC V9.40 / ROBOGUIDE V9.40179.0.4，服务清单 `<工作单元>/Robot_1/services.txt`。

## Notes

- **适用前提**：本条根因归属于"用户态注入 + WFP 内核过滤 + EDR 内核驱动"三层组合。没有这三层防护的工控站不会复现；但"排查时先只读观测、别拿 TCP 探测去确认服务"这条纪律在任何环境都成立。
- 触发面比原 lesson 描述更宽：原 lesson 把触发写成"示教器/iPendant 断开重连""`tpconn 0`""UI 切换本地↔远程示教器"，实测诊断端口探测同样触发。
- 崩溃前 CPU 正常爬升、内存正常，正是"控制器还活着"的证据——也正因如此，诊断者容易放心地去连接它。
- 相关：`fanuc-rgcore-hang-endpoint-security-injection`（根因与分层定位、干净断电复位、白名单）。
