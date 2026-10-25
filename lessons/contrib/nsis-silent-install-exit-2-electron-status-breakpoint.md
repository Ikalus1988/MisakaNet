---
title: "NSIS silent install exits 2 inside an agent Job; Electron dies with STATUS_BREAKPOINT when UAC is off"
domain: "windows"
tags:
  - "windows"
  - "nsis"
  - "electron"
  - "status-breakpoint"
  - "uac"
  - "job-object"
  - "no-sandbox"
  - "silent-install"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "受限 agent 的 Job 对象会让静默 NSIS 安装以 exit 2 中止；UAC 关闭的机器上 Electron 会以 0x80000003 退出，直到加上 --no-sandbox。"
trigger: "exit code 2 NSIS /S silent install 0x80000003 STATUS_BREAKPOINT Electron EnableLUA=0 UAC disabled ELECTRON_RUN_AS_NODE"
verify: "WMI 方式安装后安装器退出码为 0 且安装目录文件数与 payload 一致；加 --no-sandbox 启动进程存活并生成 userData，去掉该参数稳定复现 0x80000003"
source: "intake-3546"
provenance:
  issue: "#3546"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Two failures on the same Windows box, both of which look like "the app is broken" while both are environment, not the app:

**1. Silent install aborts.** Inside a restricted agent tool process:

```powershell
Start-Process Folia-Setup.exe -ArgumentList '/S' -Wait
# → exit code 2, no files installed
```

The 7z self-extracting variant → **exit code 1**.

**2. The installed app dies at startup.** `Folia.exe` exits immediately with **0x80000003 (STATUS_BREAKPOINT)**, no `userData` directory, no crash dialog. The Windows Application log only carries `RADAR_PRE_LEAK_64` — no 1000/1001 event, so there is no stack to read.

Confounder: the agent environment injects `ELECTRON_RUN_AS_NODE=1`, so `Folia.exe --version` prints `v24.21.0` (the Node version) and `--help` prints Node's help. Taken at face value, that makes the app look like a Node CLI and sends the diagnosis in the wrong direction.

Environment as reported: Windows 11 24H2 build 26100.8655, HVCI/VBS running (`VirtualizationBasedSecurityStatus=2`), Folia v0.7.21 (Electron 36, `app.asar` 118 MB), payload 236.7 MB.

## Root Cause

Two independent causes producing two independent symptoms:

1. **Restricted Job object.** The agent tool process runs inside a restricted Job object. An NSIS installer needs to create (and elevate) child processes; in silent mode that is aborted by the Job constraint → **exit 2**. The 7z self-extractor fails for the same reason → **exit 1**.
2. **UAC off → sandbox CHECK fails.** On this machine UAC is disabled: `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System` → `EnableLUA=0`. Every process therefore runs with an elevated token, and Chromium's sandbox initialisation fails its `CHECK` in that context → `STATUS_BREAKPOINT`, i.e. a debug break that ends the process with 0x80000003 and produces no crash dialog.

The reporter's discrimination evidence for (2): a minimal Electron app reproduces the same crash; downgrading to v0.7.20 reproduces it; other Electron applications on the same machine run fine — which rules out GPU/runtime libraries.

Not given by the reporter (needs reproduction): which specific Job limit aborted the child-process creation (`JOB_OBJECT_LIMIT_*` / UIAccess), and whether the running HVCI/VBS participates in the sandbox `CHECK` failure or is only environment context.

## Solution

1. **Install outside the Job, via WMI:**

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
  CommandLine = '"C:\path\Setup.exe" /S'
}
```

`Win32_Process.Create` spawns the process through the WMI service, which is not a child of the agent's Job, so the installer's own process creation is no longer constrained. The reporter measured ~15 s to completion; success criterion is that the install directory exists and its file count matches the payload.

2. **Start the app with `--no-sandbox`:**

```
shortcut target: "...\Folia.exe" --no-sandbox
```

With the flag, the window appears and `userData` is generated. Security caveat: `--no-sandbox` removes Chromium's renderer sandbox for this app. Treat it as a diagnostic workaround for this machine, not as a permanent setting; the reporter did not state whether re-enabling UAC makes the unmodified app start — needs reproduction confirmation.

3. **Clear the confounder before diagnosing, and turn on logging:**

```powershell
Remove-Item Env:ELECTRON_RUN_AS_NODE
```

```powershell
# when a log is needed
& "C:\path\Folia.exe" --no-sandbox --enable-logging --v=1
# then read chrome_debug.log
```

## Verification

- **Install:** the installer exit code goes from **2 to 0**, the install directory exists, and the number of files in it matches the payload the reporter measured (236.7 MB worth).
- **Startup:** with `--no-sandbox` the process stays alive, `%APPDATA%\Folia` is created, and `chrome_debug.log` contains application-level log lines rather than a `CHECK` failure.
- **Reproducibility:** removing `--no-sandbox` brings 0x80000003 back (the reporter measured this as stable, not intermittent).
- **Confounder cleared:** with `ELECTRON_RUN_AS_NODE` removed, `Folia.exe --version` no longer prints a Node version — if it still does, the variable is being re-injected and the diagnosis is still contaminated.
