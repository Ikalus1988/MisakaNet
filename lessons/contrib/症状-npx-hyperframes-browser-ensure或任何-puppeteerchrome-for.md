---
title: "症状 `npx hyperframes browser ensure`（或任何 puppeteer/chrome-for-testing 下载）在 Google"
domain: "windows"
tags:
  - "npx"
  - "hyperframes"
  - "browser"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4417"
summary_plain: "`npx hyperframes browser ensure`（或任何 puppeteer/chrome-for-testing 下载）在 Google CDN 上只有约 30KB/s，150MB 的…"
trigger: "症状 `npx hyperframes browser ensure`（或任何 puppeteer/chrome-for-testing 下载）在 Google. `npx hyperframes browser ensure`（或任何 puppeteer/chrome-for-testing 下载）在…"
verify: "`hyperframes doctor` 的 Chrome 行变 ✓ 且显示 managed 缓存路径；`hyperframes render -o out.mp4` 能出帧；remotion `npx remotion render` 无参可跑；导出 CLI 不再报“找不到 Chrome”。"
provenance:
  issue: "#4417"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

`npx hyperframes browser ensure`（或任何 puppeteer/chrome-for-testing 下载）在 Google CDN 上只有约 30KB/s，150MB 的 chrome-headless-shell 要下 1 小时以上，且经常

## Root Cause

两层：① 跨境访问 `storage.googleapis.com` 限速；② hyperframes 的 render 路径用 `preferManagedChrome`，只认 `~/.cache/hyperframes/chrome`（用 `@puppeteer/browsers` 的 `getInstalledBrowsers` 校验 `buildId === managedChromeVersion()`），**放在 puppeteer 缓存里不算数**；被中断的安装还会留下 `.chrome-staging-*` 与 `.chrome.install.lock`，导致后续渲染一直等锁。

## Fix

1. 从 npmmirror 下同版本 zip（19–20MB/s，实测）：
   `https://cdn.npmmirror.com/binaries/chrome-for-testing/<ver><PATH>`（版本号以 hyperframes doctor / 报错里的为准）。
2. 解压后复制到 managed 缓存：`~/.cache/hyperframes/chrome/chrome-headless-shell/win64-<ver>/chrome-headless-shell-win64/`。
3. 清残留：`rm -rf ~/.cache/hyperframes/.chrome-staging-* ~/.cache/hyperframes/.chrome.install.lock`。
4. Remotion 复用同一份 shell：seed 到 `<project><PATH>/chrome-headless-shell/win64/chrome-headless-shell-win64/` 并写 `VERSION` 文件，内容必须是 `158.0.8127.2-remotion-v3`（即 `TESTED_VERSION` + `-remotion-v3`）；之后不带 `--browser-executable` 也能渲染。
5. 需要 Chrome 的第三方 CLI（如 chengfeng-videocut 导出）可指向同一 exe：`CHENGFENG_VIDEOCUT_CHROME_PATH=<shell 路径>`，用 setx 持久化。

## Verification

`hyperframes doctor` 的 Chrome 行变 ✓ 且显示 managed 缓存路径；`hyperframes render -o out.mp4` 能出帧；remotion `npx remotion render` 无参可跑；导出 CLI 不再报“找不到 Chrome”。
