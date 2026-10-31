---
title: "ssh -t 和 heredoc 一起用，sudo 拿不到终端：a terminal is required to read the password"
domain: "devops"
tags:
  - "ssh"
  - "sudo"
  - "heredoc"
  - "tty"
  - "deployment"
  - "bash"
  - "nas"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4161"
summary_plain: "部署脚本里 `ssh host 'sudo ...'` 报 `sudo: a terminal is required to read the password; either use the -S…"
trigger: "ssh -t 和 heredoc 一起用，sudo 拿不到终端：a terminal is required to read the password. 部署脚本里 `ssh host 'sudo ...'` 报 `sudo: a terminal is required to read the password…"
verify: "脚本里 sudo 步骤能执行且不报 terminal 错误；`ssh -t host 'tty'` 返回 `/dev/pts/N`（不是 `not a tty`）。"
provenance:
  issue: "#4161"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

部署脚本里 `ssh host 'sudo ...'` 报 `sudo: a terminal is required to read the password; either use the -S option...`，脚本卡住或直接失败。

## Root Cause

`ssh ... bash -s <<EOF` 已经把 stdin 占给了 heredoc，ssh 拿不到本地终端；单个 `-t` 在这种情况下不分配伪终端（要 `-tt` 才强制分配，但那样 heredoc 的内容会被 sudo 当成密码读走）。

## Fix

把需要 sudo 的那条单独拎出来，用 `ssh -t` 且不重定向 stdin：

```bash
ssh -t host 'sudo systemctl restart bms' < /dev/null

## Verification

脚本里 sudo 步骤能执行且不报 terminal 错误；`ssh -t host 'tty'` 返回 `/dev/pts/N`（不是 `not a tty`）。
