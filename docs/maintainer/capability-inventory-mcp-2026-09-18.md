# MCP 能力面清单（证据版，2026-09-18）

> 审计对象：本仓所有 MCP 相关能力面。规则：每条事实必须挂 `文件:行` 或**实际跑过的命令输出**；
> 推测一律标注。审计只读（**未改动仓库里的任何既有文件**），未调用任何写入型端点
> （`misakanet_register` / `misakanet_submit_intake` / `misakanet_write_lesson` 全部**未调用**）。
>
> **审计基线**：审计时的 checkout 在分支 `fix/setup-packaged-e2e`（比当时的 `origin/main` 多 3 个 commit）；
> 该分支已作为 PR #1818 合入 main（`b182013c6`），因此文中对 `packages/misakanet-setup/**` 与
> `.github/workflows/` 的引用与 main 一致。时间：2026-09-18。

---

## 1. 一句话结论

**真在跑且有外部证据的只有 3 个面**（远端读路径、远端 intake 写入、npm 安装器）；
**6 个面存在但没有任何"有人用过"的证据**（远端 `me_events`、本地 stdio、Codex 插件清单、
Glama/well-known 卡片、Smithery 条目、遥测/计数面）；
**4 个面是文档/清单声称、实际没接上**（DSH bundle 通道、官方 MCP registry 条目、PyPI 的 stdio
分发面、worker 自报版本号）。最能说明问题的是三组数字：

1. 线上 `initialize` 自报版本 **2.27.1**，而仓库/清单/PyPI/npm 全是 **2.30.2**
   （PyPI release 列表显示 2.27.1 之后还有 2.28.0/2.28.1/2.29.0/2.30.0/2.30.1/2.30.2 共 6 个 release）；
2. 官方 MCP registry 的 `isLatest` 停在 **2.29.0**，而 `server.json` 已写 **2.30.2**——没人在发；
3. 全库搜索遥测 `/api/search-signals/stats?days=365` 只有 **20 行**（09-16 一行、09-17 十九行）。

---

## 2. 总表

| 面 | 是什么 | 谁会用到 | 真实使用证据（带数字/命令） | 已知缺陷 | 证据强度 |
|---|---|---|---|---|---|
| ① 远端读路径 `misakanet_search` / `misakanet_get_lesson` | `https://misakanet.org/mcp` 的检索面 | 任意 MCP 客户端 | `/api/search-signals/stats?days=365` → `rows 20`（solved 11 / 未解 9）；本次审计中本机 IP 的 **5 次/天** 配额**在首次调用前就已用尽**（见 §3.2） | 样本量 20；配额耗尽的返回体没有 `trust_notice`；search 与 get_lesson 的限流文案不一致 | 中 |
| ② 远端写/鉴权面 `register` / `submit_intake` / `write_lesson` / `preflight` | 注册、报料、写 lesson、风险预检 | agent（无需账号） | `label:mcp-intake` = **105** 个 issue（closed 83 / open 22）；作者分布 **Ikalus1988×97、zsxh1990×2、github-actions[bot]×1**；抽 100 条标题命中 test/smoke/verify/demo **19** 条 | 105 条里 97 条是维护者自己开的（含 "[Intake] deploy verification test" 类）；外部第三方只有 2 条 | 中 |
| ③ 远端证据面 `misakanet_me_events` | 取 lesson 复用证据（E4） | 想核验信任证据的 agent | 只有"配额耗尽"这一条实测输出；**没有任何调用它并拿到 events 的记录** | 三个信号源里"跨节点确认"是正则扫正文（`workers/register-proxy-sw.js:2305-2314`），只要有 "contributors:" 一行就判 E4 | 无 |
| ④ 本地 stdio server（9 工具） | `misakanet/server/*.py`，`scripts/mcp_server.py` 启动 | clone 了仓库、自己配 stdio 的用户 | **找不到任何"有人这么装/这么用"的证据**；主安装通道已改指远端（`docs/maintenance.md:117-124`） | 9 个工具里有 3 个只在本地存在（见 §3.3），远端 `tools/list` 没有它们；README 仍在教 stdio 装法 | 无 |
| ⑤ DSH bundle 插件通道 | 根 `package.json` 的 `dsh.bundle` + `cordis.patch.yml` + `index.js` | DSH profile | 外部仓库 AI-Scarlett/DSH-Store 的 `registry/candidates.json`：`id: ikalus1988-misakanet`，`status: "rejected"`，`route: "blocked"`，`statusReason: "SUBMISSION_PATCH_PROTECTED: Bundle Patch impersonates the protected @deepseek-ai namespace"` | 外部注册表记录的就是"被拦"，且该条目 `sourceUpdatedAt: 2026-09-11`，早于本仓的修复 commit（注释见 `cordis.patch.yml:9-23`） | 中（证明被拒） |
| ⑥ Codex 插件清单 | `.codex-plugin/plugin.json` | Codex 插件市场 | 无 | 版本由 `scripts/align_versions.py:133` 维护（=2.30.2），但没有任何"装上了/被扫过"的证据 | 无 |
| ⑦ npm 安装器 `@misaka-net/misakanet-setup` | 一键把远端 MCP 端点写进各 agent 配置 | Claude Code / Codex / Hermes / OpenClaw / codewhale 用户 | npm point API `2026-09-01:2026-09-17` → **916**；逐日：`09-14=151, 09-16=765`，其余 6 天 **0** | 下载曲线是尖峰（0/151/0/765/0），不是持续使用；包 `created 2026-09-14`，所以 `last-month`/`last-week` 的 0 是**窗口早于建包**，不能当"没人用"的证据 | 中 |
| ⑧ 官方 MCP registry 条目 `server.json` | registry.modelcontextprotocol.io | 任何按 registry 装 MCP 的人 | registry API 查到该名字共 3 个版本：`2.12.2`（07-22）、`2.28.1`（09-06）、`2.29.0`（09-11，`isLatest=true`） | 仓内 `server.json:9` 写 **2.30.2**，比 registry 最新条目高一个版本：**没有任何东西把仓内的 bump 推到 registry**；`align_versions.py` 只校验文件之间一致 | 强（矛盾已实测） |
| ⑨ Glama / well-known 卡片 | `glama.json`、`docs/.well-known/mcp.json`、`docs/.well-known/glama.json` | 爬虫 / MCP 客户端发现 | 线上 `https://misakanet.org/.well-known/mcp.json` → HTTP 200，内容与仓内一致（393 lessons / 2.30.2） | `glama.json:14` 与 `docs/.well-known/glama.json:13` 都写 `"license": "MIT"`，而仓库、`server.json`、`plugin.json` 都是 Apache-2.0 | 中 |
| ⑩ Smithery 条目 + 徽章 | `smithery.ai/servers/misakanet/misakanet` | Smithery 用户 | 线上页面（同 UA 复现脚本抓取）正则 `<span>(\d+)<!-- -->/100</span>` → **`82/100`**，与 `data` 分支 `badges/smithery.json` 一致；`update-smithery-badge.yml` 8 次运行全 success | `82/100` 是 Smithery 自己的评分，**不是使用量**；没有任何"通过 Smithery 调用过"的证据 | 中（证明条目存在） |
| ⑪ PyPI `misakanet` 的 stdio 分发面 | `pip install misakanet` → 本地 MCP server | registry/runtime 指向的人群 | PyPI 存在，15 个 release，最新 2.30.2（2026-09-15）；pypistats `last_month=1019, last_week=457, last_day=20` | **下载量是真的，但 stdio 面是断的**：见 §3.4——`scripts/mcp_server.py` 不在 wheel/sdist 里，两个 console_scripts 指向的模块也不在 | 强 |
| ⑫ worker 自报版本 | `initialize` 的 `serverInfo.version` | 所有 MCP 客户端 | 线上 `initialize` → `{"serverInfo":{"name":"misakanet","version":"2.27.1"}}`；而 `pyproject.toml:7` / `package.json:3` / `server.json:9` / `.well-known/mcp.json:4` 全是 `2.30.2` | `workers/register-proxy-sw.js:447` 是硬编码兜底串；`:193` 的注释声称 "falls back to package.json"，**代码里没有这回事** | 强 |
| ⑬ 遥测/计数面 | `/api/counter`、`/api/search-signals/stats`、`data/badges/tools.json` | 维护者、README 徽章 | `/api/counter` → `{"current":10301,"updated":"2026-09-17"}`（按 `scripts/sync_lesson_count.py:345` 的 −10000 偏移 = 301 节点）；SSOT 门禁实测 `✅ every managed node count == 262` | 计数器是**自证**（唯一外部对照是它自己）；`tools.json` 由 `update-badges.yml:54` 用 `grep -cE 'name: "misakanet_' workers/register-proxy-sw.js` 生成，**不可能与代码不一致** | 无（自证） |

---

## 3. 逐项细节

### 3.1 远端面：`tools/list` = 7，与文档一致

```bash
$ curl -sS https://misakanet.org/mcp -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -H 'MCP-Protocol-Version: 2025-06-18' -H 'Origin: https://misakanet.org' \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
TOOL COUNT 7
 - misakanet_register / misakanet_search / misakanet_get_lesson / misakanet_submit_intake
 - misakanet_write_lesson / misakanet_preflight / misakanet_me_events
```

与 `AGENTS.md:57-67`（7 个）、`README.md:16` 一致；定义在 `workers/register-proxy-sw.js:195-437`。
鉴权分界在 `:2765-2767` 的 `openTools`（`submit_intake`/`register`/`search`/`get_lesson`/`me_events`），
`:2774-2775` 再把 `initialize` / `tools/list` / `notifications/*` 列为免鉴权。

实测鉴权边界：

```bash
$ curl ... -d '{... "name":"misakanet_preflight","arguments":{"intent":"rm -rf build/"}}'
{"jsonrpc":"2.0","error":{"code":-32000,"message":"Unauthorized"}}   [http 401]
$ curl ... -d '{... "name":"misakanet_write_lesson", ...}'
{"jsonrpc":"2.0","error":{"code":-32000,"message":"Unauthorized"}}   [http 401]
```

### 3.2 配额：三个读工具共用一个 5/天/IP 计数器（与文档口径不一致）

`AGENTS.md:103` 写"**匿名**：`misakanet_search` + `misakanet_get_lesson` 合计 **5 次/天/IP**"。
代码是三个工具共用一个 `rate_read` 计数器：`workers/register-proxy-sw.js:2017-2021`（search）、
`:2211-2215`（get_lesson，注释 `:2207` "Same anonymous read quota as search"）、
`:2258-2262`（me_events，注释 `:2255` "Same anonymous read quota as search/get_lesson"）。

实测（本机 IP，本轮审计**没有一次成功读取**，首次 search 就被拒）：

```bash
$ curl -sS https://misakanet.org/mcp ... -d '{"...":"misakanet_search","arguments":{"query":"zzzqqq nonexistent xyzzy audit probe 2026"}}'
{"error":"Rate limit: 5 free searches per day exceeded","hint":"Register to get unlimited access: misakanet_register","voice":"failure-warning"}

$ curl -sS https://misakanet.org/mcp ... -d '{"...":"misakanet_get_lesson","arguments":{"id":"dco-auto-fix-workflow"}}'
{"error":"Rate limit: 5 free reads per day exceeded","hint":"Register to get unlimited access: misakanet_register"}

$ curl -sS https://misakanet.org/mcp ... -d '{"...":"misakanet_me_events","arguments":{"lesson_id":"dco-auto-fix-workflow"}}'
{"error":"Rate limit: 5 free reads per day exceeded","hint":"Register to get unlimited access: misakanet_register"}
```

两点缺陷：(a) 文档漏了 `me_events` 也吃这个配额；(b) 同一个计数器对 search 报 "5 free **searches**"、
对另外两个报 "5 free **reads**"，同一状态两种文案（`register-proxy-sw.js:2019` vs `:2213`、`:2260`）。
另外三条限流返回体**都没有** `trust_notice`，而 `AGENTS.md:140` 说"`trust_notice`：每次读取都有"。

`consumeQuota` 的设计是**fail open**（`:1658` `if (count !== null && count > limit)`；存储失败返回 null 放行），
注释 `:1654` 明确写了这一点。

### 3.3 本地 stdio server：9 个工具，3 个只在本地

`misakanet/server/tools.py` 的 `TOOLS`（`:7` 起）与 `misakanet/server/protocol.py:24-33` 的 `_HANDLERS` 都是
9 个：`search`、`get_lesson`、`submit_usage`、`submit_intake`、`write_lesson`、`preflight`、
`usage_status`、`register`、`memory_context`。

| 只在本地 | 只在远端 |
|---|---|
| `misakanet_submit_usage`、`misakanet_usage_status`、`misakanet_memory_context` | `misakanet_me_events` |

**没有任何东西自动拉起它。** `scripts/mcp_server.py:8-20` 只在 docstring 里教用户手写
`{"command":"python3","args":["scripts/mcp_server.py"]}`；`integrations/` 下的
`docs/integrations/{cursor,continue,claude-code}.md` 也是手配。反过来，`docs/maintenance.md:117-124`
已把 npm 通道改成直连远端并写明"**不再需要本地 python**"，`index.js:47-58`
的 `DEFAULT_MCP_CONFIG` 也只声明远端 URL。→ 本地 3 个工具（含 `memory_context`）
**没有任何分发通道能把它们送到用户手里**。

### 3.4 PyPI 的 stdio 面是断的（三处都断）

`server.json:10-24` 声明 `registryType: pypi, identifier: misakanet` + `runtime.args: ["python3","scripts/mcp_server.py"]`。

实测（不落盘，用管道列包内容）：

```bash
$ curl -sS <sdist-url> | tar -tzf - | awk -F/ 'NF<=2' | sort -u
misakanet-2.30.2/  LICENSE  PKG-INFO  README.md  pyproject.toml  setup.cfg
$ curl -sS <sdist-url> | tar -tzf - | grep -E '^misakanet-2\.30\.2/scripts/'
(无输出)
```

- 顶层 `scripts/mcp_server.py` 在 sdist 与 wheel 里都**不存在**（wheel 里只有 `misakanet/**`，
  最多到 `misakanet/server/handlers/*.py`）→ `server.json` 的 runtime 命令跑不起来；
- wheel 的 `entry_points.txt`：`misakanet = search_knowledge:main`、`misaka-harvest = scripts.misaka_harvest:main`；
  而 `misakanet` wheel 与依赖 `misakanet-core` 2.7.0 的 wheel（共 5 个条目，只有 `misakanet_core/`）
  **都不含** `search_knowledge.py` 或顶层 `scripts/`→ 两个 console script 装上即 `ModuleNotFoundError`。

也就是说：`pip install misakanet` 装得到的只有库，**装不出一个可启动的 MCP server**。
（`pyproject.toml:29-30` 的 `packages.find include = ["misakanet*"]` 是原因链的一环，
但只按配置文件推断，我没跑构建去复现。）

### 3.5 Origin / 协议版本：规则已实测，其中一条不会失败

```bash
$ ... -d '{"method":"initialize",...}'                       # 不带 Origin
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18",...,"version":"2.27.1"}}   [http 200]

$ ... -H 'Origin: https://evil.example.com' -d '{...initialize...}'
{"jsonrpc":"2.0","error":{"code":-32000,"message":"Forbidden: invalid Origin"}}             [http 403]

$ ... -H 'MCP-Protocol-Version: notadate' -d '{...initialize...}'
{"jsonrpc":"2.0","error":{"code":-32600,"message":"Unsupported protocol version: notadate"}} [http 400]

$ ... -H 'MCP-Protocol-Version: 2025-11-25' -d '{...initialize, protocolVersion 2025-11-25...}'
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18",...}}                        [http 200]
```

- `Origin` 缺席放行：`workers/register-proxy-sw.js:465`（`if (!origin) return true;`）；白名单 `:452-459`。
- `SUPPORTED_PROTOCOL_VERSIONS`（`:440`）那条检查**不可能失败**：`:2838-2843` 只调 `debugLog` 然后继续，
  真正的 400 只由 `:2823` 的日期形状正则产生。所以"支持 2025-06-18 / 2026-07-28"这个门禁**空转**——
  任何 `YYYY-MM-DD` 都能过，`negotiatedVersion`（`:2914-2916`）会把不认识的版本一律降级成 `2025-06-18`。

SSE / 方法误用：

```bash
$ POST ... -H 'Accept: application/json, text/event-stream' -d '{...,"method":"tools/list"}'
event: message
data: {"jsonrpc":"2.0","id":9,"result":{"tools":[…]}}          # 单次 SSE，不是分块流

$ GET https://misakanet.org/mcp -H 'Accept: application/json'
{"error":"Method Not Allowed. Use POST for MCP Streamable HTTP transport, or GET with Accept: text/event-stream for SSE."}  [405]

$ GET https://misakanet.org/mcp -H 'Accept: text/event-stream'
event: connected
data: {}                                                        # 之后保持打开（15s 超时）
```

与 `AGENTS.md:50-55` 描述一致。注意 SSE POST 是"一次响应包成 `event: message`"，
**没有真正的分块推送**（`mcpSseResponse`，`register-proxy-sw.js:2727-2738`）。

### 3.6 `no_match` → intake 闭环：代码在，但我这次**没能实测到**

`register-proxy-sw.js:2142-2185`：无结果时返回 `{results:[], no_match:true, suggestion, intake:{tool:"misakanet_submit_intake", args:{...}}}`，
并按 `inferIntakeKind` 把 how-to 问题路由到 `kind:"question"`（`:2143-2145`）。
**我无法实测**：本机 IP 配额在第一次 search 前就用尽（§3.2），拿不到 `no_match` 返回体。
覆盖它的是单测 `workers/mcp-no-match.test.mjs`。

闭环的另一半（issue 是否真的被处置）：`label:mcp-intake` 105 条中 closed **83** / open **22**，
`label:question` closed 8——**从数字看闭环是通的**，但主体是维护者自己开的（97/105）。

### 3.7 worker 自报版本：硬编码兜底 + 注释与代码不符

```bash
$ curl ... -d '{"method":"initialize",...}'
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}},
 "serverInfo":{"name":"misakanet","version":"2.27.1"}}}
```

- 代码：`workers/register-proxy-sw.js:447` `version: env.MCP_VERSION || "2.27.1"`；
- 注释（`:193`）："Version injected at build time from env.MCP_VERSION or falls back to **package.json**"
  ——兜底不是 package.json，是硬编码串；
- 部署侧没有任何地方注入它：`workers/wrangler.toml` 全文无 `[vars]`（只有 triggers/kv/d1 三段），
  `.github/workflows/deploy-worker.yml:33` 是 `npx wrangler deploy --config wrangler.toml`（无 `--var`）。
  `grep -rn MCP_VERSION` 全仓只命中 `workers/*.test.mjs` 里的测试假值。
- `scripts/align_versions.py` 管 `server.json` / `glama.json` / 两张 well-known 卡片 / `.codex-plugin/plugin.json`
  （`:133`），**不管这个 worker 里的字符串**。

### 3.8 自证与"不会失败的门禁"

| 项 | 位置 | 为什么是自证/空转 |
|---|---|---|
| MCP 工具数徽章 | `.github/workflows/update-badges.yml:54` | `grep -cE 'name: "misakanet_' workers/register-proxy-sw.js` —— 数与源同一个文件，永远一致；只数远端 7 个，看不见本地 9 个 |
| 远端可达性检查 | `scripts/doctor.py:77-92` | 只要 HTTP code 非 `000` 就算 reachable（`:89`），401/403/405/500 全过；而且 CI 里**从不调用它**：唯一的调用点是 `deploy-worker.yml:24` 的 `--kv-only`，而 `doctor.py:102-107` 在 `--kv-only` 分支直接 return，走不到 `:110` 的 `CHECKS` |
| 节点计数 | `workers/register-proxy-sw.js:4159-4190` | 优先 D1 `counters`，KV 次之，最后回落 `fetchFromGitHub(token,"data/counter.json")`（`:4187`），而该函数默认 `ref="data"`（`:3002`）——`data` 分支那份实测是 `{"current": 10047, "updated": "2026-06-01T02:25:00Z"}`，**比真值低 250+ 且停在 3.5 个月前**，没有告警 |
| 采用率报告 | `scripts/track_adoption.py` | 采集 npm/PyPI/GitHub 指标并输出周报，但 `grep -rn track_adoption` 在全仓（除自身）**零命中**：没有任何 workflow 跑它 |
| 协议版本门禁 | `register-proxy-sw.js:2838-2843` | 只 `debugLog`，不会失败（见 §3.5） |

### 3.9 DSH / Codex 插件通道

- 声明：`package.json:14-18` `dsh.bundle.patch = ./cordis.patch.yml`；`cordis.patch.yml:52-62` 插入
  `id: misakanet-mcp`、`transport: streamable-http`、`url: https://misakanet.org/mcp`；
  `index.js:47-58` 的 `DEFAULT_MCP_CONFIG` 同值（含 `headers: {Origin: ...}`）。
- 外部裁决（**这是本仓之外的真实证据**）：AI-Scarlett/DSH-Store `registry/candidates.json` 的
  `ikalus1988-misakanet` 条目 → `"status": "rejected"`、`"route": "blocked"`、
  `"statusReason": "SUBMISSION_PATCH_PROTECTED: Bundle Patch impersonates the protected @deepseek-ai namespace"`。
  该文件 `registry.updatedAt = 2026-09-15T04:39:01Z`，条目 `sourceUpdatedAt = 2026-09-11`。
- `cordis.patch.yml:9-23` 的注释正是解释这次拦截与改法（改成只 insert 自己的包名）。
  但**外部注册表里没有任何"重新通过"的记录**——我不能确认修复后是否被重新评估。
- `dsh-integration.yml`（9 次运行）/ `dsh-tests.yml`（3 次）都在 origin/main 上、本地分支没有，
  是自测，不是外部安装证据。npm 侧真正的外部信号只有根包 `misakanet` 的下载量：`2026-09-01:2026-09-17` = **429**。

### 3.10 registry / 卡片 / Smithery 的一致性

| 面 | 版本 | 备注 |
|---|---|---|
| `pyproject.toml:7` / `package.json:3` | 2.30.2 | 仓库真相源 |
| `server.json:9` / `glama.json:5` / `docs/.well-known/mcp.json:4` | 2.30.2 | 由 `align_versions.py` 维护 |
| `.codex-plugin/plugin.json:3` | 2.30.2 | `align_versions.py:133` |
| **官方 registry `isLatest`** | **2.29.0**（2026-09-11 发布） | 差一个版本，无自动发布者 |
| **线上 `initialize` serverInfo** | **2.27.1** | §3.7 |
| `docs/.well-known/glama.json:13` / `glama.json:14` | license **MIT** | 仓库是 Apache-2.0（GitHub API `license.spdx_id = "apache-2.0"`；`.codex-plugin/plugin.json:11` 也是 Apache-2.0） |

课程数 SSOT 实测是一致的（`python3 scripts/sync_lesson_count.py --check` →
`✅ every managed lesson count == 393 / nodes == 262 / domains == 43`），
所以 `docs/.well-known/mcp.json:3` 的 "393 indexed failure lessons" 有维护者，不算漂移。

---

## 4. 我无法验证的部分

1. **`no_match` 的线上返回体**：本机 IP 匿名配额在首次调用前已耗尽（§3.2），只能读代码 `:2142-2185` 与单测。
2. **`trust_notice` / `suspicious` / `structuredContent` 的线上形状**：同样被配额挡住；
   限流返回体里确实没有 `trust_notice`，但正常返回体我没能抓到。
3. **`misakanet_me_events` 有任何真实事件**：没能拿到一次成功响应；KV `helpful:*` 的实际写入者
   `POST /api/helpful`（`:4355-4369`）我没敢调用（写入型）。全仓搜索没有任何代码调用 `/api/helpful` 写入路径
   （只有 `misakanet/server/handlers/submit.py:74` 会 POST 它，且那是本地 stdio 通道）→
   "helpful 票"这条 E4 信号**很可能永远是空的**，但我不能断定线上 KV 里没有值。
4. **基线差异（已消解）**：审计时 HEAD 在 `fix/setup-packaged-e2e`，比当时的 origin/main 多 3 个 commit，
   改动集中在 `packages/misakanet-setup/bin/misakanet-setup.mjs`（+273 行）、
   `.github/workflows/misakanet-setup-ci.yml`（新增 198 行）、`workers/misakanet-setup.test.mjs`。
   涉及这些文件的判断（⑦）在 origin/main 上可能不成立。
5. **PyPI 包能否真的装上跑起来**：我按"不安装"的约束只做了包内容比对（§3.4），没跑 `pip install` 验证 `ModuleNotFoundError`。
6. **DSH 通道修复后是否被重新评估**：DSH-Store 条目停在 `sourceUpdatedAt 2026-09-11`，早于修复；
   我没有找到重新提交/复审的记录，也没有据此推断"已通过"或"仍被拒"。
7. **`misakanet.org` 的实际流量**：Cloudflare Analytics 我没有权限，
   本报告里所有"使用量"数字都来自公开 API（npm/PyPI/GitHub/search-signals），口径各不相同。
8. **`data/badges/*` 之外的徽章消费方**：`README.md:88` 的 tools 徽章、`README.md:113` 的 Smithery 徽章
   我只验证了 JSON 可访问与内容，没验证渲染。

---

## 5. 建议的下一步（按证据缺口排序，不提新功能）

1. **先修"自报版本"这条链**（缺口最大、成本最低）：把 `register-proxy-sw.js:447` 的硬编码兜底
   改成从单一真相源注入（或在 `wrangler.toml` 加 `[vars] MCP_VERSION`），
   并把 `align_versions.py` 的受管文件清单扩到该文件——否则线上 `serverInfo.version` 会永远说谎，
   而 `cordis.patch.yml`/registry/卡片全对齐在 2.30.2 只会放大这个谎。
2. **给 registry / PyPI 发布补一个"发了吗"的检查**：现在 `align_versions.py` 只保证"仓内文件彼此一致"，
   没有任何东西比对**外部**（registry `isLatest=2.29.0` vs 仓内 2.30.2；PyPI stdio 面断）。
   把 registry 查询与 PyPI 包内容比对接进现有 workflow 的判定即可，不需要新功能。
3. **决定 PyPI 上 MCP 面的去留**：`server.json` 的 runtime 在当前发布形态下必然失败，
   要么把 `scripts/mcp_server.py` 收进包（改打包配置），要么把 runtime 改成装得到的入口
   （例如 `python -m misakanet.server`），并在 CI 里断言"从 sdist/wheel 里能列出该文件"。
4. **补一条匿名读配额的回归**：三个工具共用一个计数器，但文案有两种、文档只写两个工具。
   把 `AGENTS.md:103` 的口径改成三个工具，并让三处 `message` 共用同一常量。
5. **清掉两个"不会失败"的门禁**，或明确降级为日志：`doctor.py:77-92` 的 reachable 判定
   （非 `000` 即通过，且 CI 走 `--kv-only` 根本不执行）与 `update-badges.yml:54` 的
   `grep -c` 计数（与源同文件，永远一致）；以及给 `/api/counter` 的
   `data` 分支兜底（`:4187`，实测停在 2026-06-01）加一个"太旧就告警"的判断。
