---
title: "Windows 上把 DeepSeek Harness 工作区（<PATH><u>\\Documents\\deepseek-harness）搬到 D 盘后用 mk"
domain: "windows"
tags:
  - "windows"
  - "deepseek"
  - "harness"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4209"
summary_plain: "Windows 上把 DeepSeek Harness 工作区（<PATH><u>\\Documents\\deepseek-harness）搬到 D 盘后用 mklink /J 在原路径建 junction。"
trigger: "Windows 上把 DeepSeek Harness 工作区（<PATH><u>\\Documents\\deepseek-harness）搬到 D 盘后用 mk. Windows 上把 DeepSeek Harness 工作区（<PATH><u>\\Documents\\deepseek-harness）搬到 D…"
verify: "改完用 node 复验：①JSON.parse 成功且 path 读出正确；②fs.realpathSync(path) === 存入的 path 为 true；③对已登记每条会话把 header.cwd 走 realpathSync 后与 record.path 比对全部相等（否则老会话会被 get sessionIds() 过滤掉）。最后重启 DSH 确认能新建会话、正常发消息并产生…"
provenance:
  issue: "#4209"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上把 DeepSeek Harness 工作区（<PATH><u>\Documents\deepseek-harness）搬到 D 盘后用 mklink /J 在原路径建 junction。 旧会话仍能打开，但新建会话静默失败：会话目录能建、projcache 能生成，却没有 user/message 也没有 turn/start，storages\sessions\<id>.json 不存在，界面表现为"无法创建新会话"，日志无任何报错。

## Root Cause

根因：<PATH><u>\.dsh\storages\workspace.json 里 workspaces[<id>].path 存的是创建时的字面路径（C 盘）。

## Fix

改 workspace.json 里该工作区的 path，使其等于 fs.realpath 的结果（搬迁后的真实路径）。①node -e "console.log(require('fs').realpathSync('<PATH>\Users\\<u>\\Documents\\deepseek-harness\\default-workspace'))" 算准规范路径；②备份 workspace.json；③把 tables.workspaces[<id>].path 改成上一步输出（本例 <PATH> → <PATH> BOM 的 UTF-8 —— PowerShell 的 Set-Content -Encoding UTF8 会加 BOM，Node JSON.parse 报 Unexpected token '\uFEFF'，注册表读不出来；用 [System.IO.File]::WriteAllText($f,$txt,(New-Object System.Text.UTF8Encoding($false)))；⑤同步 D 侧副本；⑥重启 DSH 生效（registry 在 Service.init 读盘）。更稳的做法：不用 junction 搬工作区，直接给 profile 的 workspace-controller 设 documentsDirectory 指向新盘（该行 schema 有 documentsDirectory / documentsLookupTimeoutMs 两键），新会话从一开始就用规范路径。

## Verification

改完用 node 复验：①JSON.parse 成功且 path 读出正确；②fs.realpathSync(path) === 存入的 path 为 true；③对已登记每条会话把 header.cwd 走 realpathSync 后与 record.path 比对全部相等（否则老会话会被 get sessionIds() 过滤掉）。最后重启 DSH 确认能新建会话、正常发消息并产生 user/message 事件。
