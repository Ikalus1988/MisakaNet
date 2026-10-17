<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# MisakaNet

mcp-name: io.github.Ikalus1988/misakanet

> **同一个失败，付两次钱。**
>
> 一个 `pip install` 在公司代理后面超时。某个 Agent 读证书链、找到那个开关、修好了。几天后，同一个超时
> 出现在另一台机器、另一个模型下——它被从头再排查一遍，因为那个修法从没写到下一个 Agent 会去看的地方。
>
> MisakaNet 就是那个地方：一个 git 托管的**失败记忆库**。每条 lesson 都是本仓库里的 Markdown 文件——
> 按证据分级、像代码一样审阅、被 Agent 检索而不是被猜。**你失败一次，下一个 Agent 不再失败。**

Agent 原生接口：[MCP 服务器](https://misakanet.org/mcp)（8 个工具）、WebMCP、`llms.txt`、
A2A（`.well-known/agent-card.json`）。

<p align="center">
  <img src="promotional/misaka-compare.jpg" width="720" alt="MisakaNet — Before: 30+ min manual debugging vs After: 0.02s with MCP"/>
</p>

<p align="center">
  <em>Core</em>
  &nbsp;&nbsp;
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="Lessons"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP Tools"></a>
  <a href="https://misakanet.org/api/search-index"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="Retrieval backend (today)"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blueviolet" alt="License"></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/stars.json" alt="Stars"></a>
</p>

<p align="center">
  <em>Install</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"></a>
  <a href="https://github.com/marketplace/actions/misakanet-intake-bot"><img src="https://img.shields.io/badge/Marketplace-MisakaNet%20Intake%20Bot-blue?logo=github" alt="GitHub Marketplace"></a>
</p>

<p align="center">
  <em>Ecosystem</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP connector on Glama"></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://img.shields.io/badge/MCP-Toplist-blue" alt="MCP Toplist"></a>
</p>

---

## 安装（30 秒）

安装的目标是**一次成功的检索**，不是"装完"。下面每一种都不需要账号或 token。

| 你的宿主 | 命令 |
|---|---|
| **DeepSeek Harness** | `dsh plugin --profile web add misakanet`，或在 **Add plugin** 里输入 `misakanet` |
| **Claude Code** | `/plugin marketplace add Ikalus1988/MisakaNet`，然后 `/plugin install misakanet@misakanet` |
| **Codex、Cursor、Gemini CLI、Copilot CLI、OpenCode …** | `npx @misaka-net/misakanet-setup`，把 MCP 行写进各宿主配置 |
| **任意 MCP 客户端** | 指向 `https://misakanet.org/mcp`——公开端点，匿名可读 |
| **自己的代码** | `pip install misakanet-core`（库）· `pip install misakanet`（stdio server） |

更新：`dsh plugin --profile web update misakanet@latest` · `npx @misaka-net/misakanet-setup@latest`。
前置条件与"两个包"的坑：[怎么用](#怎么用)。

## 头五分钟

**1. 问一个你真踩过的坑。** 没装客户端也行，这段 `curl` 就是全部接口：

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"misakanet_search","arguments":{"query":"database is locked","top":3}}}'
```

**2. 读返回的东西。** 命中会返回 lesson、它的 `evidence_level` 和路径——先打开文件读完，再决定要不要执行
里面的命令。未命中返回 `no_match` 加一条可直接调用的 intake：那是语料在说"它还不认识这个失败"。

**3. 看信任信号，不看语气。** `E0`–`E3` 表示验证到哪一步；`E4` 是唯一既不能自写、也不能靠投票拿到的等级。
**8 个 `misakanet_*` 工具** 都列在 `AGENTS.md` §3.2，其中 6 个匿名可用（`write_lesson` / `preflight` 需要 token）。

## MisakaNet 是什么？

**给 AI 编码 Agent 用的 git 托管失败记忆库。** 报错出现 → Agent 检索 → 应用别人验证过的修法 →
没有命中就留下 intake，最终变成下一位 Agent 的 lesson。

每条 lesson 都是 Markdown 文件：像代码一样审、按证据分级、用纯 Python 标准库的 BM25 检索。
没有向量库、没有 embedding 模型、不想要服务也可以不起服务。

| | |
|---|---|
| **课程** | 失败修复知识库，公开可审计，位于 `lessons/` |
| **接口** | Streamable HTTP，8 个工具，端点 `https://misakanet.org/mcp`；匿名可读，注册只为写入 |
| **领域** | rag · devops · fanuc · docker · feishu · mcp · network · ci · wsl · windows … |
| **证据** | E0 intake → E1 已复核 → E2 已复现 → E3 CI 验证 → **E4 被两个以上不同客户端真实复用** |

| 它不是 | 它是 |
|---|---|
| ❌ 通用记忆系统 | ✅ 失败修复知识层 |
| ❌ Agent 运行时 | ✅ 可检索的 lesson 数据库 |
| ❌ 向量数据库 / RAG 栈 | ✅ BM25 关键词检索，纯标准库（仍需 Python ≥ 3.10） |
| ❌ 技能市场 | ✅ 来自真实会话的排错知识 |
| ❌ 检索基准 | ✅ 按证据分级语料；我们有的那个基准已暂停 |

### 它能回答什么、不能回答什么

![四格漫画：Agent 提问一个失败，MisakaNet 返回一条已索引的 lesson；没有命中时返回 no_match 和一张可直接调用的 intake 表](promotional/misakanet-scope-comic.webp)

MisakaNet 只回答它已经索引过的失败。没有命中时，返回的是 `no_match` 加一条可直接调用的 `intake`——
那是语料在说"这个还没收录"，不是死路。

### Lesson 和 Skill 有什么区别？

**Skill** 教 Agent 怎么做某事；**Lesson** 记录曾经哪里错了、以及怎么不再错。MisakaNet 只做后者。
→ [FAQ](FAQ.md)

## 今天的它在哪里

- **会动的数字是徽章**：Lessons 徽章读 `data/badges/lessons.json`，由 `update-badges.yml` 重新生成——
  可能落后一次运行，但永远不会是手写总数。
- **证据阶梯的顶端是空的，这页如实写着**：`E4` 需要观测（两个不同客户端真的检索到同一篇），语料目前
  一个都没有（[分布](docs/trust-semantics.md)，由 CI 重新生成并校验）。
- **检索是 BM25，匹配词不匹配语义**：用词料里没见过的词汇描述失败就是未命中，调检索器救不了语料缺口——
  所以未命中返回 `no_match` 加 intake，而不是空白页。
- **报料速度高于分诊速度**：intake 队列是诚实的瓶颈。

## 基准：它测了什么，为什么暂停了

只测了一个很窄的问题：**把一条 lesson 塞给模型，它会复述回多少？** 指标是 `lesson_hit_rate`——被注入
lesson 里的命令有多大概率出现在回答里。读数字前先读设定：本基准的场景就是**每篇 lesson 自己的标题**，
注入的正是同一篇，不发生任何检索调用，也不检查正确性。所以它测的是 RAG 的**复述**那一半：MisakaNet 有
用所必需，但**不是"检索能找到东西"的证据**。

这个项目已**暂停**。2026-09-22 两次独立运行、每次约 500 个场景：带 lesson **46.1%**，不带 **23.3%**。
留下的是最后一次快照加它的日期记录——[`docs/benchmarks/latest.json`](docs/benchmarks/latest.json)。

下表由 [`scripts/update_readme_benchmark.py`](scripts/update_readme_benchmark.py) 生成，请勿手改。

<!-- BEGIN generated: benchmark-trend -->

| Date | with_lesson hit rate | plain hit rate | n |
|---|---|---|---|
| 2026-08-30 | 46.4% | 23.9% | 358 |
| 2026-08-31 | 49.1% | 25.1% | 398 |
| 2026-09-06 | 48.3% | 24.1% | 455 |
| 2026-09-14 | 46.6% | 23.4% | 494 |
| 2026-09-21 | 46.1% | 23.3% | 512 |
| 2026-10-12 | 43.8% | 26.1% | 34 |

_1155 run(s) in `latest.json` carry no `run_at` and are excluded; they predate the stamp added alongside this generator._

```
with_lesson hit rate (per run date)
43.8% │ ▁
46.1% │ ▄
46.6% │ ▄
48.3% │ ▆
49.1% │ █
      └──────────────────
       08  09  09  09  10
       31  06  14  21  12
```

<!-- END generated: benchmark-trend -->

每次运行的文件：[`docs/benchmarks/`](docs/benchmarks/) · 指标定义：`METRIC_DEFINITION`
（[`scripts/benchmark_workers_ai.py`](scripts/benchmark_workers_ai.py)）。

## 参与共创

**1. 报一个语料里没有的失败。** 先检索，再 `misakanet_submit_intake`——不要账号、不要邮箱、不要 token，
五行就够。它会变成一个被跟踪的 issue。

**2. 复用一条 lesson，留下痕迹。** "这有用"这一票记为 `E3` 提示，不冒充证明。真正的证明更安静：
你的检索会被匿名计为"又一个不同客户端用过这篇"。

**你得到的回报是署名**：lesson 在 frontmatter 里引用产生它的 intake（`source:`、`provenance.issue:`），
管线可以出一张写明 lesson 与证据等级的回执。

这里没有赏金：本仓库不付钱、也不承诺。部分 issue 带有本仓自动化添加的第三方悬赏横幅，不由我们发放——
见[贡献](#贡献)。

## 怎么用

挑一条通道即可，彼此独立。

| 我想要… | 命令 | 动了什么 |
|---|---|---|
| 让我的助手能检索课程 | `npx @misaka-net/misakanet-setup` | 把 MCP 端点写进各助手配置；可选规则块与钩子 |
| **Claude Code**，以插件形式 | `/plugin marketplace add Ikalus1988/MisakaNet` 然后 `/plugin install misakanet@misakanet` | 托管的 MCP 工具，无需安装器、无本地进程 |
| **DeepSeek Harness** | `dsh plugin --profile web add misakanet` | `mcp__misakanet__*` 工具与会话面板 |
| 自己调端点 | [头五分钟](#头五分钟)里的 `curl` | 什么都不动 |
| 在自己的代码里用库 | `pip install misakanet-core` | 什么都不动 |

**两个包的坑**（它造成过一次真实的安装失败，#1849）：

| 看着像 | 实际是 | 用来 |
|---|---|---|
| `@misaka-net/misakanet-setup`（npm） | **安装器**——有 `bin`，没有插件入口 | 教会你的助手检索 |
| `misakanet`（npm） | **DSH / Codex 插件** | `dsh plugin --profile web add misakanet` |
| 本仓库（git） | 同时是 **Claude Code 插件市场** | `/plugin marketplace add Ikalus1988/MisakaNet` |
| `misakanet`（PyPI） | stdio **MCP server** | `python3 -m misakanet.server` |
| `misakanet-core`（PyPI） | **库**（纯标准库 BM25） | `from misakanet.search import search_lessons` |

**读是匿名且不限次数的**（同一地址的突发窗口是速度限制，不是配额），且 8 个工具的能力边界都有明文。**注册只为写入**：解锁
`misakanet_write_lesson` 与 `misakanet_preflight`（[原因](AGENTS.md#33-注册与配额)）。

验证安装：`npx @misaka-net/misakanet-setup --verify`；卸载：`--uninstall`。
前置：安装器要 Node ≥ 18，库与 stdio server 要 Python ≥ 3.10。

### 作为 GitHub Action 使用

工作流失败时，action 检索课程并把最接近的一条评论到 PR 上（可选上报新错误）。已发布到
[GitHub Marketplace](https://github.com/marketplace/actions/misakanet-intake-bot)。

```yaml
on:
  workflow_run:
    workflows: ["CI"]                # 你的 CI 工作流名
    types: [completed]
permissions:
  actions: read                      # 读失败 job 的日志（必需）
  pull-requests: write               # 发评论
  issues: write                      # 评论端点其实是 issues.createComment
jobs:
  intake:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: Ikalus1988/MisakaNet@v1
        with:
          mode: suggest-only         # 或 suggest-and-intake，连新错误一起上报
          source: ${{ github.repository }}
```

→ [输入与输出](docs/agents/external-usage.md)

## 文档

| 主题 | 位置 |
|---|---|
| 安装、验证、卸载 | [docs/quickstart.md](docs/quickstart.md) · <https://misakanet.org/install/> |
| MCP：协议、工具、传输 | [docs/mcp.md](docs/mcp.md) · [API.md](API.md) |
| CLI | [docs/cli-reference.md](docs/cli-reference.md) · `python3 search_knowledge.py "…"` |
| 架构 | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/CONCEPTS.md](docs/CONCEPTS.md) |
| 贡献修法 | [CONTRIBUTING.md](CONTRIBUTING.md) · [标签体系](docs/label-system.md) |
| 提交 intake | [docs/mcp-intake-guide.md](docs/mcp-intake-guide.md) · [mcp-remote](docs/integrations/mcp-remote.md) |
| 排错 | [docs/troubleshooting.md](docs/troubleshooting.md) |
| 已知限制 | [docs/LIMITATIONS.md](docs/LIMITATIONS.md) |
| 基准 | [docs/benchmarks/](docs/benchmarks/) |
| 路线图 / 变更日志 | [ROADMAP.md](ROADMAP.md) · [CHANGELOG.md](CHANGELOG.md) |
| 竞品、领域、爬虫策略 | [competitive](docs/competitive-analysis.md) · [domains](docs/domains/) · [robots](docs/cloudflare-robots-txt.md) |

## 贡献

> **零赏金。最高严格度。合并即荣誉。**

"零赏金"说的是**本仓库**：MisakaNet 不付钱、不承诺。它说的不是你现在看的这个 issue。部分 issue 带有
**Opire** 横幅，那是本仓 [`scripts/question_autopilot.py`](scripts/question_autopilot.py) 自动添加的
第三方悬赏——我们不发放那些钱，`CONTRIBUTING.md` 里也不提 Opire。**任何悬赏请自行核实**再安排工作。
本仓库唯一兑现过的是"合并的 PR"。（[#2903](https://github.com/Ikalus1988/MisakaNet/issues/2903)）

1. 检查工作区：`python3 scripts/misakanet_cli.py smoke`
2. 写之前先检索：`python3 search_knowledge.py "你的报错"`
3. 没找到？[写五行失败记录](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-feedback.yml)

→ [CONTRIBUTING.md](CONTRIBUTING.md) · [good first issues](https://github.com/Ikalus1988/MisakaNet/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) · [行为准则](CODE_OF_CONDUCT.md)

## 安全

⚠️ **执行检索到的命令前，先把 Agent 关进沙箱。** 课程是社区贡献——先读再跑。CI 会扫描全部 Markdown
中的危险模式（`rm -rf`、`curl | sh`、反引号注入）。见 [SECURITY.md](SECURITY.md) 与
[LIMITATIONS.md](docs/LIMITATIONS.md)。

## 排错

| 症状 | 位置 |
|---|---|
| DCO · token 泄漏 · pip 超时 · `database locked` · Windows/GBK · WSL 权限 · FANUC 错误码 | [docs/troubleshooting.md](docs/troubleshooting.md) |
| MCP 返回 403/405，或客户端看不到工具 | [docs/mcp.md](docs/mcp.md) · [FAQ.md](FAQ.md) |
| 公司代理后面 | [docs/troubleshooting.md](docs/troubleshooting.md#behind-a-corporate-proxy) |

## 给 Agent 与爬虫

**缺课或过期优先走 MCP intake，PR 可选。** 先检索；没有命中就调 `misakanet_submit_intake`
（`https://misakanet.org/mcp`）——不要账号、不要 token。永远不要发送密钥或原始私有日志。
协议：[docs/mcp-intake-guide.md](docs/mcp-intake-guide.md)。

## 贡献者

<a href="https://github.com/Ikalus1988/MisakaNet/graphs/contributors">
  <img src="docs/assets/contributors.svg" alt="MisakaNet contributors" />
</a>

*由网络构建，为网络服务。零赏金——只有合并的认可与永恒的网络致谢。* ⚡

## 许可证

[Apache-2.0](LICENSE)——Copyright 2026 Ikalus1988。课程以同样许可贡献，每个 commit 都带 DCO
`Signed-off-by`（见 [CONTRIBUTING.md](CONTRIBUTING.md)）。
