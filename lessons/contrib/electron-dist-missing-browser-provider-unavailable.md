---
title: "Browser provider unavailable: the electron package is installed without its dist/ binary"
domain: "dsh"
tags:
  - "electron"
  - "browser-provider"
  - "postinstall"
  - "electron-mirror"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Electron 包装上了但 dist/ 里的二进制没下载下来，DSH 的浏览器能力提供者因此报告不可用。"
trigger: "no usable browser provider is registered; electron dist missing path.txt"
verify: "available() 返回 true，且真实 spawn 后打印 READY OK - Electron child spawned and authenticated"
source: "intake-2535"
provenance:
  issue: "#2535"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Browser provider unavailable: the electron package is installed without its dist/ binary

## Problem

DSH Desktop 2.0.15（core 0.1.7-rc.2，profile `desktop`）对每一个 `browser_*` 工具都报
"no usable browser provider is registered"，而注册该 provider 的插件 `dsh-builtin-browser`
已经安装、并且在宿主日志里没有任何错误地加载了。它自己的探针返回 `false`。

Reporter's error line:

```
no usable browser provider is registered; available() === false; dsh-builtin-browser: cannot locate a spawnable Electron binary
```

插件是好的，环境不是——这是本课要区分的第一件事。

## Root Cause

npm 的 `electron` 包在 tarball 里**不带二进制**：`install.js`（postinstall）才把它下载进 `dist/`。
这台机器上 hosts 文件把 `github.com` / `objects.githubusercontent.com` 映射到 `127.0.0.1`，那次下载
静默失败，留下的是一个纯 JS 的壳：

```
<profile>/node_modules/electron/  (44.4.5)
  abi_version  checksums.json  cli.js  electron.d.ts
  index.js     install.js      LICENSE  package.json  README.md
  ← no dist/, no path.txt
```

（报料者列出的就是这 9 个文件，`dist/` 与 `path.txt` 都不在其中。）

`RemoteElectronViewHost.available()`（`lib/browser-electron/remote-host.js:682`）调用
`resolveElectronPath()`，后者只看文件系统，并且只有当 `electronDistExe(pkgRoot)` 存在时才把该包算作
候选。没有 `dist/electron.exe` ⇒ provider 报不可用。这条链路里没有任何一步会去检查"下载是否曾经
失败"，所以错误信息指向 provider，而故障在安装阶段。

## Solution

拿可达的镜像重跑这个包**自己的**安装器：

```powershell
cd <profile>/node_modules/electron
$env:ELECTRON_MIRROR = 'https://registry.npmmirror.com/-/binary/electron/'
node install.js
```

结果：`dist/electron.exe`（v44.4.5，246,032,896 字节）和 `path.txt`（内容为 `electron.exe`）。

**不要**用 `dsh plugin add electron` 或重装插件来"修"它：两者都会重跑那个已经失败的 postinstall，
再次把 `dist/` 丢掉。

provider 自己的错误信息里还给了两个替代路径：`npx install-electron`，或者用 `ELECTRON_PATH` 直接
指向一个 `electron.exe`。

## Verification

1. 探针返回 true：

```js
new RemoteElectronViewHost(defaultHostMainPath()).available()   // → true
```

2. 走生产路径真实 spawn 一个子进程，它要完成带认证的 hello：

```
READY OK in 1348ms - Electron child spawned and authenticated
```

3. 端到端：`createView()` → `presentView()` → `sendCommand('Page.navigate', {url})` →
   `capture()` 返回一张真实渲染的 489 KB PNG，`Runtime.evaluate` 能读回 `document.title`。

The reporter's stated criteria, verbatim:

```
available() -> true; a real spawn through the production path completed the child's authenticated hello
```

一个容易误判的边界：在沙箱 shell 里用 piped stdio 去 spawn 那个子进程会报 `spawn EPERM`——那是
沙箱，不是 provider；探针要在非沙箱环境里跑。

## Notes

- 报料者未给出 hosts 文件的具体条目、Electron 的确切安装时间，以及 DSH Desktop 的完整日志——需复现
  确认。本课的路径已脱敏为 `<profile>`。
- 这类"包在、二进制不在"的静默安装失败不只发生在 Electron：任何 postinstall 下载二进制的包（
  `esbuild`、`sharp`、`puppeteer` 等）在下载被墙或 hosts 被劫持时都会留下一个可导入但没有本体的壳。
  判据始终是"二进制文件是否存在"，不是 `npm ls` 是否报错。
- 与 NSIS/electron-builder 的 TLS/镜像类课程相邻但不同：那两篇是**构建安装包**时失败，这一篇是
  运行时依赖的包**安装**失败。
