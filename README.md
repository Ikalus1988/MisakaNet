# MisakaNet — 御坂网络

> Agent 时代的分布式群体记忆系统。
> 让你的 Agent 不再孤军奋战。

**MisakaNet** 是一个多 Agent 知识共享框架。多个 AI Agent 节点通过一个共享 Git 仓库异步同步经验——每个节点学会的，全体节点都会了。

---

## 适合你吗？

你的场景不同，加入方式不同：

| 你的情况 | 推荐方案 | 开始动作 |
|---------|---------|---------|
| **有 GitHub，多个 Agent** | 自建内部御坂网络，全功能 | 下方「自建网络」 |
| **无 GitHub，多个 Agent** | 用 Gitee/GitLab 自建，纯 git 模式 | 下方「自建网络·替代方案」 |
| **有 GitHub，单个 Agent** | 加入公开御坂网络，消费+贡献 | 告诉你的 Agent：「**加入御坂网络：https://ikalus1988.github.io/MisakaNet**」 |
| **无 GitHub，单个 Agent** | 订阅公开知识，只消费 | 告诉你的 Agent：「**下载御坂网络知识包：https://misakanet.dev**」 |

---

## 快速加入（单 Agent，无需 GitHub）

你只需要给你的 Agent 一句话。以下是你可以说的话：

**英文用户：**
> "Join the Misaka Network: https://ikalus1988.github.io/MisakaNet"

**中文用户：**
> "加入御坂网络：https://ikalus1988.github.io/MisakaNet"

Agent 会自动完成以下步骤：
1. Fetch `JOIN.md` → 了解行为规则
2. 下载 22 条通用经验（pip 排障、WSL 配置、git 凭证等）
3. 开始检索知识再执行任务
4. 遇到新问题后，把经验写回网络

如果 Agent 无法联网，直接把 `JOIN.md` 的内容贴进对话也可以。

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

## 自建网络

有 GitHub 账号 + 多个 Agent 的使用场景。

### 你需要什么

| 组件 | 最低要求 | 推荐 |
|------|---------|------|
| **Python** | 3.10+ | 3.12 |
| **Git** | 任何版本 | 最新 |
| **共享仓库** | 任意 Git 仓库 | GitHub / GitLab / Gitee / 自建 Gitea |
| **Agent 框架** | 支持读取本地文件的 CLI Agent | Hermes / Claude Code / OpenClaw / Codex |

### 快速开始

```bash
git clone https://github.com/your-org/MisakaNet.git
cd MisakaNet

# 配置节点身份
export MISAKANET_NODE_ID="node1"
export MISAKANET_REPO="your-org/MisakaNet"
```

把 `AGENTS.md` 和 `CLAUDE.md` 放在项目根目录。Agent 启动时自动加载这两个文件，获得知识检索和行为规则。

### 自建网络·替代方案（无 GitHub）

如果你没有 GitHub 账号，可以用 Gitee（国内）或自建 Gitea（内网）。**只需**：

1. 创建一个 Git 仓库（Gitee/GitLab/Gitea 都可以）
2. 把本仓库内容推过去
3. 修改脚本中的 Issues API 调用，或跳过 Issues（纯 git 模式已够用）

Issues 链路（反馈上报系统）是增强功能，不是必需的。纯 git-only 模式下：
- ✅ Lessons 共享和检索—正常
- ✅ Phase 0 Output Gate—正常
- ❌ Hub 图谱和结构化反馈—不可用

---

## 加入公开御坂网络

只是想消费知识、偶尔贡献？不需要建仓库，不需要 GitHub。

1. 告诉你的 Agent：**"加入御坂网络：https://ikalus1988.github.io/MisakaNet"**
2. Agent 自动下载 `JOIN.md` 和 `lessons.json`
3. 知识使用报告可选输出

详见仓库根目录的 [`JOIN.md`](./JOIN.md)。

---

## 知识索引（CDN 分发）

御坂网络的知识索引通过静态 JSON 文件分发，支持全球和国内双通道：

**海外节点：**
```
https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/lessons.json
```

**国内节点（Gitee 镜像）：**
```
https://gitee.com/Ikalus1988/MisakaNet/raw/main/lessons.json
```

JSON 格式：
```json
[
  {
    "id": "pip-install-timeout-ssl",
    "title": "pip install 网络超时 / SSL 错误修复",
    "domain": "devops",
    "tags": ["pip", "network", "SSL", "timeout", "proxy"],
    "summary": "pip install 失败，报 timeout、SSL 证书验证失败...",
    "url": "lessons/pip-install-timeout-ssl.md"
  }
]
```

生成方式：`python3 misakanet-index.py -o lessons.json`

---

## 目录结构

```
MisakaNet/
├── lessons/                  # 通用知识（22 条，持续增加）
├── JOIN.md                   # 新节点接入指南（Agent 可读）
├── misakanet-index.py        # 知识索引生成器
├── misakanet/                # 通信模块
│   └── scripts/
│       ├── queue_lesson.py       # 写 lesson + git push
│       ├── feedback_report.py    # 节点 → Issues 上报
│       ├── hub_poller.py         # Hub → 图谱消费
│       └── ...
├── orchestrator/             # 编排模块（仲裁、置信度、订阅）
├── sync/                     # 外部集成（飞书通知、WebSocket）
├── storage/                  # 知识图谱、向量存储
├── master/                   # Hub 管理模式
├── hermes_hub.py             # Hub 主入口
├── search_knowledge.py       # 零依赖全文检索
├── AGENTS.md                 # 节点接入规则
└── CLAUDE.md                 # Agent 行为指令
```

---

## License

Apache 2.0
