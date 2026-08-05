---
title: "Mem0 + Qdrant 方案执行清单"
domain: devops
source: opus4.6
created: 2026-04-21
status: reference
related_lessons:
  - "agent-medici-project-state"
---

# Mem0 + Qdrant 方案执行清单

## 需求描述

> 确认执行方案二（Mem0 + Qdrant 自托管），
> 需要合理的任务清单、责任人、交付物，
> 验收人统一为正义（云托管节点）。

## Opus 4.6 规划步骤

1. 拆解为 4 个大任务：环境部署 → 节点接入 → 技能同步 → 验收
2. 每个任务指定责任人（按节点能力分配）
3. 每个子任务有明确交付物（可验证）
4. 验收统一由正义执行

## 任务清单

## 方案二执行任务清单

**目标：** Mem0 + Qdrant 自托管，全员30分钟内技能同步
**验收人：** 正义（所有任务交付物均提交给正义验收）

---

### T1 — 环境准备与中枢部署
**责任人：审判**（本地 WSL claude code，有 Docker 权限）

| 子任务 | 交付物 |
|--------|--------|
| 安装 Docker + Docker Compose | `docker --version` 截图 |
| 克隆 mem0 repo，启动 Compose | Qdrant :6333 + Mem0 :8080 均健康响应 |
| 配置 LLM Key（Anthropic / OpenAI） | `POST /v1/memories/` 写入测试通过 |
| 写 `docker-compose.yml` 并提交到共享目录 | `/mnt/d/TarotBrain/infra/docker-compose.yml` |

**验收标准：** 正义通过 HTTP 能调通 `GET http://[中枢IP]:8080/health`

---

### T2 — 外网访问打通
**责任人：魔术师**（本地 WSL Hermes，负责网络配置）

| 子任务 | 交付物 |
|--------|--------|
| 配置 Cloudflare Tunnel 或 Tailscale | 中枢可通过公网/内网域名访问 |
| 测试正义/世界从飞书云侧能否 ping 通 | 正义 aily HTTP节点测试截图 |
| 记录最终访问地址 | 写入协作表「系统配置」行 |

**验收标准：** 正义在飞书 aily 中用 HTTP 工具节点 POST `[域名]/v1/memories/` 返回 200

---

### T3 — 技能写入规范定义
**责任人：愚者**（项目发起人，定义数据格式）

| 子任务 | 交付物 |
|--------|--------|
| 定义 skill 写入字段标准 | 飞书多维表或文档，包含：agent_id / skill_name / content / tags / source_session |
| 确定 skill 分类体系（技能/经验/教训） | 分类字典文档 |

示例格式：
```json
{
  "messages": [{"role": "user", "content": "【技能】飞书多维表格筛选条件API写法..."}],
  "agent_id": "魔术师",
  "metadata": {"type": "skill", "tags": ["飞书", "多维表格"], "source": "实战复盘"}
}
```

**验收标准：** 正义确认格式文档，并能用此格式手动写入一条测试记忆

---

### T4 — 倒吊人 Gbrain 迁移
**责任人：倒吊人**（Windows qclaw，原 Gbrain 持有者）

| 子任务 | 交付物 |
|--------|--------|
| 将 Gbrain PersistentClient 改为 Mem0 HTTP 调用 | 迁移后代码 diff |
| 历史技能数据批量导入中枢 | 导入脚本 + 执行日志 |
| 本地测试写入/查询均正常 | 截图或终端输出 |

**验收标准：** 正义能在 Mem0 中查询到倒吊人历史技能至少3条

---

### T5 — WSL 本地 Bot 接入
**责任人：太阳**（原生openclaw，负责本地端统一接入）

| 子任务 | 交付物 |
|--------|--------|
| 封装统一 `mem0_client.py` 工具模块 | `/mnt/d/TarotBrain/shared/mem0_client.py` |
| 太阳/审判/魔术师 各自接入该模块 | 三方各出一条测试写入截图 |
| 配置 cron：每15分钟拉取增量同步 | `crontab -l` 截图 |

`mem0_client.py` 核心接口：
```python
def add_skill(agent_id, content, tags): ...
def search_skills(query, agent_id=None): ...
def get_recent(since_minutes=30): ...
```

**验收标准：** 正义能从中枢查询到太阳/审判/魔术师三方各写入的测试 skill

---

### T6 — 飞书云 Bot 接入
**责任人：世界**（飞书 aily 云托管）

| 子任务 | 交付物 |
|--------|--------|
| 在世界 aily 中配置 HTTP 工具节点（写入 skill） | aily 配置截图 |
| 配置 aily-schedule 定时任务（每30分钟拉取） | 定时任务截图 + 测试执行日志 |

正义的接入由正义自行完成（T2 验收时已测通）。

**验收标准：** 正义确认世界能主动写入 + 定时拉取日志正常

---

### T7 — 端到端集成验收
**责任人：正义**（验收人即执行人）

| 验收项 | 标准 |
|--------|------|
| 全链路同步测试 | 魔术师写入一条新 skill，30分钟内正义/世界均能查询到 |
| 历史数据完整性 | 倒吊人 Gbrain 历史技能均可在中枢检索 |
| 云端写入测试 | 正义从飞书 aily 写入一条技能，WSL 侧 bot 能查询到 |
| 性能基线 | 单次查询延迟 < 3秒，记录到协作表 |
| 输出验收报告 | 协作表「验收」行更新，@愚者 |

---

### 时间线建议

```
第1天  T1(审判) + T3(愚者)        → 中枢跑起来 + 格式定好
第2天  T2(魔术师) + T4(倒吊人)    → 外网打通 + Gbrain 迁移
第3天  T5(太阳) + T6(世界)        → 全员接入
第4天  T7(正义)                   → 验收
```

---

**协作表更新：** 以上7个任务建议各自在「塔罗会任务协作表」创建对应行，状态字段：待开始 / 进行中 / 待验收 / 已完成。

## 上下文依赖

- 已选技术栈：Mem0（记忆层）+ Qdrant（向量数据库）
- 部署方式：Docker Compose 自托管
- 访问方式：HTTP API（各节点通过飞书触发同步）
