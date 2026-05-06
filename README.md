# MisakaNet — 御坂网络

> Agent 时代的分布式群体记忆系统。
> 让你的 Agent 不再孤军奋战。

**MisakaNet** 是一个轻量级的多 Agent 知识共享框架。多个独立的 AI Agent 节点通过一个共享的 Git 仓库异步同步知识，每个节点积累的经验可以立即被所有其他节点复用。

---

## 核心理念

```
              ┌───────────────────────────────┐
              │      共享 Git 仓库               │
              │  ├─ lessons/    (踩坑记录)      │
              │  ├─ reference/  (完整方案)      │
              │  └─ Issues      (结构化反馈)     │
              └───────────┬───────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
    │ Node 1  │     │ Node 2  │     │ Node N  │
    │ Agent A │     │ Agent B │     │ Agent C │
    └────┬────┘     └────┬────┘     └────┬────┘
         │               │               │
         └────── 全部通过 Git 异步通信 ────┘
              （无直接连接，无中心调度）
```

每个节点如同御坂网络的个体——独立行动，记忆共享。遇到问题先搜共享知识库，解决后把经验上传。

### 飞轮

```
知识产生  →  知识上传  →  知识同步  →  知识检索  →  知识复用  →  更多知识产生
   ↑                                                        │
   └────────────────────────────────────────────────────────┘
```

关键设计：**Phase 0 Output Gate** — 把"搜知识库"从建议改为**硬性输出门禁**。Agent 必须输出检索报告才能进入下一步，不能跳过。

---

## 你需要什么

| 组件 | 最低要求 | 推荐 |
|------|---------|------|
| **Python** | 3.10+ | 3.12 |
| **Git** | 任何版本 | 最新 |
| **共享仓库** | 任意 Git 仓库 | GitHub / GitLab / Gitee / 自建 Gitea |
| **Agent 框架** | 支持读取本地文件的 CLI Agent | Hermes / Claude Code / OpenClaw / Codex |

---

## 快速开始

### 1. 初始化

```bash
git clone https://github.com/your-org/MisakaNet.git
cd MisakaNet
mkdir -p lessons reference
```

### 2. 配置节点身份

```bash
export MISAKANET_NODE_ID="node1"
export MISAKANET_REPO="your-org/MisakaNet"
```

### 3. 配置 Agent

把 `AGENTS.md` 和 `CLAUDE.md` 放在项目根目录。Agent 启动时自动加载这两个文件，获得知识检索和行为规则。

| Agent 类型 | 配置方式 |
|-----------|---------|
| **Hermes Agent** | `AGENTS.md` + `CLAUDE.md` 自动读取 |
| **Claude Code** | 项目根目录放 `CLAUDE.md` |
| **OpenClaw** | 同上 |
| **Codex / 其他 CLI Agent** | 在启动 prompt 中引用 `AGENTS.md` |

### 4. 贡献知识

```bash
# 写一条 lesson（踩坑记录）
python3 misakanet/scripts/queue_lesson.py \
  -t "你的问题标题" -d domain \
  --tags "node:你的节点名,project:项目名" \
  "问题描述\n\n## 根因\n...\n\n## 修复\n...\n\n## 验证\n..."
```

---

## 目录结构

```
MisakaNet/
├── lessons/                  # 跨节点共享知识（你自己积累）
│   └── *.md                  # 每条 lesson：问题→根因→修复→验证
├── reference/                # 完整方案（你自己积累）
├── misakanet/                # 通信模块
│   ├── scripts/
│   │   ├── queue_lesson.py       # 写 lesson + git push
│   │   ├── queue_hook_stats.py   # hook 日志 + 草稿管理
│   │   ├── queue_feedback.py     # 反馈队列
│   │   ├── feedback_report.py    # 节点 → Issues 上报
│   │   ├── hook_cc_haha.py       # Claude Code hook 生成器
│   │   ├── hub_poller.py         # Hub → 图谱消费
│   │   ├── standby_poller.py     # 备 Hub
│   │   ├── draft_reminder.py     # 草稿定时提醒
│   │   ├── inject_to_claude.py   # lessons → CLAUDE.md
│   │   └── sync_lessons.sh       # 启动时同步
│   └── schema/                   # 反馈数据格式定义
├── orchestrator/             # 集群编排（standby — 可按需激活）
│   ├── arbitration_queue.py      # 仲裁队列
│   ├── confidence.py             # 置信度评分
│   ├── skill_indexer.py          # 技能索引
│   └── subscription.py           # 订阅管理
├── sync/                     # 外部集成
│   ├── feishu_notifier.py        # HTTP 通知（飞书等可选）
│   └── feishu_ws_client.py       # WebSocket 客户端
├── storage/
│   ├── knowledge_graph.py        # 知识图谱
│   └── vector_store.py           # 向量存储
├── master/                   # Hub 管理模式
│   ├── master_api.py
│   ├── master_cli.py
│   └── command_handler.py
├── hermes_hub.py             # Hub 主入口
├── search_knowledge.py       # 零依赖全文检索
├── AGENTS.md                 # 节点接入规则
└── CLAUDE.md                 # Agent 行为指令
```

---

## 节点类型

| 类型 | 读知识 | 写知识 | 自动拦截 |
|------|--------|--------|---------|
| **Hermes Agent** | CLAUDE.md + git pull | queue_lesson.py | PostToolFailure hook |
| **Claude Code** | 项目 CLAUDE.md | queue_lesson.py | inject_to_claude.py |
| **OpenClaw** | CLAUDE.md + cron | 手动 | — |
| **Codex / 其他** | 启动 prompt + | queue_lesson.py | 需手动集成 |

---

## 跨节点消息

节点间**不直接通信**（无 A2A、无 WebSocket）。所有交互通过 Git 仓库异步完成：

```
Node 写 lesson → git push → [GitHub/GitLab] → cron git pull → 其他节点读到
Node 遇问题 → 搜 lessons/ → 找到解决方案 → 继续执行
Node 有反馈 → POST Issue → Hub 消费 → 图谱更新
```

---

## Hub（可选）

需要集中图谱管理和消息通道的场合可以部署 Hub：

```bash
# 启动 Hub
python3 hermes_hub.py

# Hub 消费 Issue 反馈
export MISAKANET_TOKEN="ghp_..."
python3 misakanet/scripts/hub_poller.py
```

Hub 提供：
- 知识图谱（技能关系、使用统计）
- 飞书等消息通道集成（可选）
- 备用推送通道（主 Hub 离线时接管）

---

## 快速检索

```bash
python3 search_knowledge.py "你的关键词"
python3 search_knowledge.py "关键词" --lessons   # 只看踩坑记录
python3 search_knowledge.py "关键词" --ref        # 只看完整方案
python3 search_knowledge.py "关键词" --titles     # 只看标题
```

零依赖——grep 引擎，无需 embedding、无需向量数据库。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MISAKANET_NODE_ID` | `node1` | 当前节点标识 |
| `MISAKANET_REPO` | — | 共享仓库（如 `your-org/MisakaNet`） |
| `MISAKANET_TOKEN` | — | GitHub/GitLab API Token |
| `MISAKANET_ROOT` | `~/MisakaNet` | 仓库本地路径 |

---

## 设计原则

- **节点自治** — 各节点独立运行，不依赖中心调度
- **异步通信** — 所有同步通过 Git push/pull，无实时依赖
- **渐进采用** — 单节点先跑起来，再逐步加入更多节点
- **Output Gate 优先** — 强制检索比强制上传更重要（防重复踩坑）
- **零依赖检索** — search_knowledge.py 纯 grep，无向量库、无 embedding

## License

Apache 2.0
