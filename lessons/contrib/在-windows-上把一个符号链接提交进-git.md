---
title: "在 Windows 上把一个符号链接提交进 git 仓，而这个链接的目标里写的是**未展开的变量**（例如字面量 \"$HOME/.hermes/skills/x"
domain: "windows"
tags:
  - "windows"
  - "git"
  - "home"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4184"
summary_plain: "在 Windows 上把一个符号链接提交进 git 仓，而这个链接的目标里写的是**未展开的变量**（例如字面量 \"$HOME/.hermes/skills/x/SKILL.md\"，想指向家目录下的真实路径），后果是整个仓库的 git…"
trigger: "在 Windows 上把一个符号链接提交进 git 仓，而这个链接的目标里写的是**未展开的变量**（例如字面量 \"$HOME/.hermes/skills/x. 在 Windows 上把一个符号链接提交进 git 仓，而这个链接的目标里写的是**未展开的变量**（例如字面量…"
verify: "对抗判据：git add -A 必须退出码 0 且不再出现 \"Invalid argument\"；git status --short 与 git diff 必须能正常输出（哪怕是空的）；任何 clone 到别的机器后，那个路径都必须是可读的真实文件而不是死链接。CI 侧判据：新规则加入后，\"当前树扫描\"对全部跟踪文件 0 命中，\"历史扫描\"限定范围后同样 0 命中。"
provenance:
  issue: "#4184"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

在 Windows 上把一个符号链接提交进 git 仓，而这个链接的目标里写的是**未展开的变量**（例如字面量 "$HOME/.hermes/skills/x/SKILL.md"，想指向家目录下的真实路径），后果是整个仓库的 git 操作被打死：git add -A 直接报 "error: open(...): Invalid argument / fatal: updating files failed"，git status / git diff 同样报错，任何自动化提交脚本（例如"git add -A && git commit"的同步工具）因此永久失败退出码 1。

## Root Cause

根因有两层：(1) 符号链接目标里的 $HOME **不会被任何一层展开**——它只是链接文本里的字面量，所以这个链接对任何 clone 都是死的；

## Fix

(2) git 在 Windows 上无法给这种链接做哈希，于是连索引都更新不了。 修法是把它换成一个普通的真实文件（指针 stub），内容说明"真实实体在哪、为什么在仓外、找不到找谁、被谁引用"。 附带一条同源的坑：git 的历史扫描（gitleaks git --all）扫的是**所有历史提交**，所以事后扩展一条更严的规则会把**旧历史里当时不算违规的内容**也报出来，直接把原本绿的 CI 弄红； 解法是把"当前树"和"历史"分成两步扫（当前树用 gitleaks dir . 全量零豁免，历史把范围限定在上一次全量重写之后）。

## Verification

对抗判据：git add -A 必须退出码 0 且不再出现 "Invalid argument"；git status --short 与 git diff 必须能正常输出（哪怕是空的）；任何 clone 到别的机器后，那个路径都必须是可读的真实文件而不是死链接。CI 侧判据：新规则加入后，"当前树扫描"对全部跟踪文件 0 命中，"历史扫描"限定范围后同样 0 命中。
