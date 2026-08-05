---
title: "虫群记忆系统——三方案对比与选型"
domain: devops
source: opus4.6
created: 2026-04-21
status: reference
related_lessons:
  - "agent-medici-project-state"
---

# 虫群记忆系统——三方案对比与选型

## 需求描述

> 飞书群"塔罗会"有 7 个成员节点（倒吊人/太阳/魔术师/审判/正义/世界/愚者），
> 倒吊人已建立原始的 Gbrain 向量系统。需要建立统一的虫群记忆系统，
> 所有节点的技能经验和踩坑记录可以跨节点共享。

## Opus 4.6 规划步骤

1. 调研 GitHub 上 9 个主流记忆框架（Mem0/Letta/Cognee/Graphiti/ChromaDB/Qdrant/Redis 等）
2. 综合评星、文档完整度、与现有架构适配度筛选
3. 按从轻量到完整排序，给出三个方案
4. 每个方案含：核心架构 + 部署成本 + 适配改动量 + 风险

## 三方案对比

调研完毕。给出三个方案，从最轻量到最完整排序：

---

## 审判的回复——虫群记忆三方案

> 调研来源：GitHub 9个主流框架（Mem0/Letta/Cognee/Graphiti/ChromaDB/Qdrant/Redis等），综合评星、文档完整度、与塔罗会现有架构的适配度筛选。

---

### 方案一：ChromaDB Server + 飞书多维表事件通知
**定位：最轻量，倒吊人 Gbrain 最小改动迁移**

**GitHub:** `chroma-core/chroma` ⭐27.6k | Apache 2.0

**核心架构：**
```
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
```

**Gbrain 迁移成本：**
倒吊人只需把 Gbrain 的 `PersistentClient` 换成 `HttpClient("http://localhost:8000")`，其余代码不变。

**云端机器人（正义/世界）接入：**
通过 Cloudflare Tunnel 或 Tailscale 把 WSL2 的 8000 端口暴露出去，飞书 aily 用 HTTP 工具节点直接调用。

**同步延迟：** 写入即可读（毫秒级），轮询间隔由 cron 决定，设15分钟轻松达标。

**缺点：** 纯向量库，记忆提炼/去重/冲突解决需要自己写逻辑。

---

### 方案二：Mem0 自托管（mem0ai/mem0）
**定位：最适配，开箱即用的多 Agent 记忆层**

**GitHub:** `mem0ai/mem0` ⭐53.7k | Apache 2.0

**核心架构：**
```
[中枢，部署在太阳/魔术师 WSL2]
Docker Compose:
  ├─ mem0-server  :8080   ← 统一记忆 API
  ├─ qdrant       :6333   ← 向量存储
  └─ (可选) neo4j :7474   ← 知识图谱

[任意 bot 写入技能]
POST http://中枢IP:8080/v1/memories/
{
  "messages": [{"role":"user","content":"<新技能描述>"}],
  "agent_id": "魔术师",
  "metadata": {"type": "skill", "topic": "飞书API操作"}
}

[任意 bot 查询]
POST /v1/memories/search/
{"query": "飞书多维表格操作", "agent_id": "all"}

[云端机器人：正义/世界]
飞书 aily HTTP 工具节点 → 直接 POST/GET 中枢地址
```

**与塔罗会的对应：**

| Bot | 接入方式 | 成本 |
|-----|---------|------|
| 倒吊人(Windows qclaw) | HTTP REST | 零依赖 |
| 太阳/魔术师/审判(WSL2) | Python SDK / HTTP | 一行 pip |
| 正义/世界(飞书 aily) | HTTP 工具节点 | 配置 URL 即可 |

**关键优势：**
- 原生支持 `agent_id` 标签，查询时可按来源过滤
- 自带 LLM 辅助的记忆提炼（相似技能自动合并，避免冗余）
- 写入即全局可读，实际同步 <1 秒，远超30分钟要求

**一键部署（太阳/魔术师 WSL2 执行）：**
```bash
git clone https://github.com/mem0ai/mem0
cd mem0/server
docker-compose up -d
```

**缺点：** 记忆提炼步骤需要消耗 LLM API（每次 add 一次调用），需要接 OpenAI 或 Anthropic Key。

---

### 方案三：Cognee（认知图谱 + 原生 Claude Code / Hermes 集成）
**定位：最完整，支持知识推理和自动关联，与审判/魔术师原生整合**

**GitHub:** `topoteretes/cognee` ⭐16.6k | Apache 2.0

**核心架构：**
```
ECL Pipeline（Extract → Cognify → Load）:
  任意 bot 调用 cognee.add(text, dataset_name="tarot_skills")
    ↓
  LLM 自动提炼知识节点 + 关系边
    ↓
  Neo4j 图谱 + Qdrant 向量双存储
    ↓
  任意 bot 查询：cognee.search("如何操作飞书多维表格")
    → 向量语义 + 图谱关联 混合结果
```

**与塔罗会的特殊适配：**

审判（claude-code）原生支持通过 MCP hook 自动写入记忆——
每次 PostToolUse / SessionStart 时自动触发：
```json
// .claude/settings.json (审判本地)
{
  "mcpServers": {
    "cognee": {
      "command": "uvx",
      "args": ["cognee-mcp"]
    }
  }
}
```

魔术师（Hermes）同样有官方 Cognee 适配器，直接作为 memory provider 接入。

**知识图谱优势（其他方案没有的）：**
- 技能之间的关联关系自动建立（"飞书API操作"→"多维表格"→"数据聚合"）
- 矛盾检测：两个 bot 写入相互矛盾的经验，Cognify 会标记冲突
- 时序追踪：知识随时间演进的轨迹可查

**云端机器人（正义/世界）接入：**
```bash
cognee serve  # 启动 HTTP 服务
```
aily 通过 REST API 调用 `/api/v1/add` 和 `/api/v1/search`。

**缺点：** 需要 Neo4j（额外基础设施），Cognify 步骤有 LLM 调用延迟（数秒），配置比方案一复杂。

---

## 三方案对比

| | 方案一 ChromaDB | 方案二 Mem0 | 方案三 Cognee |
|--|--|--|--|
| 部署复杂度 | ★☆☆ 最低 | ★★☆ 中等 | ★★★ 较高 |
| 与 Gbrain 兼容 | 直接迁移 | 需适配 | 需重写 |
| 同步延迟 | <1s（写即可读） | <1s | <1s |
| 云端 bot 接入 | HTTP 暴露即可 | 同左 | 同左 |
| 知识推理能力 | 无 | 中（去重合并） | 强（图谱关联+矛盾检测） |
| LLM 消耗 | 无 | 每次 add 1次 | 每次 add N次 |
| Claude Code 原生集成 | 无 | 无 | MCP hook 原生 |

---

## 审判建议

**短期（本周）：** 方案一——让倒吊人先把 Gbrain 迁移到 ChromaDB Server，验证全链路文件可达性。成本最低，30分钟内可以有一个跑通的原型。

**中期（本月）：** 方案二 Mem0 替换 ChromaDB 作为记忆层，加入 LLM 辅助的记忆提炼，让技能同步更"智能"而不是原始文本堆积。

**长期（规划中）：** 方案三 Cognee 作为最终形态，审判+魔术师通过 MCP 自动积累经验，形成塔罗会共享知识图谱——即愚者说的"自成长"和"自省"能力。

## 上下文依赖

- 现有节点：7 个（Windows/WSL/云托管混合）
- 已有基础设施：倒吊人 Gbrain（原始向量系统）
- 通信方式：飞书群
- 网络条件：各节点网络环境不同（部分需代理）
