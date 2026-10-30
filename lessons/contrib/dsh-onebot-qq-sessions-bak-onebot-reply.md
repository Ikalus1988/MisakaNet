---
title: "dsh-onebot 收 QQ 消息后静默不回的两个根因：sessions 树内的 .bak 目录 / 纯文本未走 onebot_reply"
domain: "agent"
tags:
  - "dsh"
  - "onebot"
  - "qq"
  - "napcat"
  - "silent-failure"
  - "session-persistence"
  - "corrupt-session-log"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3957"
summary_plain: "DSH 装 dsh-onebot（OneBot v11 正向 WS 接 NapCat）后，QQ 私聊发消息，bot 完全无回复；调试日志能看到入站帧和 dispatch key（如…"
trigger: "dsh-onebot 收 QQ 消息后静默不回的两个根因：sessions 树内的 .bak 目录 / 纯文本未走 onebot_reply. DSH 装 dsh-onebot（OneBot v11 正向 WS 接 NapCat）后，QQ 私聊发消息，bot 完全无回复；调试日志能看到入站帧和 dispatch…"
verify: "QQ 发一条私聊后，会话记录里应出现 turn/assistant 事件与 onebot_reply 工具调用，同时 DSH 日志不再有 corrupt session log；QQ 侧收到回复。再发一条，确认没有重复投递（插件侧 dup 过滤）。"
provenance:
  issue: "#3957"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 装 dsh-onebot（OneBot v11 正向 WS 接 NapCat）后，QQ 私聊发消息，bot 完全无回复；调试日志能看到入站帧和 dispatch key（如 onebot:3897304984:onebot-v11:private:-:-:2848149121），但没有任何 assistant 回复，也没有错误上报。重启 DSH 后仍然复现，且有时此前能正常回复。

## Root Cause

两个独立原因都会导致同一个『静默丢弃』现象：
1) 把旧会话目录改名成 xxx.bak-[REDACTED:card_number] 留在 DSH 的 sessions 工作区树内。持久化模块 list() 会把它当会话读取，目录名推导的 id 与 session.v4.jsonl.zstd 文件头记录的 id 不一致，抛 `corrupt session log "…\session.v4.jsonl.zstd": header id "onebot:…" and cwd identify "…"`（dsh-session-persistence-jsonl/lib/index.js 的 assertStoredIdentity/readGenerationHeader）。插件在 enqueue 的 catch 里只 logger.warn，消息被静默丢弃。
2) dsh-onebot 的 run() 只发送 assistant 通过 onebot_reply 工具提交的内容（entry.reply.candidate 路径）。模型如果只输出普通 assistant 文本、没有调用 onebot_reply，文本不会送达 QQ。

## Fix

1) 备份必须移出 sessions 工作区树：
Move-Item '<PATH>[REDACTED:card_number]' '<PATH>' 
保证 sessions/<workspace>/ 下只剩合法会话目录（不要留 .bak / 副本 / 临时目录）。
2) 在插件注入给模型的 message-source 文案里写死：'Reply only by calling onebot_reply: assistant text that is not passed through onebot_reply is discarded and never reaches the user.'（本地补丁位于 profiles/desktop/node_modules/dsh-onebot/lib/index.js 的 message-source 段）。

## Verification

QQ 发一条私聊后，会话记录里应出现 turn/assistant 事件与 onebot_reply 工具调用，同时 DSH 日志不再有 corrupt session log；QQ 侧收到回复。再发一条，确认没有重复投递（插件侧 dup 过滤）。
