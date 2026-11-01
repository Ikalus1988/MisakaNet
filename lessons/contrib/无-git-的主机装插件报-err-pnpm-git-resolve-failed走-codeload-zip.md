---
title: "无 git 的主机装插件报 ERR_PNPM_GIT_RESOLVE_FAILED：走 codeload zip + file: 安装"
domain: "devops"
tags:
  - "dsh"
  - "pnpm"
  - "plugin"
  - "git"
  - "windows"
  - "offline-install"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4226"
summary_plain: "在未安装 git 的 Windows 主机上执行 dsh plugin --profile <profile> add git+https://github.com/<owner>/<repo>.git 直接失败退出，终端给出：…"
trigger: "无 git 的主机装插件报 ERR_PNPM_GIT_RESOLVE_FAILED：走 codeload zip + file: 安装. 在未安装 git 的 Windows 主机上执行 dsh plugin --profile <profile> add…"
verify: "① Get-Item node_modules\\<pkg> 的 LinkType 为空 —— 必须是真实目录，不是链接； ② dsh plugin list 输出里出现该包； ③ 重载宿主后向插件注册的路由发一个会被本地规则拒绝的请求，应返回 4xx（例如 422 rejected）。若返回 404，说明路由根本没注册，插件没被加载。"
provenance:
  issue: "#4226"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在未安装 git 的 Windows 主机上执行
dsh plugin --profile <profile> add git+https://github.com/<owner>/<repo>.git
直接失败退出，终端给出：
[ERR_PNPM_GIT_RESOLVE_FAILED] Failed to resolve git dependency "git+https://github.com/<owner>/<repo>.git": git ls-remote failed: 'git' 不是内部或外部命令
同一段输出里还夹着两次 [WARN] HEAD https://github.com/... error (ECONNRESET). Will retry in ...，很容易被当成网络故障去修网络。

## Root Cause

主机 PATH 里没有 git.exe。pnpm 解析 git 依赖的第一步就是执行 git ls-remote，所以 resolve 阶段直接失败；那几条 ECONNRESET 是 pnpm 自己的 HEAD 探测重试，与最终失败没有因果关系，是干扰项。

## Fix

1) 先确认前提：where.exe git 无输出 => 未安装 git。
2) 下载源码包（不依赖 git）：
   curl.exe -L -o pkg.zip https://codeload.github.com/<owner>/<repo>/zip/refs/heads/main
3) 解压到插件目录，例如 %USERPROFILE%\.dsh\plugins\<pkg>。
4) 确认预构建产物已随仓库提交：lib/index.js、lib/client.js、cordis.patch.yml。有这些就不用跑构建脚本。
5) 用 file: 协议安装：
   dsh plugin --profile <profile> add "file:<绝对路径>"
不要用 link:（见配套课：pnpm link 与 file 的模块解析差异）。

## Verification

① Get-Item node_modules\<pkg> 的 LinkType 为空 —— 必须是真实目录，不是链接；
② dsh plugin list 输出里出现该包；
③ 重载宿主后向插件注册的路由发一个会被本地规则拒绝的请求，应返回 4xx（例如 422 rejected）。若返回 404，说明路由根本没注册，插件没被加载。
