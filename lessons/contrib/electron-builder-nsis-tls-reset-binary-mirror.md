---
title: "electron-builder NSIS Packaging Dies on a TLS Reset While Downloading Its Binaries"
domain: "network"
tags:
  - "electron-builder"
  - "nsis"
  - "windows"
  - "tls"
  - "mirror"
  - "build-cache"
  - "download"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: '打包到一半卡在下载 NSIS/7-Zip 工具，TLS 连接被掐断；把下载镜像和缓存目录挪到别处再跑同一条命令就过了。'
trigger: "Client network socket disconnected before secure TLS connection was established failedTask=build stackTrace=RequestError electron-builder"
verify: '导出 ELECTRON_BUILDER_BINARIES_MIRROR 与 ELECTRON_BUILDER_CACHE 后重跑同一条打包命令，退出码 0 且生成安装包与其 blockmap；若仍报 RequestError，说明镜像变量未生效（别误设成 ELECTRON_CACHE）'
source: "intake-3089"
provenance:
  issue: "#3089"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Windows x64 host, building an unsigned NSIS installer from source. electron-builder fails **intermittently** while downloading the NSIS / 7-Zip helper binaries:

```
⨯ Client network socket disconnected before secure TLS connection was established  failedTask=build stackTrace=RequestError
```

The error is a `RequestError` from `got`, and it arrives **after the app directory has already been assembled** — so the expensive build stages are already paid for when the run dies. Retrying the whole packaging sequence re-does every one of them.

The failure is a transient TLS reset against the GitHub release assets electron-builder fetches, not a configuration error: the same command, unchanged, can succeed on another attempt.

## Root Cause

electron-builder downloads its own helper binaries (NSIS, 7-Zip, and the other `electron-builder-binaries` assets) on first use or on a cache miss. On this host the outbound TLS handshake to the asset host is closed before it completes — `Client network socket disconnected before secure TLS connection was established` — which is a connection-layer reset, not a 404 and not a malformed URL.

Two properties of the failure make it expensive rather than merely annoying:

- **It is stage-late.** The download sits after packaging has assembled the app directory, so each failed attempt discards minutes of work.
- **It is not probeable.** A single HEAD request is not conclusive. The reporter checked that the download host answers HEAD requests and got `fetch failed` from one target and `200` from another — which tells you the *host* can answer, not that the *download path* will survive a multi-megabyte transfer.

One honesty note about the fix below: the reporter changed two variables at once (mirror **and** cache location), so which one was strictly necessary is not established. Not given by the reporter — 报料者未给出，需复现确认: which of the two caused the pass, and which exact asset host reset the handshake (`github.com` release redirect vs `objects.githubusercontent.com`).

## Solution

Point electron-builder's binary downloads at a mirror, and move its cache off the system drive (onto a path with free space). Then re-run the **identical** packaging command — nothing else changes:

```powershell
# ① 指向 electron-builder-binaries 镜像
#    npmmirror 在 /-/binary/electron-builder-binaries/ 下发布了一份
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://registry.npmmirror.com/-/binary/electron-builder-binaries/"

# ② 把缓存挪到有空闲空间的盘
$env:ELECTRON_BUILDER_CACHE = "D:\eb-cache"

# ③ 原样重跑打包命令
```

Persist both variables in the shell profile of the build machine (or in the CI environment) rather than exporting them per run — the failure mode is intermittent, so it will only bite the build you were not watching.

The variable name that actually matters here is `ELECTRON_BUILDER_BINARIES_MIRROR`. Do not substitute `ELECTRON_CACHE`: that one covers only the Electron distribution itself, and an Electron download that works while NSIS still fails looks like the mirror "not working" when it was never applied to the failing download.

## Verification

Re-run the identical packaging command with the mirror and cache variables exported. Pass criteria, as reported:

- the run passes the previously failing download step and exits **0**;
- it produces the installer **and** its blockmap;
- the packaging run record reports success.

A useful negative check: if the `RequestError` comes back on the very next run with both variables set, the mirror did not take effect — confirm you exported `ELECTRON_BUILDER_BINARIES_MIRROR` (not `ELECTRON_CACHE`) in the same shell that runs the packaging command, because a stale cache directory will also keep serving a half-downloaded asset.

Not given by the reporter — 报料者未给出，需复现确认: whether clearing `ELECTRON_BUILDER_CACHE` alone before the run would also have passed (i.e. whether the mirror was necessary at all).
