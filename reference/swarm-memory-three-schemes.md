---
title: "虫群记忆系统 — 三方案对比与选型"
domain: hub
tags: [architecture, swarm-memory, reference, node:opus-4-6]
created: 2026-05-03
source: opus-4.6-conversation
---

## 需求描述

塔罗会成员（愚者/倒吊人/正义/太阳/魔术师/审判/世界）分布在多个环境（WSL / Windows / 云端），
需要建立一个统一的虫群记忆系统，让各成员共享技能使用经验、踩坑记录和能力拓扑。

现有基座：倒吊人已建立简单记忆向量系统 Gbrain（很原始）。
需求：选择最合适的中枢记忆方案，实现全员同步。

## Opus 规划步骤

Opus 4.6 首先调研了 GitHub 上 9 个主流框架（Mem0/Letta/Cognee/Graphiti/ChromaDB/Qdrant/Redis等），
综合评星、文档完整度、与现有架构适配度，筛选出三个方案：

### 方案一：ChromaDB Server + 飞书多维表事件通知
**定位：最轻量，倒吊人 Gbrain 最小改动迁移**
**GitHub:** chroma-core/chroma ⭐27.6k | Apache 2.0

**核心架构：**
```yaml
components:
  vector_db: ChromaDB Server (chroma run --host 0.0.0.0 --port 8000)
  event_bus: 飞书多维表（事件通知 webhook）
  notification: 飞书消息卡片

data_flow:
  agent_creates_skill:
    - 写入 Gbrain（倒吊人侧）
    - 触发飞书多维表事件
    - Hub 通过 event webhook 收到通知
    - Hub 拉取新技能 → 索引 → 广播
```

**优势：**
- 已有 ChromaDB 使用经验（RAG 项目）
- 飞书多维表不需要额外部署
- 30 分钟内可出原型

**劣势：**
- 无跨 session 记忆关联
- 纯向量检索，无 LLM 辅助提炼

### 方案二：Mem0 + Qdrant 自托管
**定位：中等投入，方案一的自然升级**
**GitHub:** mem0ai/mem0 ⭐25.3k

**核心架构：**
```yaml
components:
  vector_db: Qdrant (docker, port 6333)
  memory_layer: Mem0 (docker, port 8080)
  notification: 飞书消息卡片

data_flow:
  agent_creates_skill:
    - 通过 Mem0 API 写入
    - Mem0 自动：
      1. 提取关键信息（LLM 辅助提炼）
      2. 生成 embedding → 存入 Qdrant
      3. 关联已有记忆（去重/合并）
    - Hub 收到 Mem0 webhook → 更新图谱
```

**优势：**
- 自动记忆提炼和关联
- 跨 session 记忆整合
- Docker 一键部署

**劣势：**
- 需要 Docker 环境（WSL 可行）
- 比方案一重

### 方案三：Cognee 端到端知识图谱
**定位：最完整，长期目标**
**GitHub:** tometchy/cognee ⭐3.2k

**核心架构：**
```yaml
components:
  graph_db: NetworkX / Neo4j
  vector_db: Qdrant / ChromaDB
  llm: 现有三通道 LLM
  memory_layer: Cognee pipeline

capabilities:
  - 实体识别与关系抽取
  - 知识图谱构建
  - 冲突检测与置信度计算
  - 记忆衰退与遗忘
```

**优势：**
- 知识图谱 = 虫群记忆的最终形态
- 冲突检测 + 置信度计算内建

**劣势：**
- 社区较小，文档不够成熟
- 与现有架构集成成本高

## 最终推荐（Opus 的决策逻辑）

```python
# 决策树逻辑
if 急需上线:
    方案一  # 30分钟原型
elif 有Docker环境:
    方案二  # 推荐，平衡投入与收益
else:
    方案三  # 长期规划
```

Opus 最终选择**方案二（Mem0 + Qdrant）**作为实施方向，
同时要求方案一作为保底（最快可跑通）。

## 上下文依赖

- 塔罗会成员分布：WSL Hermes × 2 + cc-haha + OpenClaw + 云 Agent × 2
- 现有基础设施：ChromaDB + 飞书 webhook + GitHub Issues
- 约束条件：不引入新的外部依赖，所有组件可自托管
