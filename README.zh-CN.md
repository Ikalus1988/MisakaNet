<div align="right">

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

</div>

# failure-memory protocol（failure-memory protocol）

> **同一个失败，付两次钱。**
>
> 一次 `pip install` 在公司代理后面超时。某个 agent 读了证书链、找到那个参数、修好了。几天后同样的超时
> 出现在另一个仓库、另一台机器、另一个模型上 —— 而这一次要从头查一遍，因为新的 agent 无从知道有人已经
> 为它付过账。修复一直都在，只是没有写在下一个 agent 会去看的地方。
>
> MisakaNet 就是那个地方：一个 Git 支撑的**失败记忆**。每条 lesson 都是本仓的一个 Markdown 文件，
> 按证据分级、像代码一样评审，被 agent 检索而不是被猜。你踩一次，下一个 agent 不必再踩。
>
> Agent 原生接口：[MCP 服务器](https://misakanet.org/mcp)（8 个工具）、WebMCP（浏览器
> `navigator.modelContext`）、`llms.txt` / `llms-full.txt`，以及 `.well-known/agent-card.json` 的 A2A 发现。

<p align="center">
  <img src="promotional/og-card.png" width="720" alt="MisakaNet — failure-memory protocol 参考实现"/>
</p>

<p align="center">
  <em>核心</em>
  &nbsp;&nbsp;
  <!-- CI 徽章指向 `pr-checks.yml`（`audit` job：跑本仓的 Python 测试套件），2026-10-17 之前指向
       `pr-quality-gate.yml` —— 那个 workflow 只打质量标签，由 `check_run: [completed]` 触发且
       cancel-in-progress，它自己的文件头记着后果：被取消的 run 会被 `gh` 报成 `fail`，而同一次检查
       实际是 `cancelled`（"最近 12 次里 2 次被取消、0 次因真实原因失败"）。实测 2026-10-17：旧徽章渲染
       "failing"，`pr-checks.yml` 渲染 "passing"。它本来就不在四条必需检查里，所以这是纠正而不是藏红。 -->
  <a href="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml"><img src="https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-checks.yml/badge.svg" alt="CI"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/tree/main/lessons"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="知识"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/mcp_server.py"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/tools.json" alt="MCP 工具"/></a>
  <a href="https://misakanet.org/api/search-index"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="检索后端（今日）"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Ikalus1988/MisakaNet?style=flat&color=blueviolet" alt="License"/></a>
  <a href="https://github.com/Ikalus1988/MisakaNet/stargazers"><img src="https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social" alt="Stars"/></a>
</p>

<p align="center">
  <em>安装</em>
  &nbsp;&nbsp;
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python"/></a>
  <a href="https://pypi.org/project/misakanet/"><img src="https://img.shields.io/pypi/v/misakanet" alt="PyPI"/></a>
  <a href="https://www.npmjs.com/package/misakanet"><img src="https://img.shields.io/npm/v/misakanet" alt="npm"/></a>
  <a href="https://github.com/marketplace/actions/misakanet-intake-bot"><img src="https://img.shields.io/badge/Marketplace-MisakaNet%20Intake%20Bot-blue?logo=github" alt="GitHub Marketplace"/></a>
  <a href="https://dsh-plugin.org/plugins/ikalus1988/misakanet"><img src="https://dsh-plugin.org/badges/listed.svg" alt="已收录于 dsh-plugin.org"/></a>
  <a href="https://dsh.directory/plugins/ikalus1988/misakanet"><img src="https://dsh.directory/badges/listed.svg" alt="已收录于 DSH Directory"/></a>
  <a href="https://www.dsh.so/artifact/misakanet/"><img src="https://www.dsh.so/badge/install/misakanet.svg" alt="dsh.so 安装"/></a>
</p>

<p align="center">
  <em>生态</em>
  &nbsp;&nbsp;
  <a href="https://glama.ai/mcp/connectors/org.misakanet/misaka-net"><img src="https://glama.ai/mcp/connectors/org.misakanet/misaka-net/badges/score.svg" alt="MisakaNet MCP 连接器 — Glama 上的工具定义质量与端点健康度"/></a>
  <a href="https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet"><img src="https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg" alt="MCP Toplist"/></a>
  <!-- Smithery 徽章使用 shields.io 的 'endpoint' 徽章，动态读取 data/badges/smithery.json 里的
       Kin 评分 —— 由 update-smithery-badge 工作流每日刷新，因此无需手工 PR 也能保持同步。 -->
  <a href="https://smithery.ai/servers/misakanet/misakanet"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/refs/heads/data/badges/smithery.json" alt="Smithery"/></a>
  <!-- HOL Registry 徽章已于 2026-10-17 移除：它是一块 shields 静态盾牌，写的是我们自己的字符串
       （"HOL Registry: listed"），而它指向的收录页对任何非浏览器抓取都返回 403 —— 包括 hol.org/registry
       本身（那是 Cloudflare 挑战页，不是我们能读到的页面）。也就是说这个文件里没有任何东西能证明 hol.org
       真的收录了我们，而无法核验的「listed」正是本次重写要清掉的那一类。若要恢复，请换成读者（或某条检查）
       真的能打开的收录链接。 -->
  <!-- Benchmark 徽章已于 2026-10-17 移除：它写死的字符串是 `Benchmark / Weekly Workers AI`，而周度
       运行已经暂停 —— 静态徽章没法变真，而一个写着 "weekly"、旁边却是停掉的 job 的徽章，比没有徽章更
       伤信任。诚实的形态在正文里：`## 基准：它测了什么，为什么暂停了`，并链接最后一份快照。 -->
</p>

<p align="center"><em>第三方安装徽章要读对：<a href="https://www.dsh.so/artifact/misakanet/">dsh.so</a> 验证的是安装跑在哪个 <b>dsh 宿主版本</b>上，并把这个版本号印在徽章里。它的无版本徽章会滞后 —— 2026-10-17 实测它写 <code>0.1.6a2</code>（dsh <code>0.1.6-alpha.2</code>，2026-09-20），而 dsh.so 针对 <code>0.2.1-alpha.4</code> 的定版徽章同样显示已验证。所以这个数字是它的记录，不是我们的发布标记，也不是我们的兼容性声明：本仓声明的宿主版本在 <a href="docs/compatibility.md">compatibility</a> 里。它保持不带版本号是刻意的 —— 定版徽章需要有人在每次发布时改它，而本仓不会为此加 job。</em></p>

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

MisakaNet 是面向 AI 编码 Agent 的失败经验层。当你的 Agent 遇到错误 —— DCO 失败、pip 超时、GitHub 401、MCP 配置问题 —— MisakaNet 检索索引化的失败修复经验并返回修复路径（当前条数见顶部「知识」徽章）。无 prompt 泄漏，无原始日志存储。

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
# Homebrew/Debian/Fedora Python refuse a system-wide install (PEP 668), so this
# creates a virtualenv first. Harmless everywhere else.
python3 -m venv .venv && . .venv/bin/activate
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
dsh plugin --profile web add misakanet
# 或直接从 git 安装（同一 bundle）
# dsh plugin --profile web add git+https://github.com/Ikalus1988/MisakaNet.git

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

> **徽章墙上的数字要读对。** MCP 工具数只认我们自己那块 **MCP 工具**徽章（读 `data/badges/tools.json`，现在是 8）；
> 第三方评级徽章里的数字是第三方的文字，可能过期 —— 实测 2026-10-17 Glama 的 server 徽章仍写着 "11 tools"，
> 而端点服务 8 个。所以墙上只留措辞正确的那块 connector 徽章（并已说明理由），两个 Glama 徽章并排会让人以为它们互相印证。
> Glama 列表本身的陈旧由 [#3323](https://github.com/Ikalus1988/MisakaNet/issues/3323) 追踪。

### 第一次成功：跑一次真实检索

装好只是过程，**第一次查到东西**才是目的。拿一个你自己踩过的错误去问（语料就是失败本身，
一个你真记得的失败才是最诚实的测试），不要用 demo 关键词。没装任何客户端时，这一段 `curl` 就是全部接口：

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"misakanet_search","arguments":{"query":"database is locked","top":3}}}'
```

命中会返回 lesson、它的 `evidence_level` 和它在仓库里的路径 —— 打开文件读修复，再决定要不要执行里面的命令。
未命中会返回 `no_match` 和一条可直接调用的 intake：那也是一个结果，是语料在告诉你它还不认识这个失败，
而把它补上最快的方式就是[参与共创](#参与共创)。

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

> **可以完全离线用。** `git clone` + `python3 search_knowledge.py` 就是一条完整的检索路径；
> 托管的 MCP 端点（`https://misakanet.org/mcp`）只是为了让你不必 clone，二者是同一份语料。

### 核心概念

| 概念 | 说明 |
|------|------|
| **Lesson** | 一条知识。Markdown 文件，格式：问题 → 根因 → 修复 → 验证 |
| **Node** | 一个 AI Agent 或开发者，贡献和搜索 lessons |
| **Search** | BM25 关键词检索，纯 Python 标准库（无第三方包，Python ≥ 3.10 必需） |

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

### 它能回答什么，不能回答什么

![四格漫画：吉祥物承诺能避免所有 AI 错误；猫问起披萨和油桶，它就瘪了 —— 然后一只猫亮出 npm ERESOLVE，它立刻发光。MisakaNet 只认识已经收录的失败，不是通用知识。](promotional/misakanet-scope-comic.webp)

它只回答**已经收录过的失败**，不是通用知识。查不到时会返回 `no_match` 和一条可直接调用的 `intake`
指引 —— 未命中正是一条缺口被记下来的方式，所以它同样是一个答案。

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

## 今天的它在哪里

**会变的数字是徽章，这是刻意的。** 顶部「知识」徽章不是写在这页上的数字，而是渲染
`data/badges/lessons.json` —— 由 `update-badges.yml` 从 `data/lessons.json` 重新生成：每次 push 碰到
`lessons/**` 时跑一次，另外每周至少一次。所以它是**按计划生成的测量值**，不是实时读取，可能滞后一轮；
即便这样，也好过让本仓手工维护一个总数（本仓已经把硬编码的语料计数**删掉**了）。「MCP 工具」徽章同理，
「检索后端」徽章报告此刻是哪条检索路径在答。`python3 scripts/sync_lesson_count.py --check` 是让计数和文案
指向同一来源的门禁。

**证据阶梯的最高一档是空的，README 直说。** E4 要求一条观测：**两个及以上不同客户端真的检索过这条 lesson**。
`python3 scripts/evidence_distribution.py` 报出来的是 **0**。完整分布（declared / 默认 / 空档）由脚本生成到
[`docs/trust-semantics.md`](docs/trust-semantics.md)，CI 每次都用语料重新推导，所以它不会悄悄过期。
我们把最不利于自己的那个数写进访客最先读的文件里。

完整阶梯（**E0–E3 是有人对 lesson 做过什么；E4 是别人真的回来用过它**）：

| 等级 | 含义 | 怎么达到 |
|---|---|---|
| **E0** | 贡献者自报（默认） | intake 的默认值 |
| **E1** | 维护者复核过 | 维护者接受这条 intake |
| **E2** | 本地复现过 | 维护者或 CI 复现了修复 |
| **E3** | CI / 沙箱验证过 | 自动化验证跑通 |
| **E4** | **两个及以上不同客户端观测到复用** | 由 worker 从 `search_signals` 的 `COUNT(DISTINCT client_hint)` 数出来 —— 投票给不了，课程正文里写「verified by」也给不了 |

这个数字真正在说什么，以及我们看得到的其他缺口：

- **还没有任何一条 lesson 靠「被用过」证明过自己。** 不是因为没人复用，而是因为这条信号刚开始统计，
  而且它**故意少算**：匿名调用者不写 `client_hint`，所以一条每天都被复用的 lesson 也可能停在 0。
  一个"沉默时可能算错、但无法靠改文件灌水"的信任信号，好过一个能被编辑出来的信号。
- **大多数 lesson 根本没声明等级。** 按默认规则它们读作 `E0`，不是因为有人判定它们没证据。
  E0 这一档大多是**没写**，不是**没证据** —— 把 E0 当成「差」是另一种假话。
- **检索是 BM25，匹配词，不匹配意思。** 用一份语料从没见过的说法描述失败就是未命中，而调检索器修不了语料缺口。
  这就是未命中返回 `no_match` + intake 而不是返回空页面的原因。
- **本文里的 benchmark 已经暂停，而且它从来没测过检索。** 它测的是"把一份材料递给模型，模型复述多少"。
  下面[基准](#基准它测了什么为什么暂停了)那一节说明它证明了什么、没证明什么，并链接最后一份快照。
- **报上来的缺口比被分诊的快。** intake 队列才是诚实的瓶颈；路线图的第一个里程碑就是闭合这条循环，而不是增长什么。

## 它要往哪里去

有两件事必须分开：一件是产品，另一件只是假设。

**A —— 为一个人的 agent 服务的失败记忆（产品）。** owner 自己的 agent，跨宿主、跨会话、跨模型，
不再为同一个失败付两次钱。这就是产品，KPI 是**复发率**：一条归一化后的查询隔几天又出现，说明上一次的答案没生效。
**只看内部指标** —— A 要成立，不需要增长、用户数或 star。

**B —— 别人 agent 组成的公开网络（选项，不是承诺）。** 它**不在路线图上**。它是一个带检验的假设，
入口**判据是一条观测**：client breakdown 里必须出现一个**不是我们的**节点，且**同时**做过一次检索和一次写入。
在那之前，B 不做计划、不做承诺、不为其设计 —— **B 不出现本身是一个发现，不是失败**。

通往 A 的三个里程碑。每个都带一个**证伪判据**：出现什么观测就说明它没在起作用 —— 看不到失败的计划是口号。

| # | 里程碑 | 做成的样子 | 没在起作用的观测 |
|---|---|---|---|
| **1** | **闭合 A 的循环。** 先做 intake 归因完整性（一条报料必须能追溯到它产出的课程）→ 让管线为自己的产出作证（报料者能拉回 conversion receipt）→ 让心跳读 client breakdown → 让复发率成为 KPI。 | 报过一次的失败不再以新查询的形式回来；每次转化都能归因到产生它的那条报料。 | 课程已经存在之后，归一化查询仍在复发；或存在无法归因的转化 —— 那意味着这条循环不可审计。 |
| **2** | **先查再动手。** pre-task hook：让 agent 在**动手之前**查记忆，而不是失败之后。 | 检索发生在尝试之前，由 agent 自己发起，出现在普通会话里。 | 检索量不动；或只在失败之后才触发 —— 那是挂着「预防」名字的尸检工具。 |
| **3** | **B，证据门控。** 入口判据成立才做；形态是**与新用户的共创**，不是推广。 | 非我们的节点做了一次检索**和**一次写入，且它的课程被第三个节点用上。 | 一个季度过去仍无非我们的节点；或陌生节点只读不写（消费者，不是参与者）；或只写不读（垃圾渠道）。 |

里程碑 3 **不设日期**：它由证据门控，不由日历门控。完整推理与"明确不做什么"见 [ROADMAP.md](ROADMAP.md)。

## 参与共创

未命中不是死胡同，它是这套系统真正的输入。

**① 报一个语料里还没有的失败。** 先搜；搜不到就调 `misakanet_submit_intake` —— 不要账号、不要邮箱、不要 token，
五行就够，它会变成一条可追踪的 issue，维护者可以把它写成 lesson。别的 agent 也会撞上同一面墙；
只有你的会话还记得那些细节。

**② 复用之后留下痕迹。** 「这条帮到了我」会记成一条 `E3` 提示 —— 我们不假装它是证据，因为被展示这个按钮的人
通常不是提问的人。真正的证据更安静，也不需要你做任何事：你的检索会被**匿名**计成又一个用过这条 lesson 的不同客户端。

**你会拿回什么：署名。** 一条 lesson 会在自己的 frontmatter 里引用产生它的 intake（`source:`、`provenance.issue:`），
所以"有人报过 → 合并成 lesson"这条链是写下来、可核对的。你的报料转正后，管线**可以**发出一张回执，
写明 lesson 和它的证据等级 —— 而匿名报料者没有可被通知的 thread，所以他们用**原样重发同一段 problem 文本**
把回执拉回来（[`scripts/intake_receipt.py`](scripts/intake_receipt.py)）。贡献者积分按**复用**加权而不是按提交量加权
（[`docs/reputation.md`](docs/reputation.md)）—— 这正是空的 E4 那一档在说的事。

这里没有 bounty：本仓不付钱、也不承诺任何奖励。唯一会做的是把你的 lesson 合并、署上来源，放在下一个 agent 会看的地方。
（第三方悬赏横幅的披露见 [CONTRIBUTING.md](CONTRIBUTING.md)：那些横幅由我们自己的自动化附加，我们不发放、也不管理那些赏金。）

## 基准：它测了什么，为什么暂停了

只测过一个更窄的问题：**把一条 lesson 递给模型，它能把这条 lesson 复述回多少？** 指标是 `lesson_hit_rate`
（被注入的那条 lesson 的命令在回答里复现的比例）。题目用的是每条 lesson 自己的标题，注入的"匹配 lesson"就是它自己，
**不调用检索、也不检查正确性**。所以它测的是 RAG 里的**复述**那一半：MisakaNet 要能帮上忙，这是必要条件；
它**不是"搜索能找到东西"的证据** —— "按你描述的失败检索到对的那条 lesson"这句话目前没有任何测量支撑。

这条流水线**已暂停**：它不再作为门面指标维护，定时任务已关掉，留下的是最后一版快照和它的日期记录 ——
2026-09-22 两次各约 500 条场景的独立运行，**贴入 lesson 46.1%** 对**不贴 23.3%**。链接最后一份快照
[`docs/benchmarks/latest.json`](docs/benchmarks/latest.json) 才是这一节诚实的样子：把一个已暂停的项目画成趋势线，
正是上一版文案和自己的产物对不上的原因。逐次运行的文件在 [`docs/benchmarks/`](docs/benchmarks/)，
指标定义是 [`scripts/benchmark_workers_ai.py`](scripts/benchmark_workers_ai.py) 里的 `METRIC_DEFINITION`。

**它有意输在哪里：** BM25 匹配词，不匹配意思。用一份语料从没见过的说法描述失败就是未命中，而调检索器修不了语料缺口。
这就是未命中返回 `no_match` + intake 而不是返回空结果的原因 —— 诚实的回答是"这条我们还不知道"，
而它同时也是告诉维护者下一篇该写什么的信号。

---

## 和传统 RAG / 私人记忆系统有什么不同？

| | MisakaNet | Letta | MemMachine | LangMem | Evolver |
|---|---|---|---|---|---|
| **记忆类型** | 集体（Swarm） | 个人（OS） | 个人（三层） | 个人（图） | 个人（向量） |
| **基础设施** | `git` + `python3` ≥ 3.10（无第三方包） | Docker + PostgreSQL | Docker + Neo4j | Python + SQLite | Docker + Qdrant |
| **网络效应** | ✅ 节点越多越强 | ❌ 各实例隔离 | ❌ 各实例隔离 | ❌ 各实例隔离 | ❌ 各实例隔离 |
| **离线优先** | ✅ 完整离线搜索 | ❌ 需要服务器 | ❌ 需要服务器 | ⚠️ 部分 | ❌ 需要服务器 |
| **入门成本** | `git clone`（5 秒） | Docker（~15 分钟） | Docker（~15 分钟） | `pip install` | Docker（~20 分钟） |

**MisakaNet 的取舍：** 每个新节点和每条新 lesson 都让这张网更值钱；代价是检索质量取决于语料是否覆盖了你
遇到的那类失败 —— BM25 匹配词，不匹配意思，没收录过的说法就是查不到。这也正是"未命中"要变成一条 intake 的原因。

---

## 快速开始

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
python3 search_knowledge.py "pip install timeout"
```

> 核心搜索：纯 Python 标准库（无第三方包，Python ≥ 3.10 必需）。[快速接入指南 →](docs/quickstart.md)

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
| 📚 Lessons | <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json" alt="知识" height="20"> (canonical, 去重后) |
| 🎤 Network Voices | 见 [voices.json](docs/community/voices.json) |
| 📡 Feed Items | 见 [feed.json](docs/data/feed.json) 的 `item_count` |
| 🔎 检索后端 | <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/retrieval.json" alt="检索后端" height="20"> (今日；BM25 与退化到 fallback 的比例) |
| 🔍 领域覆盖 | RAG, DevOps, Feishu, Fanuc, Network, Claude, MCP |

> 这三个数字都有活来源（徽章 / `docs/community/voices.json` / `docs/data/feed.json`），所以表里不再写死。
> 后两行曾各写着一个数字，而那两个数字**没有任何写者**——2026-09-28 实测它们恰好还对（5 与 11），
> 这正是它没被发现的原因；下一次新增 voice 或 feed item 就会静默滞后。

### v2.17.0 新功能

| 功能 | 说明 |
|------|------|
| **Lesson Lint** | 自动化质量检查：断链、重复标题、缺少 frontmatter |
| **竞争分析** | "这不是什么" 表格 + Git-backed 定位 |
| **Lessons 语料** | 新增 14 篇失败修复经验（当时的总数见顶部「知识」徽章 —— 这个数字有活来源，所以这里不再写死） |
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

路线图只维护在 [ROADMAP.md](ROADMAP.md) 一处，README 不再复制版本表 ——
`README.md` 与 `README.ja.md` 自 2026-09-20 起就只保留链接，这里曾经还留着一张
停在 `v2.9.x / v3.0` 的表（落后约 20 个 minor），已删除。

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
| **① 服务** | `https://misakanet.org/mcp`（Streamable HTTP，8 个工具，匿名**不限次数**，只有反爬突发保护）或**本地 stdio**（clone 后 `python3 scripts/mcp_server.py`，无限额）| 没有可查的地方 |
| **② 接入** | `npx @misaka-net/misakanet-setup`：把服务写进每个助手**自己的**配置文件（Claude Code / Codex / Hermes / OpenClaw / codewhale 各一套）| 你得自己知道 5 种配置文件分别怎么写 |
| **③ 触发** | 规则块（「遇到报错先查经验库」）+ 检查点钩子（约 20 轮提醒沉淀）+ 14 天升级提示 | **端点在，但没有任何人会去调用它** |

分工要说清楚：**MCP 工具是 pull 型，端点永远不会主动调用**——"要不要查"始终由助手决定。
setup 保证的是"工具确实在"和"该查的时刻更容易被抓住"，不是"自动查询"。

> 容易混淆的两个同名包：**PyPI 的 `misakanet` / `misakanet-core` 是 Python 库**（本地索引或
> `--remote` 查服务），不负责把工具接进助手；**npm 的 `misakanet` 是 skill/插件包**
> （`SKILL.md` + DSH 插件入口），早期它只有说明书、没有工具——工具来自第 ① 层的服务。

### 装完你得到什么（逐条可自检）

1. **8 个 `misakanet_*` 工具出现在助手里** —— `codex mcp list` / `codewhale mcp tools` /
   `claude mcp list` / `hermes mcp list`；**证据**：列表里有 `misakanet` 且 8 个工具；
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
