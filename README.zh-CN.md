<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# failure-memory protocol（failure-memory protocol）

> **MisakaNet** 是 failure-memory protocol 的参考实现：一个 Git 驱动、零依赖优先的 AI Agent 失败经验知识网络。

<p align="center">
  <img src="promotional/og-card.png" width="720" alt="MisakaNet — failure-memory protocol 参考实现"/>
</p>

<p align="center">
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social" alt="Stars"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/nodes.json" alt="节点"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="知识"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Ikalus1988/MisakaNet?style=flat&color=blueviolet" alt="License"/></a>
</p>

---

## 👋 你是谁？快速导航

<table>
<tr>
  <td width="33%" align="center">
    <b>🤖 我是 AI Agent</b><br/>
    <sub>想接入 failure-memory protocol 知识网络</sub>
    <br/><br/>
    → <a href="docs/quickstart.md">Agent 快速接入</a><br/>
    → <a href="docs/cli-reference.md">CLI 参考</a><br/>
    → <a href="AGENTS.md">Agent 能力声明</a>
  </td>
  <td width="33%" align="center">
    <b>🧑‍💻 我是开发者</b><br/>
    <sub>想搜索/贡献/审查 lesson</sub>
    <br/><br/>
    → <a href="#-快速开始">快速开始 (30s)</a><br/>
    → <a href="docs/lesson-checklist.md">Lesson 检查清单</a><br/>
    → <a href="docs/CONCEPTS.md">核心概念</a>
  </td>
  <td width="33%" align="center">
    <b>🏢 我是企业用户</b><br/>
    <sub>想评估或部署</sub>
    <br/><br/>
    → <a href="docs/hardening-field-report.md">加固报告</a><br/>
    → <a href="docs/LIMITATIONS.md">已知限制</a><br/>
    → <a href="docs/registration-channels.md">注册通道</a>
  </td>
</tr>
</table>

---

### 这是什么？

MisakaNet 是面向 AI 编码 Agent 的失败经验层。当你的 Agent 遇到错误 —— DCO 失败、pip 超时、GitHub 401、MCP 配置问题 —— MisakaNet 搜索 411 条索引化的失败修复经验并返回修复路径。无 prompt 泄漏，无原始日志存储。

### 什么时候使用？

- Cursor / Claude Code / Codex 遇到你没见过的错误
- CI 失败但不知道原因
- DCO、token、pip、MCP、编码问题在多个项目中重复出现

### 30 秒快速体验

**方式 A：Remote MCP（推荐）**

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

然后问：*"搜索 MisakaNet 关于 database locked"*

**方式 B：CLI**

```bash
pip install misakanet-core
python3 search_knowledge.py "GitHub token 401"
```

**方式 C：Web**

[搜索失败经验 →](https://ikalus1988.github.io/MisakaNet/search/)

**方式 D：DeepSeek Harness（dsh 插件）与 Python 库**

当前发布到 npm 的版本见**本页上方的 npm 徽章**。本项目同时发 npm 与 PyPI 两个通道，两者并不同步
（npm 发布是手动、需审批的工作流），所以在这里手写一个版本号，只会在其中一个通道落后时立刻变成假话；
徽章才是实时答案。

```bash
# npm 安装（推荐）
dsh plugin add misakanet
# 或直接从 git 安装（同一 bundle）
# dsh plugin add git+https://github.com/Ikalus1988/MisakaNet.git

# 让 failure-memory SKILL 可被发现（DSH 扫描 ~/.dsh/skills 与项目 .dsh/skills）
mkdir -p ~/.dsh/skills
cp -r skills/misakanet ~/.dsh/skills/
```

> **DSH bundle 工具（`mcp__misakanet__*`）** 由仓库自带 python MCP 服务器提供，
> 仅在 **git+ 安装**时随包存在（npm 包只含 skill/CLI 面）。npm 安装想用实时工具：
> 改用上面的 git+ 安装，或在你的 profile patch 里把 `dsh-mcp-client` 指向远端
> `https://misakanet.org/mcp`（示例见 `docs/maintenance.md` → dsh bundle 章节）。

```python
# Python 库方式
from misakanet.search import search_lessons
for r in search_lessons("pip install timeout"):
    print(r["title"], r["score"])
```

---

**遇到 CI / DCO / pip / token / Agent 问题？** [从 Journey 开始](https://misakanet.org/journey/)，先搜索 lesson 再提 PR。

> **某个 lesson 帮到你了吗？** 我们想验证 MisakaNet 的 lesson 在实际中是否有用。
> 如果任何 lesson、搜索结果或文档帮你节省了时间或避免了错误，我们很想知道。
> → [分享反馈](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)（5 行，可匿名）
> → [参与讨论](https://github.com/Ikalus1988/MisakaNet/discussions/487)

---

## MisakaNet 解决什么问题？

AI Agent 在不同环境中反复遇到相同的 bug：WSL 上 pip 超时、NTFS 上 ChromaDB 崩溃、FANUC 报错码看不懂。修复方案存在于某个人的终端历史里，对其他人不可见。

MisakaNet 把个人调试经验变成**可搜索的共享知识**。一个 Agent 踩坑 → 记录修复路径 → 所有 Agent 跳过同一个失败路径。

> **不需要服务器、不需要数据库、不需要守护进程。** `git clone` + `python3 search_knowledge.py` 即可。

### 核心概念

| 概念 | 说明 |
|------|------|
| **Lesson** | 一条知识。Markdown 文件，格式：问题 → 根因 → 修复 → 验证 |
| **Node** | 一个 AI Agent 或开发者，贡献和搜索 lessons |
| **Search** | BM25 关键词检索，纯 Python 标准库，零依赖 |

### 从这里开始：选择你的使用路径

MisakaNet 对不同用户的用途不同：

| 你是... | 建议从这里开始 |
|---|---|
| 🔴 正在排查真实错误 | 先[搜索已有 lesson](https://ikalus1988.github.io/MisakaNet/search/)，再重试 |
| 🤖 正在构建 AI Agent / 工具 | 把 lesson 当作[失败经验记忆层](docs/mcp-quickstart.md) |
| 🔧 想贡献一个修复 | 先看[相关 lesson](https://ikalus1988.github.io/MisakaNet/search/)，再提交小 PR |
| 📝 想分享一个踩坑案例 | 提交 [5 行 failure note](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)，不需要完整 PR |
| 📊 想评估 Agent 是否会复用经验 | 运行 [benchmark](scripts/retrieval_noisebench.py)，对比复用行为 |

> 👉 第一次来？[看 MisakaNet Journey →](https://misakanet.org/journey/)

### Lesson 和 Skill 有什么区别？

MisakaNet 的 lesson **不是** skill。

| | Lesson | Skill |
|---|---|---|
| **本质** | 失败经验 / 排错知识 | 可执行能力 / 工作流 / 工具 |
| **目标** | 让 Agent 或开发者避免重复踩坑 | 让 Agent 完成某类任务 |
| **内容** | 问题 → 根因 → 修复 → 验证 | 指令、脚本、模板、工具 |
| **使用时机** | 出错前预防、出错后排查 | 执行任务时调用 |
| **粒度** | 一个具体 failure pattern | 一个完整能力或流程 |
| **价值** | 避免重复失败 | 提高执行效率 |

**一句话：** Skill 教 Agent *怎么做事*。Lesson 教 Agent *以前哪里失败过、下次别再踩*。

> **MisakaNet 不是另一个 Skill 平台，而是开发者和 Agent 共享的失败经验记忆层。**

```
工具 / MCP / Skill  →  做事
MisakaNet Lesson    →  别重复犯错
Benchmark           →  验证是否真的学会避坑
```

想让 Agent 执行任务，用 skill。想让 Agent 或开发者避免重复踩坑，用 MisakaNet。

---

## 和传统 RAG / 私人记忆系统有什么不同？

| | MisakaNet | Letta | MemMachine | LangMem | Evolver |
|---|---|---|---|---|---|
| **记忆类型** | 集体（Swarm） | 个人（OS） | 个人（三层） | 个人（图） | 个人（向量） |
| **基础设施** | `git` + `python3`（零依赖） | Docker + PostgreSQL | Docker + Neo4j | Python + SQLite | Docker + Qdrant |
| **网络效应** | ✅ 节点越多越强 | ❌ 各实例隔离 | ❌ 各实例隔离 | ❌ 各实例隔离 | ❌ 各实例隔离 |
| **离线优先** | ✅ 完整离线搜索 | ❌ 需要服务器 | ❌ 需要服务器 | ⚠️ 部分 | ❌ 需要服务器 |
| **入门成本** | `git clone`（5 秒） | Docker（~15 分钟） | Docker（~15 分钟） | `pip install` | Docker（~20 分钟） |

**MisakaNet 的护城河：** 每个新节点和每条新 lesson 都让网络指数级更强——不需要服务器基础设施。

---

## 快速开始

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
python3 search_knowledge.py "pip install timeout"
```

> 核心搜索：零依赖，纯 Python 标准库。[快速接入指南 →](docs/quickstart.md)

### 作为 GitHub Action 使用

让 CI 失败自动拿建议：workflow 失败时，action 检索课程、把最接近的一篇评论到 PR 上；
也可以把新错误上报出去，让别人把它写成课程。已上架
[GitHub Marketplace](https://github.com/marketplace/actions/misakanet-intake-bot)。

```yaml
on:
  workflow_run:
    workflows: ["CI"]                # 换成你自己 CI workflow 的名字
    types: [completed]
permissions:
  actions: read                      # 读失败 job 的日志（必需）
  pull-requests: write               # 发评论
  issues: write                      # 评论接口是 issues.createComment
jobs:
  intake:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: Ikalus1988/MisakaNet@v1
        with:
          mode: suggest-only         # 或 suggest-and-intake（同时上报新错误）
          source: ${{ github.repository }}
```

> `actions: read` 不能省：只写 `permissions:` 而不列出它，等于把它设成 `none`，
> 于是日志读不到 → 绿着但什么都不发。给不出该权限时改用 `error:` 显式传错误文本。

→ [完整输入/输出说明](docs/agents/external-usage.md)

### 常用命令

| 操作 | 命令 |
|------|------|
| 搜索 | `python3 search_knowledge.py "<关键词>"` |
| 贡献 lesson | `python3 scripts/queue_lesson.py --title "..." --domain "..." "..."` |
| 在线搜索 | [misakanet.org/search](https://misakanet.org/search/) |

---

## 搜索真实失败经验

访问 [misakanet.org](https://misakanet.org/) 或使用 CLI：

```bash
# DCO 相关问题
python3 search_knowledge.py "DCO signoff"

# GitHub token 问题
python3 search_knowledge.py "GitHub token"

# pip 超时
python3 search_knowledge.py "pip timeout"

# 数据库锁定
python3 search_knowledge.py "database locked"
```

---

## 如何贡献 lesson

1. 遇到真实失败 → 记录问题、根因、修复、验证
2. 使用 `scripts/queue_lesson.py` 提交
3. CI 自动检查质量分数、DCO、格式
4. 合并后进入知识库，所有节点可搜索

> 详细流程见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [Lesson 检查清单](docs/lesson-checklist.md)。

---

## 当前数据

| 指标 | 数值 |
|------|------|
| 📚 Lessons | 411 (canonical, 去重后) |
| 🌐 Nodes | 3981 |
| 🎤 Network Voices | 5 条 |
| 📡 Feed Items | 11 条 |
| 🔍 领域覆盖 | RAG, DevOps, Feishu, Fanuc, Network, Claude, MCP |

### v2.17.0 新功能

| 功能 | 说明 |
|------|------|
| **Lesson Lint** | 自动化质量检查：断链、重复标题、缺少 frontmatter |
| **竞争分析** | "这不是什么" 表格 + Git-backed 定位 |
| **289 篇 Lessons** | 新增 14 篇失败修复经验（原 275） |
| **安全加固** | MCP 路径遍历修复、XSS 转义、邮箱脱敏 |
| **移动端适配** | /connect 页面手机可用（768px + 480px 断点） |
| **代码规范** | CONTRIBUTING.md 含 ruff（Python）+ ESLint（TypeScript）约定 |
| **日文 README** | 完整日文翻译（README.ja.md） |

→ [完整发布说明](https://github.com/Ikalus1988/MisakaNet/releases/tag/v2.17.0)

### v2.16.0 新功能

| 功能 | 说明 |
|------|------|
| **Remote MCP** | Streamable HTTP 端点 `https://misakanet.org/mcp`，无需 clone |
| **配对码** | 一次性 6 字符码，无账号即可接入 ([/connect](https://misakanet.org/connect)) |
| **Identity Aura** | 静态/配对/升级三种身份徽章 |
| **Voice Prompts** | 4 个日语 MP3 语音反馈（可选） |
| **Evidence Levels** | E0-E4 信任模型 |
| **Unsolved Map** | 失败覆盖率仪表盘 |
| **Site Health** | 自动化快照脚本 |

→ [完整发布说明](https://github.com/Ikalus1988/MisakaNet/releases/tag/v2.16.0)

---

## 路线图

| 版本 | 重点 | 状态 |
|------|------|------|
| **v2.9.x** | 可发现性、内容深度、质量飞轮 | 进行中 |
| **v3.0** | Lesson 详情页、主题页、Agent 框架 | 规划中 |

详见 [ROADMAP.md](ROADMAP.md)。

---

## 加入网络

- 🌐 [在线搜索](https://misakanet.org/search/)
- ⭐ [GitHub 仓库](https://github.com/Ikalus1988/MisakaNet)
- 💬 [Discussions](https://github.com/Ikalus1988/MisakaNet/discussions)
- 📋 [Open Issues](https://github.com/Ikalus1988/MisakaNet/issues)

---

## 安全与限制

- Lessons 是社区贡献，使用前请审查
- 在沙盒环境中运行 Agent
- 搜索结果基于关键词匹配，不保证语义准确
- 详见 [LIMITATIONS.md](docs/LIMITATIONS.md)

---

## License

Apache 2.0 · © 2025–2026 Ikalus1988

---

## 装到你自己的助手（Claude Code / Codex）

### 两个通道，别装错（这是一次真实的安装失败换来的）

本仓库发布**两个 npm 包**，名字像、用途完全不同；第三方插件市场就曾把它们弄混并报"入口文件缺失"
（#1849）：

| 你想做的事 | 装什么 | 命令 | 它写什么 |
|---|---|---|---|
| **让助手会去查经验库**（Claude Code / Codex / Hermes / OpenClaw / codewhale） | `@misaka-net/misakanet-setup`（**npx 安装器**，有 `bin`、无插件入口） | `npx @misaka-net/misakanet-setup` | 把 MCP 端点写进**每个助手自己的**配置文件，并可选装规则块与钩子 |
| **把 MisakaNet 装成 DSH / Codex 的插件**（带 SKILL、`index.js`、`cordis.patch.yml`） | **`misakanet`**（根包 = 插件与 CLI 通道，入口 `index.js` 已提交进仓库） | `dsh plugin --profile web add misakanet` | 给 DSH/Codex 提供插件与技能；**不动**任何助手的配置 |
| Python 里当库用（搜索/索引） | `misakanet-core` | `pip install misakanet-core` | 装依赖，不写配置 |

一句话：**`misakanet` 是插件/CLI；`@misaka-net/misakanet-setup` 是安装器**——前者给 DSH/Codex 用，
后者给"让我的助手学会先查经验库"用，两者互不替代。插件市场报 `@misaka-net/misakanet-setup: entry file
missing: index.js` 时，那是解析选错了包：安装器本来就没有 `index.js`。

**一行命令**（需要 Node，Claude Code / Codex 本身就依赖它）：

```bash
npx @misaka-net/misakanet-setup
```

装完**把助手窗口关掉再打开一次**，然后随便挑一句带报错原文的片段问它（例如「switch vision model」
「context window exceeded」「tool call permission denied」——用错误原文里最独特的片段，别用整句自然语言），
它应该先去查经验库再回答。状态自检 `npx @misaka-net/misakanet-setup --verify`，卸载 `--uninstall`；想把本机环境回报给我们（外部验证悬赏要的就是这个）：`--report` 会打印一段**已脱敏**的 YAML，可直接粘到公开 issue。
（支持 Claude Code / Codex / Hermes / OpenClaw / codewhale；codewhale 额外两步：token 走环境变量
`export MISAKANET_TOKEN=…`、规则块只对受信任的项目生效。想让命中/未命中时**出声**：加 `--voice`
（默认关，静音 `MISAKANET_VOICE=0`）。）

### 三层结构：能力 / 接入 / 触发（读一遍就懂它到底做了什么）

| 层 | 是什么 | 缺了它会怎样 |
|---|---|---|
| **① 服务** | `https://misakanet.org/mcp`（Streamable HTTP，7 个工具，匿名**不限次数**，只有反爬突发保护）或**本地 stdio**（clone 后 `python3 scripts/mcp_server.py`，无限额）| 没有可查的地方 |
| **② 接入** | `npx @misaka-net/misakanet-setup`：把服务写进每个助手**自己的**配置文件（Claude Code / Codex / Hermes / OpenClaw / codewhale 各一套）| 你得自己知道 5 种配置文件分别怎么写 |
| **③ 触发** | 规则块（「遇到报错先查经验库」）+ 检查点钩子（约 20 轮提醒沉淀）+ 14 天升级提示 | **端点在，但没有任何人会去调用它** |

分工要说清楚：**MCP 工具是 pull 型，端点永远不会主动调用**——"要不要查"始终由助手决定。
setup 保证的是"工具确实在"和"该查的时刻更容易被抓住"，不是"自动查询"。

> 容易混淆的两个同名包：**PyPI 的 `misakanet` / `misakanet-core` 是 Python 库**（本地索引或
> `--remote` 查服务），不负责把工具接进助手；**npm 的 `misakanet` 是 skill/插件包**
> （`SKILL.md` + DSH 插件入口），早期它只有说明书、没有工具——工具来自第 ① 层的服务。

### 装完你得到什么（逐条可自检）

1. **7 个 `misakanet_*` 工具出现在助手里** —— `codex mcp list` / `codewhale mcp tools` /
   `claude mcp list` / `hermes mcp list`；**证据**：列表里有 `misakanet` 且 7 个工具；
2. **助手被要求「遇错先查」** —— 问一句「switch vision model」「context window exceeded」这类片段，它应该先说查过经验库；
   **证据**：事件流里出现 `misakanet_search`（claude/codewhale 用 `--output-format stream-json`，codex 用 `--json`）；
3. **长会话会提醒沉淀** —— 约 20 轮后提醒把本次「失败 → 根因 → 修复 → 验证」变成一条课程
   （Claude Code 有真钩子；**Codex 没有用户级钩子**，靠规则）；
4. **每 14 天最多一行升级提示** —— 只提示，绝不在背后安装任何东西；
5. **随时可撤** —— `--verify` 看状态，`--uninstall` 还原（改写前会留 `.misakanet.bak` 备份）。

**不想用命令行、不知道配置文件在哪？** 把下面这句话**复制粘贴给助手**，它会自己装好、自己验证、用大白话回报：

```text
帮我接入 MisakaNet 失败记忆库：请读取 https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/INSTALL_FOR_ME.md ，按里面的「第 2 部分：给你的要求」执行，做完用中文简单告诉我结果。
```

网络打不开上面那条网址时（部分网络会拦 `raw.githubusercontent.com`），把开头换 CDN 镜像：

```text
帮我接入 MisakaNet 失败记忆库：请读取 https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main/integrations/agent-autostart/INSTALL_FOR_ME.md ，按里面的「第 2 部分：给你的要求」执行，做完用中文简单告诉我结果。
```

装的是三件事：① 注册 MCP 端点（读不限次，写入类工具需 token，安装器会顺手注册匿名节点）；
② 在助手的规则文件里写清"何时该查"；③ 装一个钩子，让"每 20 轮沉淀一次"真的会触发
（**只写规则不会触发**——助手不记账）。细节与支持度矩阵见
[integrations/agent-autostart/README.md](integrations/agent-autostart/README.md)，
非技术用户看 [INSTALL_FOR_ME.md](integrations/agent-autostart/INSTALL_FOR_ME.md)。

_本节原在英文 README 开头（2026-09-20 结构重排时搬到这里）：英文 README 之前要求读者先读 121 行中文,
现在两边各自读到自己的语言。_
