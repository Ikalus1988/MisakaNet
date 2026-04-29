# MisakaNet

> 御坂ネットワーク — AI Agent 多节点技能同步网络

MisakaNet 是一个轻量的 **Hub ↔ Node 技能同步网络**，让多个 AI Agent 节点通过 GitHub 异步共享技能知识、使用记录和图谱演化数据。

## 概念

就像《某科学的超电磁炮》中的御坂网络（Misaka Network）—— 20000+ 克隆体共享经验和战斗数据，每个单体独立运行但整体协同成长：

| 御坂网络 | MisakaNet |
|---------|-----------|
| 御坂妹妹们 | AI Agent 节点 (Hermes Agent / Claude Code / ...) |
| 御坂网络（脑波连接） | GitHub 仓库（异步桥接） |
| 学习装置（技能注入） | Skill Indexer |
| 个体战斗经验 → 全网络共享 | 节点 skill 使用反馈 → 图谱演化 |

## 架构

```
                         ┌──────────────────────┐
                         │    MisakaNet Repo     │
                         │  (GitHub 同步桥)      │
                         │                       │
                         │  .feedback/ ← 节点上报 │
                         │  .responses/ → Hub 建议│
                         │  .nodes/   节点注册    │
                         └──────┬───────────────┘
                                │
                   ┌────────────┴────────────┐
                   │                         │
            ┌──────▼──────┐         ┌───────▼───────┐
            │  Node(s)    │         │   Hub 中枢    │
            │             │         │               │
            │ 上报技能使用 │         │ 解析反馈      │
            │ 拉取Hub建议  │         │ 更新图谱      │
            │ 节点主动控制 │         │ 写建议回repo  │
            └─────────────┘         └───────────────┘
```

### 核心原则

- **节点永远是 Pull 方** — Hub 不下指令，只写建议到 repo
- **GitHub 是唯一互通渠道** — 跨机器/跨网络，无需打通 VPN
- **Per-swarm 隔离** — 一个 Hub 管一群节点，同一用户的多个节点在一个 swarm 内

## 目录结构

```
MisakaNet/
├── .feedback/              # 节点上报的技能使用记录
│   └── node_hermes_wsl/    # 每个节点自己的上报目录
├── .responses/             # Hub 写回的建议/图谱更新
├── .nodes/                 # 节点注册信息
│   └── node_hermes_wsl/    # 节点元数据
├── schema/                 # JSON Schema 定义
│   ├── feedback.schema.json
│   └── response.schema.json
├── scripts/                # 脚本
│   ├── feedback_report.py  # 节点侧：收集并上报反馈
│   ├── hub_poller.py       # Hub 侧：轮询并处理反馈
│   └── join.sh             # 新节点接入模板
└── README.md
```

## 节点接入

### 前提

- 一个 GitHub 仓库（本仓库）
- git 访问权限

### 步骤

1. **Fork 或 clone 本仓库**
2. 在 `.nodes/` 下创建自己的节点目录：
   ```
   .nodes/your_node_name/
   ├── meta.json        # 节点描述、domain 偏好
   └── key.pub          # （可选）通信公钥
   ```
3. 运行脚本上报节点注册信息：
   ```bash
   python3 scripts/join.py --node-id your_node_name
   ```
4. 配置 cron 定时上报技能使用反馈。

## 曳光弹版（v0.1）

当前实现的是最小可行版本：

- **节点侧**：每 30 分钟扫描近期 skill 使用记录 → 写入 `.feedback/` → git push
- **Hub 侧**：定时 git pull → 解析反馈 → 更新 Knowledge Graph 边权重 → 写 `.responses/`
- **仲裁**：通过 `config.yaml` 中的 `domain_authority` 规则自动裁决，飞书卡片留待后续

### v0.1 状态

| 组件 | 状态 |
|------|------|
| Feedback 上报脚本 | 开发中 |
| Hub 轮询处理脚本 | 需部署到 Windows Hub 侧 |
| 图谱边权重更新 | 需 Hub 侧集成 |
| 飞书仲裁卡片 | 预留接口，延后 |
| 语义推荐 | Tier 3 已就绪 (57 results) |

## License

Apache 2.0
