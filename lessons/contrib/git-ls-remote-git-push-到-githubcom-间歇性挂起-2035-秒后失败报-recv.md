---
title: "`git ls-remote` / `git push` 到 github.com 间歇性挂起 20–35 秒后失败，报 `Recv failure: Conn"
domain: "dsh"
tags:
  - "git"
  - "http.sslbackend-openssl"
  - "schannel"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4985"
summary_plain: "`git ls-remote` / `git push` 到 github.com 间歇性挂起 20–35 秒后失败，报 `Recv failure: Connection was reset` 或 `Failed to connect…"
trigger: "`git ls-remote` / `git push` 到 github.com 间歇性挂起 20–35 秒后失败，报 `Recv failure: Conn. Connection was reset` 或 `Failed to connect to github.com port 443 after N…"
verify: "连续执行 4 次 `git ls-remote <repo> HEAD` 并统计成功率，同时在同一时段用 Node fetch 请求 `https://github.com/` 作对照。若 Node 正常而 git 出现 20–35 秒挂起，即命中此失败模式；若重试后 exit code 0 且耗时约 1 秒，说明本次已恢复。 **Matched lesson (not helpful):**…"
provenance:
  issue: "#4985"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

`git ls-remote` / `git push` 到 github.com 间歇性挂起 20–35 秒后失败，报 `Recv failure: Connection was reset` 或 `Failed to connect to github.com port 443 after N ms`；重试数次后可成功。同一台机器、同一时刻，Node.js 的 fetch 请求同一域名稳定返回 200（约 350ms）。

## Root Cause

未确认。现象是「连接建立后挂起约 20–35 秒再超时」，且只出现在 git 的 libcurl 传输路径上，Node 的 TLS 客户端在同一时刻不受影响。怀疑是该链路对特定握手表征或长连接的定向丢包，但未抓包，无法定论。

## Fix

重试。实测 2–6 次内通常成功。成功时耗时约 1.1 秒，失败时固定 20–35 秒，因此可据此设超时并快速重试，不必等满整个超时窗口。

注意：网络上流传的「把 github.com 钉到 140.82.112.x 等老 IP」方案在本环境下全部不可用（0/3、0/3、1/3），换地区即失效，不要盲目套用。

## Verification

连续执行 4 次 `git ls-remote <repo> HEAD` 并统计成功率，同时在同一时段用 Node fetch 请求 `https://github.com/` 作对照。若 Node 正常而 git 出现 20–35 秒挂起，即命中此失败模式；若重试后 exit code 0 且耗时约 1 秒，说明本次已恢复。

**Matched lesson (not helpful):** `github-dns-443-block-hosts-workaround`
