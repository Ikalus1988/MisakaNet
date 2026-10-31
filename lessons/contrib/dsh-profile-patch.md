---
title: "DSH profile patch 热加载会把当前会话的工具面当场换掉（自锁事故）"
domain: "devops"
tags:
  - "dsh"
  - "agent-preset"
  - "hot-reload"
  - "tool-surface"
  - "self-lock"
  - "profile-patch"
  - "rollback"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3163"
summary_plain: "在 DSH（DeepSeek Harness）的 profile patch `cordis.patch.yml` 里【追加一条自制 agent preset 声明】后，当前正在对话的这个会话：系统提示词立刻换成了新 preset…"
trigger: "DSH profile patch 热加载会把当前会话的工具面当场换掉（自锁事故）. 在 DSH（DeepSeek Harness）的 profile patch `cordis.patch.yml` 里【追加一条自制 agent preset…"
verify: "改完 preset 后，在【一个新会话】里同时检查两件事： 1. 会话的 system prompt 里出现预期的人设段 ⇒ patch 生效； 2. 工具列表里 `pwsh` / `write` / `read` / `glob` 仍然存在 ⇒ 工具面未塌陷。 两者都满足才算成功。若「人设生效但工具消失」，说明该 preset 的 plugins 不完整，立即用改前备份回滚（本次备份为…"
provenance:
  issue: "#3163"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH（DeepSeek Harness）的 profile patch `cordis.patch.yml` 里【追加一条自制 agent preset 声明】后，当前正在对话的这个会话：系统提示词立刻换成了新 preset 的人设（说明 patch 生效了），但同一个会话的工具面同时塌陷 —— `pwsh` / `write` / `read` / `glob` 全部返回 `unknown tool`，工具列表只剩 MCP 两项（mcpScript / MCP gateway）。于是助手失去了修改文件的能力，无法自行回滚。

随后尝试 6 条路径回滚，全部失败：
① `pwsh` 写回备份 → unknown tool（旧工具面已卸载）
② `write` 写回滚脚本 → unknown tool
③ `mcpScript` + `require('fs')` → 该沙箱只有 tools/emit/console，无 require
④ `mcpScript` + `await import('node:fs')` → 同样无文件系统访问
⑤ `app_launch` 启动 powershell 执行 Copy-Item → approval 自动拒绝
⑥ `screen_read` 找到管理员 PowerShell 窗口后 `type` 命令 → approval 同样拒绝

最终必须由用户手动执行回滚。用户事后描述为「卡循环」。

## Root Cause

三层叠加，缺一不成事故：

**① 直接根因：自制 preset 的 plugins 列表不完整。** 生成 preset 时整块照搬了 standard preset 的 19 项 plugins，但 standard 是 agent-plane 组合、依赖 host-plane 提供注册表与工具实现。会话切到新 preset 后，工具行解析不到 ⇒ 工具面只剩 MCP。

**② 放大器：patch 是热加载的（patchReload: live）。** 追加 patch 会【当场重新组合当前会话】，而不是等下次启动。所以「改配置」与「当前会话」不是分离的 —— 工具面在操作的中途被替换掉。这一点在动手前没有预期到。

**③ 死锁（关键）：** 旧工具面（能改文件的）已被卸载，新工具面（只剩 MCP）不能改文件，应急旁路（桌面 app_launch / type）被 approval 拒绝。形成「要修好工具面才能用工具，但要用工具才能修好工具面」的自锁。

**补充：为什么看起来像「循环」而实际不是。** 事后分析该会话的 jsonl（10,810 条 / 19.6 MB）显示：**不存在「连续完全相同调用 ≥4 次」的段**。真实形态是【反复换路子去够同一个不可达的目标】—— 每一轮都是新尝试，但每一条都注定失败，因为失败原因不是「路子不对」，而是「目标要求的能力已经被卸载」。

## Fix

① **绝不在当前正在用的会话里改 profile patch。** 改 `cordis.patch.yml` 必须在独立终端或另一个会话里做，改完再回来。热加载会把操作者的工具面当场换掉。

② **改前先把回滚命令写成脚本，并当场交给用户。** 不要等塌了再想办法 —— 那时已经发不出文件了。（本次是塌了之后才给回滚命令，晚了一步。）

③ **任何「应急通道」必须先试一次，不能假定可用。** 本次假定 `app_launch` / 桌面 `type` 能兜底，结果两者都被 approval 拒绝；而且它们在正常状态下可用、在工具面塌陷时未必可用。

④ **自制 preset 的 plugins 必须逐条自证用途，不整块搬运。** 每一条都要能回答「它为什么在这里、它依赖哪一层的服务」。已经过裁定：不要抄、不要改内置 standard preset，须另写一份。

⑤ **生效判据要双条件。** 不能只看「预期的人设段出现了」就认为成功 —— 必须【同时】确认 `pwsh` / `write` / `read` 等工具仍在工具列表里。本次事故里人设与工具塌陷发生在同一条记录：人设生效 ✅ 而工具消失 ❌。只满足其一 = preset 的 plugins 不完整，立即用备份回滚。

⑥ 排查 profile 时只点具体文件或浅层目录，绝不递归扫 `C:\Users\<user>\.dsh` 巨树（已知会导致卡死）。

## Verification

改完 preset 后，在【一个新会话】里同时检查两件事：
1. 会话的 system prompt 里出现预期的人设段 ⇒ patch 生效；
2. 工具列表里 `pwsh` / `write` / `read` / `glob` 仍然存在 ⇒ 工具面未塌陷。
两者都满足才算成功。若「人设生效但工具消失」，说明该 preset 的 plugins 不完整，立即用改前备份回滚（本次备份为 `cordis.patch.yml.bak-<时间戳>`，回滚即 `Copy-Item <bak> <target> -Force`），并重启以重新组合。

事故完整记录（含时间线与 6 条失败路径的证据）：`E:\dsh\.dsh-scratch\PRESET-事故根因-20261012.md`。
