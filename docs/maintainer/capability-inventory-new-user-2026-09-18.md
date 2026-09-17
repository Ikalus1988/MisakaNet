# 新用户的 agent 到底得到了什么（能力清单 + 证据分级）

> 审计日期：2026-09-18（UTC 实测 2026-09-17 18:2x）。审计口径：只读、只发 GET、不注册、不 POST。
> 仓库基线：审计时在 `fix/setup-packaged-e2e`（`c88ceafcc`）；该分支已作为 PR #1818 合入 main（`b182013c6`）。
> 全文区分两种证据：**自证**（产品自己报的数/自己填的字段）与**外部可核**（npm/PyPI 下载、第三方 listing、
> 别人机器上的真机回报、会因为claim为假而失败的测试）。

## 1. 一句话结论

新用户的 agent 实际拿到的是**三样东西**：① `@misaka-net/misakanet-setup` 写进 5 套 agent 配置的一个 MCP 端点条目
（+ token，`packages/misakanet-setup/bin/misakanet-setup.mjs:846`、`:1196`）；② 追加到 `CLAUDE.md`/`AGENTS.md`/
`SOUL.md` 的一段**祈使句规则块**（`PROMPT_BLOCK`，`bin/misakanet-setup.mjs:532`）；③ Claude Code 上两个 hook
（`UserPromptSubmit` / `PostToolUseFailure`，`bin/misakanet-setup.mjs:760-761`）。

**凭什么这么说**：这三样都是**可复核的机器状态**——第三方 @2lll5 在隔离真机上的回报（issue #1753 评论，2026-09-16）
实测 `tools/list` 返回 7 个工具、匿名 `tools/call: http=200 name=misakanet_search result_present=true`
（原文见 `docs/field-reports/2026-09-16-setup-verification-2lll5.md`），且 `misakanet.org/mcp` 现在活着
（GET → `405 {"error":"Method Not Allowed. Use POST for MCP Streamable HTTP transport…"}`）。

**但"agent 因此变得更会干活"这件事，现在没有任何一条外部可核证据。** 仓库里唯一那句"lessons make models
smarter"（`README.md:392-401`，21%→43%、42%→73%）量的是 `lesson_hit_rate`，定义是把课程 Fix 段的命令关键词
是否出现在**模型回复文本**里（`scripts/benchmark_workers_ai.py:126-152`，`rate = hits / len(reference_commands)`，
`:143`）——它既不是安装器分发的机制（它把课程正文塞进 prompt，不是给 agent 一个工具），也不测任务是否成功。
仓库自建的两个"有/无 MisakaNet"对比基准在代码里是占位符（`bench/self-healing/run_benchmark.py:139`
`success = with_misakanet  # Placeholder — real implementation needed`）。维护者自己的评估文件也这么写：
"**我们对遵循率没有任何测量**"（`docs/maintainer/setup-value-assessment-2026-09-16.md:73-74`），
"到目前为止，**所有真机验证都来自同一台机器（WSL）**"（issue #1753 正文）。

## 2. 表格一：分发表面

| 表面 | 新用户怎么遇到它 | 现在是否可达（实测） | 版本/规模数字（来源） | 证据强度 |
|---|---|---|---|---|
| `@misaka-net/misakanet-setup`（npx 主路径） | `README.md:23` 第一屏命令 | **live**：registry 解析 `latest: 0.5.4`；tarball 内容实测 9 个文件 | 12 个版本，首发 `2026-09-14T11:41:04Z`（registry.npmjs.org）；下载 interval `2026-08-18:2026-09-18` 合计 **916**，但**只有 2 个非零日**：09-14=151、09-16=765 | **写入行为外部可核**（第三方真机回报 + 85 项测试）；**价值仅自证** |
| 规则块 `PROMPT_BLOCK` | 装完追加进 4 个助手的规则文件 | live（写文件成功即可见） | 17 行祈使句，6 条规则（`bin/misakanet-setup.mjs:532-543`） | (ii) 存在，**无任何用户价值证据** |
| Claude Code hook `checkpoint_reminder.mjs` | 装完进 `settings.json` hooks | live（代码在 tarball 内，`package/hook/checkpoint_reminder.mjs`） | 325 行；turn 20 起每 10 轮注入沉淀提醒（`integrations/agent-autostart/checkpoint_reminder.mjs:258-286`） | (ii) 测试只断言文件里有这个字符串（`tests/test_agent_autostart.py:95`） |
| 根 npm 包 `misakanet` | `dsh plugin add misakanet@2.30.2`（README Option 5） | **live**：`latest: 2.30.2`，tarball 14 个文件 | 下载 interval 合计 **429**；峰值 09-01=134、09-14=151、09-16=70，**与发布日重合**（2.23.0 于 09-01、2.30.0 于 09-14） | 包内容可核；"196/月的用户"不可归因 |
| PyPI `misakanet` | `pip install misakanet`（`README.md:162`） | **live 但文档命令跑不通**——见 §4.3 | 2.30.2（pypi.org JSON）；pepy.tech：`total_downloads: 6169`，近 14 天 2232 | (iii) **wheel 里没有 `search_knowledge` 模块** |
| MCP registry `io.github.Ikalus1988/misakanet` | 客户端内置 registry 搜索 | **live 但落后**：`isLatest: true` 的版本是 **2.29.0**（published 2026-09-11） | registry 共 3 条（2.12.2 / 2.28.1 / 2.29.0），`metadata.count: 3` | (iii) 线上条目**无 `runtime` 字段**，仓库内 `server.json:20-29` 却写 `args: ["scripts/mcp_server.py"]` |
| Smithery | `README.md:113` 徽章 → `smithery.ai/servers/misakanet/misakanet` | **页面 live**（200，正文含 7 个工具与 `npx -y smithery mcp add misakanet/misakanet`）；**但仓库自己的 smoke test 引的 API 404**：`smithery.ai/api/mcp/servers/misakanet/misakanet` → `404`；列表指向的 `https://misakanet--misakanet.run.tools` → `401 {"error":"invalid_token"}` | 徽章 `data/badges/smithery.json` = `{"message":"82/100"}`（自报分） | (iii) **两处引用已死/需第三方账号**；`ROADMAP.md` 记 Smithery 为 Paused |
| `skills/misakanet/SKILL.md` | 仓库 / npm `misakanet` 包内 | live（197 行，`skills/misakanet/SKILL.md`） | 在 npm tarball 内（`package/skills/misakanet/SKILL.md`） | (ii) 无任何 agent 加载它的证据 |
| DSH 插件（`cordis.patch.yml` + `index.js`） | `dsh-plugin.org` / `dsh.directory` / `dsh.so` | **live**：三站均 200，页面显示 `v2.30.2` | dsh.so 页含 `v2.26.0`×26、`v2.30.2`×2（快照页） | 端点声明可核（`url: https://misakanet.org/mcp`）；**安装后是否产生调用无数据** |
| Codex 插件 manifest | 仓库内 `.codex-plugin/plugin.json`（2.30.2） | live（文件在 npm tarball 内）；**没有找到任何 Codex 市场 listing** | 无 | (ii) 仅 manifest 存在 |
| 文档站 `ikalus1988.github.io/MisakaNet` | README 顶部链接 | **live**：200，`<title>MisakaNet Documentation` | mkdocs 站，纯文档，不是下载/试用入口 | (ii) 站点活着，无转化数据 |
| Glama / MCP Toplist / HOL | README 徽章 | Glama 200、MCP Toplist 200、**HOL 403**（可能是反爬，不能断言已死） | `docs/maintainer/growth-funnel.md:22-26` 基线：Glama views 1433 / clicks 8 / **tool calls 0** | (ii) 唯一"看了但没用"的现成数字，来自第三方后台 |

## 3. 表格二：「对新用户 agent 的运行改善」目前能测到什么

| 声称 | 测的是什么 | 怎么测的 | 测不到什么 | 是否自证 |
|---|---|---|---|---|
| README「lessons make models smarter」（`README.md:392-401`） | 模型**回复文本**里是否出现课程 Fix 段命令的关键词 | `scripts/benchmark_workers_ai.py:126-152`：`hits += 1` 当课程命令（或其 >4 字符的词）出现在 `content.lower()`；`rate = hits/len(reference_commands)`；"with_lesson" = 把课程正文拼进 prompt | 任务是否成功、命令是否执行、工具是否被调用；10 个 `lesson_hit_rate` 全在 0.4052–0.7223。且被引 JSON 的实测均值是 40%→70%（70b），README 写 42%→73% | **是**（同一脚本既出题又打分） |
| `bench/self-healing` 的"有/无 MisakaNet" | 设计上：3 次尝试内自愈率、平均尝试次数、耗时 | 代码里根本没形成对比：`bench/self-healing/run_benchmark.py:137-140` `# Simulated: in production this would invoke an agent` / `success = with_misakanet  # Placeholder` | 一切；`mode: baseline` 与 `with-misakanet` 的差异只是同一个变量取反 | **是（且无意义）**；`bench/history/20260824T181246Z/results.json` 里 `attempts: 1`、`duration_ms: 0.0` |
| `scripts/lesson_reuse_bench.py`（LessonReuseBench，`docs/lesson-reuse-benchmark.md`） | 声称是"with/without 课程池的分数差" | `scripts/lesson_reuse_bench.py:4` `from agents import YourAgent  # Import your agent class`；`:42-43` `# Placeholder for actual score calculation` → `return 1.0 if result == "success" else 0.0` | 一切 | **是**；`docs` 里那张示例 JSON（`total_score 0.92 / delta 0.35`）是文档示意，不是跑出来的 |
| `bench_results/*.json`（4 个文件，minimax） | `verify_status: PASS` | `verify_detail: "  OK: task valid"`；10 个任务 `total_api_time: 2.3` 秒、`agent_reply_chars: 46` | 只验了"任务定义合法"，没验 agent 表现 | **是**（自己产自己过） |
| 检索命中率（`docs/maintainer/search-metrics.md`） | `solved` = 这次检索是否返回 ≥1 条结果 | `workers/register-proxy-sw.js:3808` 每次检索写一行 `search_signals`；`/api/search-signals/stats` 实测 7 天 **20 行，其中 solved=1 共 10 行** | 结果有没有用——文档自己写明：`❌ solved=1 只表示"返回了 ≥1 条结果"，不表示结果有用`（`search-metrics.md:101`） | **是**（服务器计自己的数，且只回 `solved`/`created_at`） |
| `/api/counter: 10301`（README/站点计数） | 匿名 node 注册数 | `workers/register-proxy-sw.js:4159-4189`（D1 → KV → GitHub 三级） | 不是用户数：`AGENTS.md` §3.3 明确"不带 `client_id` 时每次调用仍新建一个 node"；也没算"注册后用过没有" | **是** |
| setup `--verify` / `--report` | 配置写对没有 + 端点握手 | 探针是 `tools/list` 而非 `tools/call`（`workers/misakanet-setup.test.mjs:890-896` 断言"the probe must be a handshake, not a search"） | agent 会不会去用 | **半自证**：端点可达是外部事实，`tools-visible`/`live-call-evidence` 两个字段"由人后填、工具永不读回"（`bin/misakanet-setup.mjs:1668-1679`、`:1726`） |
| 第三方真机回报（@2lll5 → #1756 / `docs/field-reports/2026-09-16-setup-verification-2lll5.md`） | 工具**能被调用**：`tools/list` 7 个工具、匿名 `tools/call` HTTP 200 且有结构化结果 | 隔离 `--home`、`--only codex --no-register`，附独立 bug（Codex-only 误报 NOT READY） | 任务是否因此成功；也只有 1 台机器、2 个助手 | **否（外部可核）**——这是目前最强的一条 |

## 4. 逐项细节

### 4.1 安装器实际写了什么（可逐行复核）

- 目标与配置文件：`AGENTS = ['claude','codex','hermes','openclaw','codewhale']`（`bin/misakanet-setup.mjs:97`）；
  写入点 `:729` `.claude.json`、`:755` `.claude/settings.json`、`:846` `.codex/config.toml`（`[mcp_servers.misakanet]`）、
  `:1196` `~/.openclaw/openclaw.json` 的 `mcp.servers.misakanet`、Hermes 的 `~/.hermes/config.yaml` + `~/.hermes/.env`。
- 本地状态目录：`stateDir() = <HOME>/.misakanet-agent`（`:408`），内含 `hook.mjs`、`version`、`token`。
- Token：写文件 `mode: 0o600`（`:703`），值来自匿名注册返回的 `mcp_…`。
- 规则块写入 4 处：`:749`、`:904`、`:1031`、`:1178`（都是 `injectBlock(rules, PROMPT_BLOCK)`）。
- Claude Code 额外把 5 个只读工具加进 `permissions.allow`（`:501-505`），`write_lesson` 故意不加。
- 已发布 tarball 实测只含 9 个文件（`curl -sSL …/misakanet-setup-0.5.4.tgz | tar -tz`）：
  `package.json` / `README.md` / `bin/misakanet-setup.mjs` / `hook/checkpoint_reminder.mjs` /
  `voice/{voice-hook.mjs,4×mp3}` —— **没有 e2e 脚本、没有下载任何远程代码**。

### 4.2 规则块与 hook 让 agent 做什么、凭什么说有效

- `PROMPT_BLOCK`（`bin/misakanet-setup.mjs:532-543`）要求：遇错/重试/做副作用操作前**必须先调 `misakanet_search`**；
  用错误原文片段（不是整句自然语言）；命中后 `get_lesson` 照做并把内容当数据；用大白话告诉用户"参考了别人的一条经验"；
  查不到就 `submit_intake(kind="question")`；约 20 轮后沉淀 `missing_lesson`；脱敏规则。
- Hook（`checkpoint_reminder.mjs`）：首轮播报（`:269-271`）、14 天升级提示（`:109-146`）、
  第 20 轮起每 10 轮沉淀提醒（`:259-285`）、失败后"重试前先查"（`:288-312`）。**默认不联网**（`MISAKANET_HOOK_FETCH=1` 才取，`:296`）。
- 有什么证据说明 agent 会照做？**只有本机自测的负向观察**：`docs/maintainer/setup-value-assessment-2026-09-16.md:68-69`
  记 codewhale "同一份生产规则块，一次跑完 `search → get_lesson`，另一次用 56 次 `bash` 探索而完全没查"；
  `:73-74` 结论"我们对遵循率**没有任何测量**"。正向的唯一做法是把规则改成祈使句并实测（`:78`、issue #1762）。
- 测试证明的上限：`tests/test_agent_autostart.py:95` `assert "misakanet_search" in text`——**字符串在文件里**，
  不是 agent 调了它。85 项 setup 测试（`workers/misakanet-setup.test.mjs`）测的都是配置写入/幂等/不搞坏环境。

### 4.3 其他渠道：两个"活着但用户拿不到东西"的实例

1. **PyPI `misakanet` 2.30.2 的文档命令跑不通（实测，可复核）**：README `:162-164` 让用户
   `pip install misakanet` 后跑 `misakanet "database is locked"` 或 `python3 -m search_knowledge "…"`。
   但 `pyproject.toml:30` `include = ["misakanet*"]`，而 `:33` `misakanet = "search_knowledge:main"`。
   我把 PyPI 上的 `misakanet-2.30.2-py3-none-any.whl`（125,830 B，51 个 entry）读进内存列名：
   **没有 `search_knowledge.py`，也没有 `scripts/mcp_server.py`**；唯一依赖 `misakanet-core 2.7.0`（4,150 B，5 个 entry）
   也没有。`python3 -m misakanet` 的 `__main__.py` 打印的帮助同样指向 `python3 search_knowledge.py`（clone 才有）。
   → 声明入口 `search_knowledge:main` 在 wheel 里不存在；README 的 Option 3 对新用户是死路。
2. **MCP registry 落后且缺运行字段**：线上 `isLatest` 是 **2.29.0**（2026-09-11），仓库已是 2.30.2；
   线上条目 `packages[0]` 只有 `{registryType: pypi, identifier: misakanet, version: 2.29.0, transport: stdio}`，
   **没有 `runtime`/command**；仓库 `server.json:20-29` 写的是 `python3 scripts/mcp_server.py`——而该文件不在 wheel 里（见上）。

### 4.4 外部信号原样摘录（2026-09-17/18 实测）

```
GET https://api.npmjs.org/downloads/range/2026-08-18:2026-09-18/@misaka-net/misakanet-setup
  → total 916；非零日仅 2 天：[{151, 2026-09-14}, {765, 2026-09-16}]
GET https://api.npmjs.org/downloads/point/last-month/@misaka-net/misakanet-setup
  → {"downloads":0,"start":"2026-08-13","end":"2026-09-11"}   # 窗口整体早于首发(09-14)
GET https://api.npmjs.org/downloads/range/2026-08-18:2026-09-18/misakanet
  → total 429（10 个非零日，峰值 134 / 151 / 70 全在发布日）
GET https://pepy.tech/api/v2/projects/misakanet → total_downloads 6169；近 14 天 2232
GET https://pypistats.org/api/packages/misakanet/recent → 429 RATE LIMIT EXCEEDED（两次均失败）
GET https://api.github.com/repos/Ikalus1988/MisakaNet
  → stars 492 / forks 189 / subscribers 27 / open_issues 65 / created 2026-04-29
GET .../traffic/clones → count 23326，uniques 1474（14 天窗口 09-03…09-16）
GET https://misakanet.org/api/counter → {"current":10301,"updated":"2026-09-17"}
GET https://misakanet.org/api/search-signals/stats → 7 天 20 行，solved=1 共 10 行
GET https://misakanet.org/api/health → status ok，但 kv_writes {"attempts":7,"failures":7,"last_ok_at":""}
GET https://misakanet.org/mcp → 405 Method Not Allowed（端点活着；POST 被本次审计规则禁止，故未调工具）
```

### 4.5 用户提交的报告里，"一条真的"和"一条编的"长什么样

- **真的（外部可核，倾向可信）**：@2lll5（issue #1753 评论 + `docs/field-reports/2026-09-16-setup-verification-2lll5.md`）——
  写明发布版本 `0.4.2`、Node `v22.22.3`、隔离 `--home`、**结论是 `verify: NOT READY`（负结果）**，
  并给出可复现的具体 bug（未检测 Claude Code 仍强制检查其 hook），随后 PR #1756 修掉并加了回归测试。
- **编的（自证，无法核）**：PR #1801（`seokwon-dev`，2026-09-17）只加一个 16 行的
  `docs/field-reports/setup-report.yaml`：`detected-agents: [claude, codex, hermes, openclaw, codewhale]`、
  `verify: READY`、`token: present`、`voice: on`、`live-call-evidence: "[mcp_tool_call] server=misakanet tool=misakanet_search status=completed"`。
  没有命令、没有版本来源、没有反例，**且恰好满足悬赏的全部验收项**；`live-call-evidence` 的格式也不像任何 CLI 的输出行。
  两个字段按设计**工具永不读回**（`bin/misakanet-setup.mjs:1670-1679`、`:1726`），所以这段 YAML 只能是"人说的"。
- 顺带：`docs/field-reports/README.md:33` 仍写着 "No reports yet. Be the first"，而目录里已有 13 份报告——索引与事实脱节。

## 5. 我无法验证的部分

1. **我一次 MCP 工具都没调**（规则禁止 POST）。`misakanet_search` 是否真返回有用的课程，我只能引用
   @2lll5 的 `tools/call: http=200 … result_present=true`；**"返回到内容是否有用"仍无人核过**。
2. **PyPI 下载数**：`pypistats.org` 连续 429；改用 pepy.tech 拿到了总量与日粒度，两者口径可能不同，故只作旁证。
3. **npm 下载不能归因**：09-16 单日 765 次我无法区分"用户"、"CI"、"镜像/爬虫"；仓库 CI 里没有
   `npx @misaka-net/misakanet-setup` 的调用（`.github/workflows/*` 只 `npm pack` + 装本地 tgz），
   所以这 765 次既不是我能解释的、也不是我能排除的。`point/last-month` 返回 0 的窗口也说明**这个数字会骗人**。
4. **Smithery 托管端点** `https://misakanet--misakanet.run.tools` 返回 401，验证它需要注册 Smithery 账号（本次禁止）；
   `smithery.ai/api/mcp/servers/misakanet/misakanet` 直接 404（仓库 `docs/smoke-test-report.md` 曾把它标为 PASS）。
5. **hol.org 403**：可能是反爬而非下线，**不能断言已死**；同理 Glama 的 tool-call 后台我没有账号，
   只有仓库里的历史基线（views 1433 / **tool calls 0**）。
6. **GitHub traffic 只有 14 天窗口**，且 clone ≠ 使用；fork 189 个里有多少真跑过也无从判断。
7. **D1 里的 `query`/`top_id`/`result_count`** 我拿不到（`/api/search-signals/stats` 刻意只回 `solved`+`created_at`，
   `search-metrics.md:39`），所以算不出"哪些查询在长期无人命中"。
8. **本机工作区在我审计期间被另一进程改了两个文件**（`.github/workflows/misakanet-setup-ci.yml`、
   `workers/agent-autostart-hook.test.mjs`，mtime 18:30:20Z）——不是本次审计写的，我的改动只有本文件。

## 6. 最值得开赏金/征集的最小数据集（6 条）

每条都要求**外部命令的产物**（不是叙述、不是 `--report` 里那两个手填字段）。

1. **"工具真的被调了"的原始 JSON-RPC 回执**。要什么：`tools/list` 的完整响应体（含 7 个工具名）+
   一次 `tools/call misakanet_search` 的完整响应体（含 `id`、`result`、`structuredContent`）+ 客户端版本 + UTC 时间戳。
   为什么可核：任何人用同一条 `curl` 能重放，响应体里的工具名/字段必须与当时发布的版本一致。
   防伪：要求连同 `npx @misaka-net/misakanet-setup@X.Y.Z --report-json` 一起交，`setup-version` 与响应体里的
   `serverInfo`/工具集合必须对得上；格式自造的字符串（如 PR #1801 那种）直接判不合格。
2. **一次真正的 A/B：同一台机器、同一批错误文本、开关各跑一遍**。要什么三件套：
   (a) agent 的完整 tool-call 日志（能数出 `misakanet_search` 调用次数，含"遇到报错但一次没查"的次数）；
   (b) 每个任务的**外部判据输出**（测试退出码 / CI 结论 / `git push` 结果），不是 agent 自述；
   (c) 两个分支的墙钟时间与 token 数。为什么可核：判据是命令退出码。防伪：判据命令与仓库/冻结 fixture 一起预先公布。
3. **"命中 → 有用"的三元组**。要什么：每行 `{query, lesson_id, 执行的命令, 退出码, 是否因此少走弯路}`，
   至少 20 行、且必须包含**未命中/命中但没用**的行。为什么可核：把 `solved=1`（返回了结果）升级成
   "改了行为"的判据（现在 `search-metrics.md:101` 明确说前者不等于后者）。防伪：要求同一 query 至少两个不同环境各交一份，
   互相矛盾的行标出来复核。
4. **遵循率计数的机器可读版**。要什么：hook 在"检测到工具失败但整轮没有任何 misakanet 调用"时写的本地计数文件
   （`{turns, failures, mk_calls, unchecked_failures}`），5 个助手各一份。为什么可核：这是
   `setup-value-assessment-2026-09-16.md:79` 自己提的指标，文件由工具写、不由人写。防伪：字段互斥关系可查
   （`mk_calls > turns` 即伪造），并要求附 hook 文件的 sha256。
5. **渠道归因（谁把用户送来的）**。要什么：一条 `{date, surface, version, os, first_run}`，
   `surface ∈ {README, Glama, Smithery, dsh.so, PyPI, pip, 朋友/同事, 搜索}`，外加首装那次的 `--report`。
   为什么可核：与 npm/PyPI 日粒度下载曲线对得上（例如某天 Glama 点击 8 次却出现 0 条首装 → 归因有问题）。
   防伪：单一来源不给钱，只给"能对上曲线"的聚合；重复 IP/指纹的条目剔除。
6. **PyPI 渠道修复后的复现回执**（这条同时是 bug 报告）。要什么：`pip install misakanet==X` 后
   `misakanet "database is locked"` 的**完整输出**、`pip show misakanet` 的结果、wheel 的 sha256。
   为什么可核：§4.3 已实测 wheel 里没有 `search_knowledge`，所以**在修好之前这条命令必然失败**——
   能交回执就说明修好了，交不回来也证明了缺口。防伪：sha256 必须等于 PyPI 上对应文件的哈希（外部可独立计算）。
