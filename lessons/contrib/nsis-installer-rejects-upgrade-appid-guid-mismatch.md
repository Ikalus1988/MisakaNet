---
title: "NSIS Installer Refuses In-Place Upgrade When appId Differs from the Released Build"
domain: "windows"
tags:
  - "windows"
  - "nsis"
  - "electron-builder"
  - "appid"
  - "registry"
  - "installer"
  - "upgrade"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: '自己打的 Windows 安装包不肯覆盖旧版：打包用的 appId 和线上发行版不一致，注册表里的安装目录记录就对不上，安装器把原目录当成别人的。'
trigger: "请选择空文件夹 NSIS 覆盖升级 appId APP_GUID INSTALL_REGISTRY_KEY electron-builder 不一致"
verify: '从新包 resources/app.asar 的 package.json 读 dshDesktopAppId，算 UUID.v5(appId, "50e065bc-3134-11e6-9bab-38c9862bdaf3") 与 HKCU\Software\<guid> 实际键名相等；再在装旧版的机器上选原目录，应直接进入覆盖升级'
source: "intake-3093"
provenance:
  issue: "#3093"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Packing a Windows desktop app from source with **electron-builder + NSIS** produces an installer that refuses to overwrite an existing installation. The dialog (verbatim, application name interpolated):

```
请选择空文件夹，或 DeepSeek Harness 原来的安装目录。
```

That happens even when the user selects exactly the original install directory — which is, by construction, not empty. There is no way forward from the dialog, so a locally built installer cannot be used to upgrade a machine that already runs the released build.

The reporter's environment is the DSH desktop app's own source tree, which ships `.env.windows.example` — a template whose `DSH_DESKTOP_APP_ID` does not match the released build's appId.

## Root Cause

The pack-time `appId` differs from the released build's `appId`, and NSIS derives its install registry key from `appId`:

```
INSTALL_REGISTRY_KEY = "Software\${APP_GUID}"
APP_GUID             = UUID.v5(appId, <electron-builder's fixed NS UUID>)
```

A different `appId` yields a different GUID, so the installer looks under a key that no installation was ever recorded under. It finds no `InstallLocation`, cannot prove that the non-empty directory it was pointed at is its own, and therefore classifies it as **someone else's directory** and refuses.

This is a textbook trap in two specific ways:

- The source repository's own template is *a plausible-looking wrong value*. In this case `.env.windows.example` carried `com.deepseek.harness` while the released build is actually `com.deepseek.dsh`. Copying the template is the documented path, and it is the broken one.
- Nothing in the flow complains. The build succeeds, the installer is signed off as fine, and the failure only appears at install time on a machine that already had the app — the one machine you cannot easily reset.

Not given by the reporter — 报料者未给出，需复现确认: whether the fixed namespace UUID changes across electron-builder majors, and whether the dialog also appears for an all-users (per-machine, `HKLM`) install versus the per-user `HKCU` case that was diagnosed.

## Solution

Set `DSH_DESKTOP_APP_ID` in the local `.env.windows` to the same value the released build uses (`com.deepseek.dsh`). Do **not** copy it from `.env.windows.example` (`com.deepseek.harness`).

To find the right value, work backwards from a machine that already has the released build. Two methods, both given by the reporter:

1. **Reverse it from the installed registry key.** Compute the GUID from a candidate `appId` and compare it against the real key name under `HKCU\Software\<guid>\InstallLocation` (registry key names are compared case-insensitively):

```js
const { v5: uuidv5 } = require('uuid');
const NS = '50e065bc-3134-11e6-9bab-38c9862bdaf3';   // electron-builder's fixed NS UUID
const appId = process.argv[2];                         // candidate, e.g. com.deepseek.dsh
console.log(uuidv5(appId, NS));
```

```powershell
# list the install-location records that actually exist on this machine
Get-ChildItem 'HKCU:\Software' |
  Where-Object { Test-Path (Join-Path $_.PSPath 'InstallLocation') } |
  ForEach-Object { "$($_.PSChildName)`t$((Get-ItemProperty $_.PSPath).InstallLocation)" }
```

2. **Read it straight out of the installed app.** The shipped `package.json` carries a `dshDesktopAppId` field:

```js
const asar = require('@electron/asar');
const pkg = JSON.parse(
  asar.extractFile('<install-dir>/resources/app.asar', 'package.json').toString()
);
console.log(pkg.dshDesktopAppId);
```

Method 2 needs no candidate list and no GUID arithmetic, so prefer it when the old build is installed. Method 1 is what you need when all you have is a registry key and you must decide which `appId` produced it.

## Verification

Reporter's criteria, in order:

1. **Static match before installing anything.** Read `dshDesktopAppId` from `resources/app.asar` → `package.json` in the *new* build; compute `GUID = UUID.v5(appId, "50e065bc-3134-11e6-9bab-38c9862bdaf3")`; compare it with the existing installation's key name under `HKCU\Software\<guid>`. Equal is `MATCH`; not equal means the installer will refuse again.
2. **Behavioural check.** On a machine that already has the old version installed, run the new installer and select the original install directory. It must go straight into the in-place upgrade flow instead of showing `请选择空文件夹，或 … 原来的安装目录。`

Step 1 fails loudly and costs seconds; step 2 is the one that actually reproduces the user-visible symptom. Run both — step 1 alone will not tell you whether NSIS's own directory-recognition logic agrees with your GUID arithmetic.
