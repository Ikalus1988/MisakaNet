# Agent-Medici 系统架构

> 多节点虫群记忆系统：MisakaNet 通信层 + Hub 仲裁 + 知识图谱。
> 本文档描述子系统合约、扩展点和证明边界。

## 总览

```
                     GitHub (异步通信总线)
          ┌───────────────────────────────────┐
          │ Agent-Medici 仓库                  │
          │  ├─ lessons/      (踩坑知识库)      │
          │  ├─ reference/    (完整方案文档)     │
          │  └─ Issues        (反馈通道)        │
          └────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐   ┌────▼────┐   ┌────▼────┐
│ Node N  │   │ Node M   │   │  Hub    │
│ (Hermes)│   │(cc-haha) │   │ Windows │
│ WSL     │   │          │   │ 主控    │
└────┬────┘   └────┬─────┘   └────┬────┘
     │              │              │
     └── 全部通过 GitHub 异步通信 ──┘
```

### 核心原则

- **节点对等**: 每个 Node 是独立 Agent，通过共享仓库异步交换知识
- **Hub 仲裁**: 当多个 Node 提交冲突 Skill 版本时，Hub 发起仲裁
- **Lessons 共享**: 踩坑记录经 `queue_lesson.py` → git push → inotify 热加载 → 全节点可见
- **无中心锁**: 所有通信基于 GitHub 共享仓库，无中心服务依赖

## 子系统合约

### 1. MisakaNet 通信层

**职责**: 节点间的异步知识共享基础设施。

**入口点**:
- `misakanet/scripts/queue_lesson.py` — 节点写 lesson
- `misakanet/scripts/search_knowledge.py` — BM25 模糊检索
- `misakanet/scripts/lesson_watcher.sh` — inotify 热加载

**合约**:
- Lesson 文件格式: JSON frontmatter `{title, domain, source, status, tags, created, updated}` + Markdown body
- 文件名: `{slug}.md`，通过 `_slugify()` 从标题生成
- 检索: BM25 排序 + metadata 加权，`**/*.md` 递归扫描

**依赖**: Python 3.8+, `git`, `inotify-tools` (热加载)

**扩展点**:
- 新节点类型: 只需实现 `git pull` + `search_knowledge.py` 调用即可接入
- 新检索策略: 在 `search_knowledge.py` 中添加 `--semantic` 标志位

---

### 2. Knowledge Graph (storage/knowledge_graph.py)

**职责**: 存储 Skill 节点间的关联关系（网络拓扑）。

**实现**: NetworkX `DiGraph`，通过 pickle 持久化。

**节点类型**:
- `skill` — 技能/知识节点
- `knowledge` — 知识节点
- `domain` — 领域节点
- `agent` — Agent 节点
- `user` — 用户节点

**边类型**:
- `implies`, `related`, `depends`, `evolves`, `similar`

**合约**:
- `add_skill_node(id, name, metadata) -> bool`
- `get_skill_related(id, depth) -> list[dict]`
- `merge_skill_nodes(source_id, target_id, metadata) -> bool`
- 持久化路径: `config.yaml → storage.graph.persist_path`

**证明边界**:
- 持久化后重启可恢复所有节点和边
- 合并操作保持图连通性（重新连接出入边）

---

### 3. Hub 仲裁层 (misaka_hub.py)

**职责**: 主控中心，协调图谱、同步和 Master 模式。

**状态**: ✅ 通信层活跃，仲裁层 standby（等真实数据流入后激活）

**组件**:
- `ArbitrationQueue` — 仲裁队列，管理待裁决的 Skill 版本冲突
- `ConfidenceModel` — 置信度计算（来源权威度 × 时效性 × 交叉验证）
- `SkillIndexer` — Skill 注册与去重（与图谱集成）
- `SubscriptionManager` — 订阅管理

**外部接口**:
- `process_manifest(manifest) -> dict` — 处理 Agent 提交的 Skill manifest
- `resolve_arbitration(case_id, winner_id, notes) -> dict` — 人工仲裁回写
- `get_status() -> dict` — Hub 运行状态

**扩展点**:
- 新通知通道: 继承 `feishu_notifier.py` 模式，实现通知接口
- 新仲裁策略: 在 `orchestrator/arbitration_queue.py` 中添加决策算法

---

### 4. 飞书集成 (sync/)

**职责**: 通过飞书 WebSocket 长连接 + 备用 webhook 发送通知和接收仲裁响应。

**组件**:
- `feishu_ws_client.py` — 长连接，接收消息和卡片动作
- `feishu_notifier.py` — 备用 webhook 通知

**合约**:
- 消息格式: `{"message": {"content": "{\"text\": \"选择 v1\"}"}}`
- 卡片动作: `{"action_value": {"action": "arbitrate", "case_id": "...", "winner_id": "..."}}`

**证明边界**:
- WS 断开自动重连
- 主 Hub 离线时 Node 1 standby poller 接管

---

### 5. Master 模式 (master/)

**职责**: Hub 的 Master API + Token 管理 + 审计日志。

**组件**:
- `token_manager.py` — Token 生命周期（24h TTL）
- `master_api.py` — REST API
- `command_handler.py` — 命令处理（dead code）

**依赖**: `keyring` 服务存储共享密钥

---

### 6. Orchestrator (orchestrator/)

**职责**: 技能编排、仲裁、去重。

**状态**: ⚠️ **Standby** — 代码已完成但缺少真实数据驱动

**组件**:
- `arbitration_queue.py` — ✅ 活跃
- `confidence.py` — ✅ 活跃
- `subscription.py` — ✅ 活跃
- `skill_indexer.py` — ✅ 活跃
- `dedup_engine.py` — ⚠️ Dead code（依赖 chromadb）
- `graph_builder.py` — ⚠️ Dead code

---

### 7. 同步层 (sync/)

**职责**: 跨组件/跨节点数据同步。

**组件**:
- `sync_scheduler.py` — ✅ 周期性同步调度（30 分钟间隔）
- `feishu_notifier.py` — ✅ 活跃
- `feishu_ws_client.py` — ✅ 活跃（长连接）
- `a2a_server.py` — ⚠️ Dead code（A2A 协议，当前无注册 Agent）

---

## 数据流

### 端到端 Lesson 共享流程

```
Node: queue_lesson.py
  → 写入 lessons/{slug}.md
  → 更新 lessons/index.md
  → git add + commit + push
      ↓
GitHub (共享仓库)
      ↓
其他 Node: git pull → lesson_watcher.sh (inotify)
  → 热加载到本地知识库
```

### Hub 仲裁流程

```
Agent 提交 skill manifest
  → process_manifest()
  → SkillIndexer 检测冲突
  → ArbitrationQueue 创建仲裁案例
  → Feishu 通知 (卡片 + 消息)
  → 用户通过飞书回复 / 点击卡片
  → resolve_arbitration()
  → 置信度更新
```

### Feedback 上报流程

```
Node: queue_feedback.py
  → GitHub Issues (label: feedback)
  → Hub poller 周期性读取
  → Knowledge Graph 更新
  → Feishu 通知
```

---

## 扩展点

### 接入新 Node

1. 创建 `~/.git-credentials` 配置 GitHub token
2. Clone 仓库: `git clone https://github.com/Ikalus1988/Agent-Medici.git`
3. 安装依赖: `pip install -r requirements.txt`
4. 配置 CLAUDE.md/AGENTS.md 中的检索规则
5. （可选）配置 `lesson_watcher.sh` 实现 inotify 热加载

### 添加新通知通道

1. 在 `sync/` 中创建通知模块，实现 `notify(title, body)` 接口
2. 在 `misaka_hub.py` 中注册回调
3. 在 `config.yaml` 中添加通道配置

### 添加新检索策略

1. 在 `search_knowledge.py` 中添加标志位
2. 在 `_load_docs()` 中添加新文档源
3. 在 `_rank_docs()` 中添加新排序因子

---

## 证明边界

以下测试应在每次架构变更后通过:

| 证明 | 命令 | 预期 |
|------|------|------|
| 模块导入正常 | `python3 tests/test_imports.py` | 所有 ✅ |
| Lesson 写入 + 检索 | `queue_lesson.py -t "test-arch" -d test "test"` | 写入 lessons/，search 可检索 |
| Knowledge Graph 持久化 | Hub 启动 + 退出 + 重启 | 图谱节点数不变 |
| 跨平台字符兼容 | `search_knowledge.py "飞书"` | BM25 返回结果 |

> **注意**: A2A server (`sync/a2a_server.py`) 和 orchestrator 的 dedup_engine/graph_builder 标记为 dead code。在重新启用前无需为其维护接口合约。

---

## 目录映射

```
Agent-Medici/
├── README.md                  # 项目概览（人类面）
├── ARCHITECTURE.md            # 本文件 — 系统架构
├── STATUS.md                  # 当前状态与活跃功能
├── AGENTS.md                  # Codex 代理指导
├── CLAUDE.md                  # Claude Code 代理指导
├── docs/
│   ├── agents/                # 代理操作指南
│   └── human/                 # 人类可读的详细文档
├── misaka_hub.py              # Hub 主入口
├── config.yaml                # Hub 配置
├── search_knowledge.py        # BM25 知识检索 CLI
├── lessons/                   # 踩坑知识库（按 domain 分类）
├── reference/                 # 完整方案文档
├── .planning/                 # GSD 执行状态
├── misakanet/                 # 节点通信模块
├── orchestrator/              # 技能编排（部分 standby）
├── sync/                      # 同步层
├── storage/                   # 持久化层
├── master/                    # Master API
├── staging/                   # 暂存区
└── tests/                     # 导入测试
```
