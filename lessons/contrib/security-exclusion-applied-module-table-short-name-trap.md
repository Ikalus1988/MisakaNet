---
title: "Three signals that lie about whether a security-software exclusion was applied, plus the 8.3 short-name trap"
domain: "security"
tags:
  - "endpoint-security"
  - "exclusion"
  - "dlp"
  - "dll-injection"
  - "windows"
  - "verification"
  - "short-name"
  - "process-modules"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "判断安全软件有没有真的给目标程序加白，只看目标进程模块表里还有没有那个注入 DLL；配置文件改过和材料结论都不是证据。"
trigger: "如何判断加白/注入排除是否生效 / 配置文件 mtime 变了但故障照旧 / 材料写未检出注入 / FRROBO~1.EXE 到底是哪个进程"
verify: "Get-Process <目标进程> 的 Modules 里不再出现挂钩 DLL 才算生效，且故障签名不复现；模块表仍列出 DLL 即未生效，与配置 mtime 无关。"
source: "intake-3321"
provenance:
  issue: "#3321"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Three signals that lie about whether a security-software exclusion was applied, plus the 8.3 short-name trap

## Problem

向 IT 提交「给某软件加注入排除 / 白名单」的申请后，无法判断申请是否被执行。三种常见误判在本例同时出现，导致长期错误结论：

1. **看安全软件的配置文件时间戳**——发现「配置在 X 时间被改过」，推断「IT 操作过了」；
2. **信申请材料自己写的基线结论**——材料里写「第三方模块注入：未检出」，推断「已生效 / 问题自愈」；
3. **按进程短名推断文件归属**——认为某个 8.3 短名是某 exe 的别名，只给其中一个加了白。

结果：材料结论表写「未检出注入」，据此推断「崩溃源可能已消失」，实际注入仍在、故障仍复现。

实测时间线：

```
10-15 09:41  材料写「未检出注入」
10-15 13:50  DLP 配置批量更新（看起来「已操作」）
10-16        实测 CGEHDll.dll 仍在两个进程的模块表中，故障 36 秒复现
```

## Root Cause

**唯一可信的判据是「目标进程当前的模块表里有没有那个注入 DLL」。** 其余都是间接证据：

| 证据来源 | 为什么不可信 |
|---|---|
| 安全软件配置文件 mtime | 例行策略同步也会批量刷写（本例 11 个文件在同一分钟更新，含指纹 / 规则包 / 登录数据），不是定向加白 |
| 申请材料的基线表 | 可能在目标进程未启动时检查（本例虚拟控制器未引导就查注入，当然查不到）；且结论行比附注警告更显眼 |
| 配置文件内容 | 供应商加密格式（本例 `CGENCDF2022V01` 头），本地读不出 |
| 进程短名推断 | 8.3 短名归属反直觉，必须用 `dir /x` 核实 |

### 8.3 短名陷阱（本例实证）

目录下同时存在 `frrobot.exe`（1,884,211 字节）与 `FRRobotNeighborhood.exe`（430,080 字节）。`dir /x` 输出：

```
1,884,211              frrobot.exe
  430,080  FRROBO~1.EXE FRRobotNeighborhood.exe
```

即 `FRROBO~1.EXE` = `FRRobotNeighborhood.exe`，**不是** `frrobot.exe`。按「短名 = A 的别名」去加白，会漏掉真正的目标进程。

## Solution

判定加白是否生效，只用这一条：

```powershell
Get-Process <目标进程> | ForEach-Object {
  $_.Modules | Where-Object {
    $_.FileName -notmatch '^C:\WINDOWS\' -and $_.FileName -notmatch '<应用自身目录>'
  } | Select-Object ModuleName,FileName
}
```

- 模块表里**仍有**注入 DLL → 加白未生效，无论配置改没改；
- 模块表里**没有**注入 DLL → 才可认为生效（再用故障签名复测二次确认）。

写申请材料时的纪律：

1. 不要写「未检出注入」这类会让人以为已解决的结论，除非是在目标进程已完整运行、且已用上式验证后写的；
2. 结论必须写成**可被对方独立复验的判据**（给出命令和期望输出），而不是叙述；
3. 进程清单用 `dir /x` 核实过短名归属后再写，或干脆按目录递归加白，不依赖短名；
4. 若某次检查是在目标进程未启动时做的，明确标注「该结论无效，待进程起来后重测」，不要放进结论表。

## Verification

判定「已生效」：

- 目标进程模块表中无注入 DLL（上式输出为空）；
- 故障签名复测不复现。

判定「未生效」（本例）：

- 目标进程模块表中仍列出注入 DLL，即使安全软件配置在申请提交后有批量 mtime 更新。

判定短名归属：

- `cmd /c "dir /x <目录>"` 的短名列与长名列对照，不靠命名规律猜测。

报料者未给出故障签名采集命令与复测脚本，需复现确认。
