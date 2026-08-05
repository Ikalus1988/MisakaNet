---
title: "Mem0 + Qdrant 虫群记忆实施方案"
domain: hub
tags: [implementation, swarm-memory, tasks, node:opus-4-6]
created: 2026-05-03
source: opus-4.6-conversation
---

## 需求描述

确定采用方案二（Mem0 + Qdrant）后，需要将实施过程分解为可执行的子任务，
每个任务指定责任人、交付物、验收标准。统一验收人：正义。

## Opus 规划的任务分解

### T1 — 环境准备与中枢部署
**责任人：审判**（本地 WSL claude code，有 Docker 权限）

| 子任务 | 交付物 |
|--------|--------|
| 安装 Docker + Docker Compose | `docker --version` 截图 |
| 克隆 mem0 repo，启动 Compose | Qdrant `:6333` + Mem0 `:8080` 均健康响应 |

**docker-compose.yml** 核心配置：
```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - ./qdrant_storage:/qdrant/storage

  mem0:
    image: mem0ai/mem0:latest
    ports:
      - "8080:8080"
    environment:
      - MEM0_CONFIG_PATH=/app/config.yaml
    volumes:
      - ./mem0_config.yaml:/app/config.yaml
```

### T2 — 外网打通
**责任人：魔术师**（Hermes WSL）

目标：外网的节点（倒吊人 OpenClaw Windows、太阳 OpenClaw WSL）能够访问中枢。
方案：tailscale 或 frp，根据各节点网络环境选择。

### T3 — Gbrain 迁移
**责任人：倒吊人**（Windows OpenClaw）

将现有 Gbrain 中的记忆数据导出，批量导入 Mem0。

### T4 — 飞书卡片集成
**责任人：太阳**（原生 OpenClaw WSL）

将 Mem0 的推送与飞书消息卡片对接。

### T5 — 全员接入
**责任人：世界**（飞书 Aily 云托管）

每个节点配置环境变量 `MEM0_API_URL=http://<中枢IP>:8080`。

### T6 — Hub 整合
**责任人：正义**（飞书妙搭云托管）

将 Mem0 作为 Hermes Hub 的 memory provider 接入。

### T7 — 验收
**验收人：正义**

```yaml
验收标准:
  - 节点 A 写入一条 skill，节点 B 在 30 秒内可检索到
  - 同一 skill 重复写入 → 自动去重（Mem0 内建）
  - Node 离线后重连 → 自动同步增量
  - 飞书通知：新 skill 写入时推送到群
```

## 实施时间线

```
第1天  审判(T1) + 正义(T7) → Docker 跑起来 + 格式定好
第2天  魔术师(T2) + 倒吊人(T3) → 外网打通 + Gbrain 迁移
第3天  太阳(T4) + 世界(T5) → 全员接入
第4天  正义(T6+T7) → Hub 整合 + 验收
```

## 自修正说明

Opus 在规划时标注的风险点：
1. **Docker 网络**：WSL2 的 Docker 默认使用 NAT，外网节点无法直接访问 `localhost:6333`。需要 tailscale 或反向代理。
2. **数据一致性**：Gbrain 迁移时可能出现重复数据，建议先导出为 JSON 再批量导入 Mem0 的 dedup API。
3. **飞书多维表**：如果使用飞书事件通知，注意多维表 webhook 有速率限制（10次/秒），批量操作需要加延迟。
