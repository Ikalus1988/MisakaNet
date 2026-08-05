---
title: bootstrap 方案一 ChromaDB Server 飞书多维表事件通知 定位 最轻量 倒吊人 Gbr
domain: feishu
tags:
- source:bootstrap
source: bootstrap
status: draft
created: '2026-04-01'
confidence: 0.7
---

 方案一：ChromaDB Server + 飞书多维表事件通知 定位：最轻量，倒吊人 Gbr"
domain: rag
source: bootstrap
bootstrapped: true
author: node2
machine: hermes-wsl
original_date: "2026-04-21"
tags: ["node:hermes_wsl", "bootstrap", "project:edoc", "severity:low"]
status: active
quality: draft
session_file: 20260421_220437_45cbd031.jsonl
---
## 背景
[assistant] ✅ **魔术师任务完成**

| 项目 | 结果 |
|------|------|
| 表格权限 | bitable:app 已开通，读写正常 |
| 任务认领 | `recvhr3WxYw1Zt` → 执行中 → 已完成 |
| 向量系统状态 | edoc v4, 208,022 chunks, BGE-m3 + BM25 rerank |
| brain-repo | 尚未创建（正义阶段1进
[user] 我希望建立虫群记忆，或集群记忆，只要中枢机器人建立完整的向量记忆系统（如有更好方案可以不限于gbrain方案），至少实现有任一机器人习得skill或复盘到新的技能，全体机器人不需要立刻，在半小时内能完成同步升级，各位给出建议吧
[assistant] 好问题，这是塔罗会走向真正协作的关键跃迁。让我系统分析后给出建议。

**先说核心结论：方案可行，瓶颈不在技术，在文件可达性。**

---

## 当前障碍分析

| Bot | 平台 | 文件访问能力 |
|-----|------|------------|
| 太阳 | WSL OpenClaw | 本地文件 ✅ + Git ✅ |
| 魔术师 | WSL Hermes | 本地文件 ✅ 

## 用户描述
---
方案一：ChromaDB Server + 飞书多维表事件通知
定位：最轻量，倒吊人 Gbrain 最小改动迁移
GitHub: chroma-core/chroma ⭐27.6k | Apache 2.0
核心架构：
[倒吊人/太阳/魔术师 WSL2]
└─ Docker: chromadb server :8000
└─ 所有 bot 通过 HTTP 连同一个 collection
[技能写入触发]
bot 学到新 skill
→ chroma.upsert(skill_doc, metadata={agent_id, timestamp})
→ 同时写飞书多维表一行 {来源bot, skill_name, version, timestamp}
[其他 bot 同步]
aily-schedule / cron 每15分钟
→ 查多维表 WHERE last_sync < timestamp
→ 发现新行 → 从 chroma pull 对应向量
→ 本地缓存更新
Gbrain 迁移成本：
倒吊人只需把 Gbrain 的 PersistentClient 换成 HttpCl

## 助理回复
**方案一 + 方案二混合路径**

理由：

1. **验证优先** — 方案一30分钟可跑通，先让倒吊人迁移Gbrain到ChromaDB Server，验证全链路（WSL→云端→飞书）是否真的通
2. **成本可控** — 方案一零LLM消耗，先跑起来不花钱
3. **平滑升级** — 方案一验证通过后，ChromaDB可无缝迁移到Mem0（都是HTTP接口），只需加LLM API key即可获得去重能力
4. **方案三暂缓** — Cognee的Neo4j+图谱推理是最终形态，但当前塔罗会连基础同步都没跑通，不宜一次性上太重

**行动建议**：

> 本周内倒吊人完成Gbrain→ChromaDB Server迁移，魔术师/太阳各启动一个本地chromadb实例互相同步，验证通过后再谈Mem0。

同意请确认，我来协调倒吊人开始。

