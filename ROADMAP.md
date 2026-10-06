# MisakaNet 4-Month Roadmap

Last updated: 2026-10-02（上一版：2026-09-16，原文保留在下方，未改写）

> **要看当前计划，直接看 [`2026-10-02 更新 — 交付、在飞与 KV 迁移到 D1`](#2026-10-02-更新--交付在飞与-kv-迁移到-d1)。**
> 它只补 2026-09-16 之后的增量，并回答"现在在哪、下一步做什么"；`2026-09-16 更新 — 五层拼图与优先事项`
> 是上一轮的记录，其文字、数字、裁定一律未改写（本仓惯例：旧条目只加状态裁定，不改写历史）。
> 下面 2026-08-22 的原文全部保留，只作历史记录：其中的版本号、课程数、工具数都已前移，
> 逐条状态裁定（已完成 / 已过时 / 已放弃 + 理由 + 证据）写在 09-16 那节的「旧条目状态裁定」里。
>
> **本文是唯一对外路线图**：`README.md`（Roadmap 节）、`README.zh-CN.md`、`README.ja.md`、
> `CONTRIBUTING.md` 都只链接 `ROADMAP.md`。`docs/roadmap/` 下的四个文件与
> `docs/rfc-280-90-day-roadmap.md` 是历史材料（提案、任务拆分、bounty 描述），没有对外入口链接，
> 且已被本轮内容取代。

This roadmap covers August-November 2026. It is biased toward one practical
flywheel. The November section integrates competitive analysis findings from
TeamMemory and WeKnora research (#1162-#1168).

```text
private intake -> classification -> maintainer demand board -> curated lesson/rescue/issue
```

MisakaNet should stay offline-first and Git-backed. External listings are useful
"amplifiers", not the product itself.

## 2026-10-02 更新 — 交付、在飞与 KV 迁移到 D1

> 本节只写 **2026-09-16 之后的增量**：上一轮的五层拼图、四类用户路径、六步优先级**仍然有效**，
> 这里回答的是"这三周交付了什么、哪些还在飞、下一步先做哪一件"。
> `2026-09-16` 那节的文字、数字与裁定**一字未改**（本仓惯例：旧条目只加状态裁定，不改写历史）。
> 本节每条断言都带 issue / PR 号，可按文末附录逐条核；核不动的明确标 **未验证**。
> **语料规模不写成本节的"当前值"**：看 09-16 节的「当前数字」动态徽章（`data` 分支的 `badges/*.json`，
> 由 `update-badges.yml` 每日重算）；本节出现的唯一规模数字是附录里一条带日期的命令输出。

### 现在在哪（2026-09-16 → 2026-10-02）

**一、DSH 客户端半身：从"只有 MCP 工具"变成"宿主里看得见的一层"。**

| 面 | 落点（PR） | 状态 |
|---|---|---|
| 插件面声明（图标 / 生态元数据 / 实测兼容行） | #2543、#2546 | 已合并（09-30） |
| 检索结果的**可见性**（命中数 / 置顶那条 / 证据等级 / 新鲜度；`tool.call.toolview`，**不发任何 POST**） | #2551 | 已合并（09-30） |
| 复用投票（Helpful / Not what I needed；`conversation.chat.assistant-actions`，`order: 20`） | #2551 | 已合并（09-30） |
| 右栏面板（`sidebar.right.pane.tab`：本会话问过什么 / 报过什么 / 可信度 / 活动 / 语音） | #2551 | 已合并（09-30） |
| 左栏常驻入口 + 它打开的页面 | #2582 | 已合并（10-01） |
| `/misakanet` 命令 + 浮层（在 composer 里作答） | #2598 | 已合并（10-01） |
| 插件页的 MCP 行配置（只读） | #2599 | 已合并（10-01） |
| 设置 → General 的 MisakaNet 行（语音开关） | #2600 | 已合并（10-01） |
| zh/en locale（UI 走 `ctx.locale`，包元数据走 `locale/*.json`） | #2602 | 已合并（10-01） |
| 全窗口 toast + 侧栏底部动作（复制本会话活动） | #2618 | 已合并（10-01） |
| 客户端行为 e2e：一次性真宿主 + 真 Chromium，三场景 | #2610 | **在飞（open）** |
| 2.41.0 的 release 承载 | #2591 | **在飞（open）** |

- 这些客户端面由 **2.41.0 的 release PR #2591** 承载；截至本行 #2591 仍是 open，仓库里最后一个 tag 是
  `v2.40.0`（附录命令 ④）——所以"已合并"指**落在 `main` 上**，不等于"已发布"。
- **检索行与投票是两个座位，不是一个**（#2551 的第一版把它们混在一起，动机就是纠正它）：`tool.call.toolview`
  只做可见性，**不发任何投票**；投票注册在 `conversation.chat.assistant-actions`（`misakanet-verdict`，
  `order: 20`），即"最终助手消息"那一条动作行——检索时修复还没跑，"did this help?" 在那个时刻答不了。
  判据（可实跑，附录命令 ⑥）：`python3 -m pytest tests/test_dsh_plugin_surface.py -q` 里的
  `test_the_visibility_surface_cannot_vote` 断言检索行体内不得出现 `post(`；分工原文
  "Posts nothing." 在 `docs/maintainer/client-half-acceptance.md` §0。
- **#2610 之前，客户端行为只有人工 Playwright**：静态门禁只钉"注册了没有"（座位声明了、字典键存在、
  schema 与默认值一致），看不见"到底发生了没有"。它把 `slash-overlay` / `frame-wide-toast` /
  `settings-to-panel` 三场景变成可自动跑的检查；宿主是一次性的 `DSH_HOME`，语料库被拦截，不依赖线上。
- 一条会踩坑的记法：同一批里的 **#2607（"toast + 侧栏底部动作"）关闭未合并**，#2618 把这两面连同
  "面板抄哪一段会话"一起落地——按"关掉的 PR"去找产物会找不到。
- **未验证**：线上 2.41.0 的实际发布状态（本节只读仓库与 tag，没有调 npm / PyPI；`v2.40.0` 之后无新 tag）。

**二、容量：唯一真把功能打挂过的配额问题，现在有位置了。**

- **2026-09-12 生产事故（记在 #1647）**：KV 免费档只有 **1,000 次「写到不同 key」/天**；
  `misakanet_register` 报 `KV put() limit exceeded for the day.`，而 cron 的索引重写（同 key）照旧成功——
  **需要新 key 的路径先死**：注册一次要两个新 key（`node:<id>`、`mcp_token:<token>`），计数与它抢同一个预算。
- **2026-09-22/23 复发（#2111）**：`/api/health` 连续 ~14 小时 `degraded`，`degraded_reason: kv writes failing
  (quota 10048)`（10048 = Cloudflare 的"KV PUT 每日上限"）。读没事（KV 免费档 100,000 次读/天），
  所以症状是**陈旧**而不是"打不开"：索引重发不了，检索只能供 `evidence_level: ""`（#2080）。
- **PR #2639（2026-10-01 合并）**：`/api/lessons` 加 120 秒边缘缓存（`caches.default` + `Cache-Control`，
  `workers/lessons-cache.test.mjs` 钉住），并给 `misakanet-register-proxy` 打开 `[observability]`——
  在那之前它是**唯一没有日志、却承载全部动态流量**的 worker，所以账号内也答不了自己的容量问题。
- 它给出的容量口径：D1 免费档 500 万行读 + 10 万行写每天，Workers 10 万请求每天；相除 = **每请求 50 行读 /
  1 行写**。**D1 超限是 Worker 内部报错，fail open 救不了这一层**——写侧迁移是下一面墙，不是"优化"。

### 下一步（2026-10-02 起）

**① KV → D1 写侧迁移（#2115，open，`priority:high`）** ← 本仓唯一真把功能打挂过的配额问题，排第一

- 现状（2026-10-02 在 `main` 上重数，附录命令 ②）：

  ```text
  kvPut(env,          9
  MISAKANET_KV.put(   2
  storePut(env,      26    ← 这些已经"先写 D1"
  ```

  #2115 自己的清单是 **2026-09-23** 实测的 `30 / 27 / 7`——三周里计数与注册 key 都已迁 D1
  （#1647–#1649 建表、#1804 迁注册），**迁移已比 issue 描述走得更远**，但 issue 仍未关：
  剩下的写点按"每天新增多少 key"分类，而那张清单里"无界的那一类"**已经不在了**——#2117
  （**2026-09-24 关闭**，completed）把每地址限流整族搬进 D1：`rate:feedback` / `rate:intake` / `rate:connect`
  走 `storePut(env,`（D1 优先，KV 只是回退），`rate:read` / `rate:signal` 只剩 `counters` 表的 legacy key
  形状，同样只在 D1 缺失或写入失败时才落到 KV。今天这个文件里还会走 `kvPut(env,` 的只剩四类，都不是
  "每请求一个新 key"：`gap:<query>` + `gap:index`（#1649 起 D1 优先；KV 路径只给没有 D1 binding 的部署，
  另受每天 400 个新 key 的上限）、`node_counter`（单个固定 key，重写不新增）、`telemetry:newkeys:<date>`
  （每天一个新 key，它本身就是那个上限计数器）、以及 `bumpCounter` 的 legacy counters 回退（附录命令 ⑦）。
- 为什么放在最前：它不是性能问题，是**用户看得见的失败**——注册路径直接报错、索引重发不了、检索字段变空；
  这三件事在 09-12 与 09-22 各发生过一次。
- 验收（**口径以 #2115 的 "How this epic ends" 为准**）：`/api/health` 在普通日子不再出现
  `degraded_reason: kv writes failing`，即**写量降到免费额度以下**（#2115 原文：不是因为配额几小时后就重置），
  #2111 可以关闭。**与 #2115 的差异写在明处**：本节还想再严一档——`kvPut(env,` / `MISAKANET_KV.put(`
  的每个直写点都写明"为什么必须留 KV"——但那是**本节的自我要求，不是 #2115 的关闭条件**，不能拿它当判据。

**② provenance gate 已在跑（#1768）；intake conversion receipt 在飞（#1528 / #2491）。**

- #1768（2026-09-16 合并）：`scripts/check_provenance.py` + `.github/workflows/provenance-gate.yml` +
  `data/provenance-baseline.json`（`known_dead: []`）。它把"来源存不存在"从人工阅读变成自动挡：
  触发条件是 PR 动了 `lessons/**`、检查脚本或基线，另有一条每周的 link-rot 定时（report-only）。
- 本轮实跑（离线口径，附录命令 ⑤）：**检查 477 篇课程、引用 35 条外链，exit 0**。这是 2026-10-02 的
  命令输出，**不是当前值**——当前语料规模看动态徽章（两个口径的差别 09-16 节已解释）。
- **仍未解决**（09-16 节已写，本节不改写）：语义真伪——一个真实但无关的链接仍会通过这一档。
- intake conversion receipt：#1528（issue，open）的设计由 **#2491**（PR，open）实现——课程转正后给报料
  来源回执。它决定"报料者能不能知道自己有用"，是飞轮闭环的那一环。
- 这两条是 09-16 节优先级 ② / ③ 的前置：**先让来源可信、让报料者有回执，再谈中文检索与企业材料。**

**③ 09-16 节的其他优先级不动。** ① provenance 门禁已由 #1768 落地；③ 中文检索、④ 首次调用可观测、
⑤ 两页企业说明、⑥ 多 agent 协同语义仍按原顺序——缺的是执行，不是重新排序。

### 本节不做

- **不改 09-16 节**：它的文字、数字、裁定一律保留（旧条目只加状态裁定，不改写历史）。
- **不把语料规模写成"当前值"**：受管计数句子在 09-16 节的「当前数字」，只认 `badges/*.json` 动态徽章；
  本节唯一的规模数字是带日期的命令输出（477 篇），引用时必须带那个日期。
- 不为对齐路线图去动生成物（`data/lessons.json`、`docs/data/*`、`docs/lessons/**`）。
- 不顺手重构 `workers/register-proxy-sw.js`：① 是一项独立迁移（#2115），不是这条路线图的附带修改。

### 附录：本节断言的复现命令

```bash
# ① 这些 PR / issue 的标题与状态（本节引用的号都在这一行里）
for n in 2543 2546 2551 2582 2598 2599 2600 2602 2607 2610 2618 2591 2639 2115 1528 2491 1768; do
  curl -sS -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/Ikalus1988/MisakaNet/issues/$n" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('#%s'%d['number'], d['state'], d['title'])"
done

# ② KV 写点（#2115 用的同一口径：按出现次数，不按行）
grep -o "kvPut(env," workers/register-proxy-sw.js | wc -l
grep -o "MISAKANET_KV.put(" workers/register-proxy-sw.js | wc -l
grep -o "storePut(env," workers/register-proxy-sw.js | wc -l

# ③ 120 秒边缘缓存与 observability
grep -n "LESSONS_TTL_SECONDS" workers/register-proxy-sw.js
grep -n -A2 "^\[observability\]" workers/wrangler.toml

# ④ 客户端半身就在这个文件里；哪一批落的看提交，发布到哪看 tag
git log --oneline -8 -- lib/client.js
git tag --sort=-v:refname | head -1

# ⑤ provenance gate（离线，不碰网络）
python3 scripts/check_provenance.py --offline --check

# ⑥ 客户端两个座位：检索行只做可见性、不投票（离线）
python3 -m pytest tests/test_dsh_plugin_surface.py -q   # 含 test_the_visibility_surface_cannot_vote
grep -n "tool.call.toolview\|conversation.chat.assistant-actions" lib/client.js
grep -n "Posts nothing" docs/maintainer/client-half-acceptance.md

# ⑦ #2117（每地址限流迁 D1）已关闭，与文件里还剩的 KV 写点
curl -sS -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/Ikalus1988/MisakaNet/issues/2117" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('#%s'%d['number'], d['state'], d['state_reason'])"
grep -n "rate:feedback\|rate:intake\|rate:connect" workers/register-proxy-sw.js
grep -n "storePut(env, fbRateKey\|storePut(env, intakeRateKey\|storePut(env, connRateKey" workers/register-proxy-sw.js
grep -n "await kvPut(env," workers/register-proxy-sw.js   # 7 处：6 处直写 + storePut 自己的 KV 回退（另 1 行是注释）
```

---

## 2026-09-16 更新 — 五层拼图与优先事项

> 本节是三周多来第一次更新，内容来自 `docs/maintainer/blueprint-and-strategy-review-2026-09-16.md`
> （维护者侧审视：§1 五层拼图 / §2 四类用户路径 / §3 信任层实测 / §4 飞轮与引爆点 /
> §5 十条最薄弱假设 / §6 六步优先级）。
>
> 规则：**本节所有数字都来自下面附录里的命令，可逐条复现**；无法复现的结论一律标注 **未验证**，
> 不标注即视为已复现。下面 2026-08-22 的原文一律不删，只在新章节里给状态裁定。

### 当前数字（动态徽章，不写死）

| 指标 | 数值 |
|---|---|
| 公开索引语料 | ![lessons](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/lessons.json) |
| domain 覆盖 | ![domains](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/data/badges/domains.json) |

> 这两行不再是写死在文档里的数字：徽章读 `data` 分支的 `badges/*.json`，由 `update-badges.yml` 每日从
> `data/lessons.json`（语料）与 `scripts/sync_lesson_count.py::canonical_domains`（domain）重算，
> 所以数字没法过期——它不在文档的字节里。`llms.txt` 是唯一保留字面计数的入口（读它的人不会执行 JS）。
>
> 这一节以前由 `scripts/sync_lesson_count.py` 写死维护；起因是下面那张快照表——2026-09-23 实测它
> **13 项里 9 项过期**（393/232/43 对 411/1047/44），而它周围写着"所有数字可逐条复现"。
> **可复现 ≠ 会被重算**：这些数字此前没有写作者（#2095）。
>
> **下面那张 2026-09-16 的快照表是当天的记录，不是"当前值"**，其中的数字故意保留原样——
> 本仓的惯例是旧条目只加状态裁定、不改写历史。
>
> **状态裁定（2026-09-26）：节点数不再对外发布。** 它不是用户数——`data/counter.json` 的 `current`
> 是单调的**编号分配计数器**（匿名调用每次都会新建一个 node），只会随自动化增长，因此五个曾引用它的
> 表面（`docs/llms.txt` 两份、`README.zh-CN.md`、`README.ja.md`、本表）都已去掉该行，
> `sync_lesson_count.py --metric nodes` 也已移除。快照表里那一行只是当天的记录，其"来源命令"已失效。

### 状态快照（2026-09-16）

| 指标 | 数值 | 来源命令 / 文件 |
|---|---|---|
| 公开索引语料（SSOT） | **393** | `python3 scripts/sync_lesson_count.py --check` → `every managed lesson count == 393`（读 `data/lessons.json`） |
| `lessons/` 下 Markdown 总数 | **440** | `find lessons -name '*.md' -type f \| wc -l` |
| 已注册节点 | **232** | `python3 scripts/sync_lesson_count.py --check`（node 行） |
| domain 覆盖 | **43** | 同上（domain 行） |
| 主包 / 发布账本版本 | **2.30.2** | `grep -m1 '^version' pyproject.toml`、`.release-please-manifest.json`、`server.json` |
| 已发布 npx 安装器版本 | **0.5.3** | `packages/misakanet-setup/package.json` |
| 远端 MCP 工具数 | **7** | `grep -o 'name: "misakanet_[a-z_]*"' workers/register-proxy-sw.js \| sort -u \| wc -l` |
| 本地 stdio MCP 工具数 | **10** | `python3 -c "from misakanet.server import TOOLS; print(len(TOOLS))"`（2026-09-30 起含 `misakanet_me_events`，代理到远端；详单见 `.codex-plugin/plugin.json` 的 `mcp.local.tools`） |
| 安装器支持的 agent 目标 | **5**（claude / codex / hermes / openclaw / codewhale） | `packages/misakanet-setup/bin/misakanet-setup.mjs:72` |
| 回归查询夹具 | **11 条 / 8 类**（`updated: 2026-08-13`） | `data/regression_queries.json` |
| 带 `provenance` 的课程 | **399 / 440（91%）** | 附录命令 ⑥ |
| 带 `evidence_level` 的课程 | **98（22%）** | 附录命令 ⑥ |
| 带 `evidence_refs` 的课程 | **3（0.7%）** | 附录命令 ⑥ |
| `lessons/verified/` 里的正式课程 | **0**（目录里只有 `README.md`） | `ls lessons/verified/` |
| Python 测试 / worker 测试 | **123 / 32** | `ls tests/*.py \| wc -l`、`ls workers/*.test.mjs \| wc -l` |

**两个课程数不是矛盾，是两个口径**，引用时必须说清是哪一个：

- **393** 是"我们对外发布的索引语料"，取自 `data/lessons.json`，也是 README / 站点被门禁盯住的数字
  （`scripts/sync_lesson_count.py --check` 不一致即失败，AGENTS.md §6 有这条红线）；
- **440** 是 `lessons/` 目录下的全部 Markdown，含 `lessons/templates/`、各语言目录和仓库自述文件。
  蓝图审视 §3 用的是这个口径，所以那里写"440 篇"。旧版本的 377 / 363 / 289 都是更早的口径快照。

**信任层的三个数字要放在一起才构成结论**：`provenance` 覆盖 91%，但 `evidence_level` 只有 22%、
`evidence_refs` 只有 3 篇，`lessons/verified/` 一篇正式课程都没有。字段填了，来源本身却绝大多数
不可核验——蓝图审视 §3 据此判定 96% 的 `provenance.source` 取值是 `community` / `external` 这类
标签（该百分比是审视方口径，本节的 91% / 22% / 3 篇是按附录命令 ⑥ 重算的，两者解析细节略有差异，
结论方向一致）。所以：**不要把 393 读成"393 篇已验证"。**

顺带说明**定义已经有了，缺的是执行**：`docs/trust-semantics.md` 把 `indexed` / `published` /
`verified` 三词和 E0–E4 证据等级、晋升规则都写清楚了，但除了 `lesson_gate.py` / `injection_scan.py`
之外，**没有任何门禁去验证一个来源是否真实存在**——这正是下面优先级 ① 要补的缺口。

### 旧条目状态裁定

| 旧条目（2026-08-22 及更早） | 状态 | 理由 / 证据 |
|---|---|---|
| 基线：`GitHub release v2.18.0` | **已过时** | 发布已走到 **2.30.2**：`.release-please-manifest.json`、`pyproject.toml:7`、`server.json` 三处一致 |
| 基线：PyPI `misakanet-core` | **已过时** | 现在的 PyPI 标识是 **`misakanet`**：`pyproject.toml:6`、`server.json` 的 `packages[0].identifier` |
| 基线：`377 indexed failure lessons` | **已完成并前移** | 现为 **393**，且从"手写数字"改成 `scripts/sync_lesson_count.py` 统一维护 + `--check` 门禁 |
| 基线：`Local MCP server exposes three tools` | **已过时** | 本地 stdio 服务现 **10** 个工具（含 `misakanet_memory_context` / `misakanet_usage_status`，以及 2026-09-30 起代理到远端的 `misakanet_me_events`），远端端点 **7** 个；远端集合是本地集合的子集 |
| 基线：Smithery / GitHub `/mcp` 暂停 | **仍然成立** | 与 External channel policy 一致，本轮无外部证据可推翻（**未验证**外部页面） |
| 8月 v2.17.0：Lesson Lint（P0） | **已完成** | `scripts/lesson_lint.py` 存在；`.github/workflows/lesson-quality.yml:31` 以 `--fail-on high` 跑 |
| 8月 v2.17.0：GX1 闭环（#968 合并） | **已放弃** | commit `42e374345 fix(security): revert GX1 changes, keep security hotfix only`——GX1 被显式回滚，只保留安全修复 |
| 8月 v2.17.0：版本漂移清理（同步到 v2.17） | **已过时** | 手工对齐被自动机制取代：`scripts/sync_lesson_count.py --check`（计数）。**2026-09-25 更正**：这里原写"+ `scripts/update_status.py`"，该生成器已连同 `STATUS.md` 一起删除（#2095），且它从未在任何 workflow 里跑过 |
| 8月 v2.17.0：Security 收尾（#969 / #964） | **部分可验证** | 回滚提交带 #964（`42e374345`）；#969 在 git 历史里只出现在 `docs/maintainer/handoff-2026-08-11.md`，**未验证**已关闭 |
| 8月 v2.17.0：定位固化到 `CONCEPTS.md` | **已完成（路径需更正）** | 文件是 **`docs/CONCEPTS.md`**，开篇即"不是通用记忆系统，不是 Agent runtime，不是向量数据库"；仓库根目录没有 `CONCEPTS.md` |
| 8月 v2.17.0：Duplicate governance | **已完成** | `docs/duplicate-governance.md` 存在 |
| 8月 v2.17.0：Regression queries（原定 6 类） | **已完成但停滞** | `data/regression_queries.json` 有 11 条 / 8 类，超过原定 6 类；但 `updated: 2026-08-13`，一个多月未增补。v2.16 表里写的"20+ 条"从未达到 |
| 8月 DoD：`python scripts/site_health.py` | **已过时（命令名变了）** | 现为 `python3 scripts/site_health_check.py [--write\|--json\|--strict]`，报告落在 `docs/maintainer/site-health-<date>.md` |
| 8月 DoD：`README / STATUS / ROADMAP 数字一致（289）` | **已过时** | 289 早已前移（现 393）；机制从"人工对齐"升级为 `sync_lesson_count.py --check` 门禁 |
| v2.16.0：`POST /api/intake` curl-first | **已完成** | `workers/register-proxy-sw.js:3801-3803` |
| v2.16.0：Classifier（lesson/rescue/bug/noise） | **已完成，但分类轴已分叉** | 脚本侧成立：`scripts/intake_classify.py`、`scripts/demand_board.py:38` 的 `VALID_CATEGORIES`。MCP 侧 kind 已改为 `missing_lesson` / `stale_lesson` / `new_lesson_candidate` / `question`（`workers/register-proxy-sw.js:300`）——**两条分类轴并存**，旧表述只对脚本侧成立 |
| v2.16.0：Demand board | **已完成** | `scripts/demand_board.py` + `tests/test_demand_board.py`、`tests/test_demand_board_gaps.py` |
| v2.16.0：Feedback CLI path（`--feedback`） | **已完成** | `search_knowledge.py` 的 `_collect_feedback()` 落 `data/search-feedback.jsonl`（首次使用时创建，当前不存在属正常） |
| v2.16.0：`tools/list` 暴露 3 个工具 | **已过时** | 远端现 7 个，且每个都写了副作用 / 鉴权 / 限额 / 返回结构（`workers/register-proxy-sw.js` 的 `MCP_TOOLS`） |
| v2.16.0：PR hygiene（#623 → #624 → #622） | **未验证** | 历史里只有 `8021e391a feat: absorb intake digest script from #623`；#624 / #622 在 `git log` 里查不到，无法判定结局 |
| 9月：Review queue 状态机 `private→accepted/rejected/needs-repro→converted` | **已过时（被取代）** | 实际实现是 `scripts/maintainer_review_queue.py`：**只读**、不做状态持久化，用 GitHub 标签 + 建议动作表达（`convert-to-lesson` / `needs-info` / `close-as-noise` / `merge-duplicate`），处置规则写在 `docs/maintainer/intake-triage.md`。旧表那套四态状态机**在仓库里没有任何实现**（全文只有 ROADMAP 自己提到 `needs-repro`） |
| 9月：Trust semantics 措辞统一 | **已完成** | `docs/trust-semantics.md` 明确定义 `indexed`（入索引，quality ≥ 0）/ `published`（过质量门，≥ 75）/ `verified`（人工核对来源，Rare），并定义 E0–E4 证据等级与晋升规则；README 的 E 级表与之一致。**残留两处**：该文档示例句里的 "249 indexed" 是旧数字（现 393，且不受 `sync_lesson_count.py` 的 SITES 覆盖）；`lessons/verified/` 里仍只有 README，所以 `verified` 这一档**目前不可对外声称** |
| 9月：Frontend health（`site-health` green） | **已过时** | 同 site_health 命令名变更，见上 |
| 9月：Docs cleanup（P2） | **仍然成立** | 仍是长期项，无验收物，无变化 |
| 10月：MCP runtime verification | **已完成（仓库侧）**，**一处未验证漂移** | 远端 7 工具定义在 `workers/register-proxy-sw.js`，`workers/mcp-endpoint.stress.test.mjs` 等覆盖 `tools/list`。但 `workers/register-proxy-sw.js:447` 的版本回退字面量仍是 `"2.27.1"`，而当前发布是 2.30.2，仓库里**没有任何 workflow 设置 `MCP_VERSION`**——线上 `initialize` 实际返回什么，需真机调用才能判定，本轮**未验证**，故不改 |
| 10月：Registry metadata refresh | **已完成** | `server.json` 版本 2.30.2，描述改为 "Failure-memory layer for coding agents: search evidence-rated failure lessons by error text." |
| 10月：Glama 跟进 / GitHub `/mcp` / Smithery | **未验证** | 需要外部页面与 GitHub 侧证据，本轮未联网核。旧条目"不为 listing polish 单独 bump 版本"仍然成立 |
| 10月：Adoption evidence（区分流量与课程复用） | **仍然成立，且有更好落点** | 见新优先级 ②：用事件表量化"命中 vs 未命中" |
| 11月 #1162（faithfulness） | **已完成（文件到位），但 DoD 跑不动** | `scripts/faithfulness_eval.py`（commit `9b498401a`）；DoD 的 `--batch data/usage_log.jsonl` 无法执行——`data/usage_log.jsonl` 在仓库里不存在 |
| 11月 #1163（freshness） | **已完成（换了落点）** | 实际是 `misakanet/freshness.py`（commit `ded6cad77`）+ `search_knowledge.py` 接线 + 远端 `freshness()`（`workers/register-proxy-sw.js:473`，recent/established/legacy）。旧条目点名的 `scripts/freshness_scorer.py --report` **从未存在** |
| 11月 #1164（gap analysis） | **已完成（换了落点）** | 实际是 `scripts/demand_board.py`（含 gaps）+ `data/search_gaps.jsonl`（35 行）+ 远端 `/api/search-signal`（#788，commit `15648942f`）。旧条目点名的 `scripts/gap_analyzer.py --top 20` **从未存在** |
| 11月 #1165（context tool） | **已完成，但只在本地** | `misakanet_memory_context`（commit `36709441d`）在 stdio 服务器的 `TOOLS` 里；**远端 7 工具里没有它**。旧 DoD"`misakanet_context` tool in `tools/list`"只对本地成立 |
| 11月 #1166（memory dump watcher） | **已完成** | `misakanet/watcher.py` + `misakanet watch` CLI（commit `5403e28cb`） |
| 11月 #1167（progressive disclosure） | **已完成** | 远端 `misakanet_search` 的 `detail` 三档 `compact\|summary\|full`（commit `6fc48e033`，PR #1322） |
| 11月 DoD：usage log 有 ≥1 条 `was_used=True` | **未达标 / 不可验证** | 本地没有 `data/usage_log.jsonl`；线上用量在 Worker 侧，本轮读不到 |
| 11月 DoD 的三条脚本命令 | **需按实际落点改写** | 两条脚本名（`freshness_scorer.py` / `gap_analyzer.py`）不存在，见 #1163 / #1164 两行 |
| Quality Loop Architecture / Competitive Insights | **结构仍成立** | 只是 #1162–#1166 的**文件名与表里不一致**（见上），照旧条目去找脚本会找不到 |
| External channel policy | **基本不变** | MCP Registry 元数据已随 2.30.2 更新（见 10 月行）；Smithery 仍暂停、GitHub `/mcp` 仍未提名（**未验证**） |
| Standing principles（7 条） | **全部保留，且有第 7 条的反例** | DCO + gate + CI **挡不住编造来源**：蓝图审视 §3 的 #1713 是 24 项检查全绿、`source:` 指向 404 仓库 |

补充三处文档之间的矛盾（不是状态问题，是记录问题，供后续整理时注意；本轮只改
`ROADMAP.md` 与 `docs/rfc-280-90-day-roadmap.md`，下面各处**未在本轮修改**）：

- **两个章节都叫 v2.17.0**：`August 2026 - v2.17.0` 与 `September 2026 - v2.17.0`。
- **October 写"v2.18/v3.0 readiness"，November 又写"v2.18"**，而 v2.18.0 在 2026-08-21 就已发布（见基线节）。
- **~~README 的路线图表与本文其余部分不一致~~ —— ✅ 已于 2026-10-06 修复。**
  这条自查笔记说 README 里还列着 "Q1 2027 | Hub Federation, i18n | 📋 Planned"，
  而 `docs/roadmap/long-term.md` 记着 "2026-08-31: … Hub was retired the same day"。
  **两个前提现在都不成立**：那一行 2026-09-20 就删掉了（`26fc0eeb`），
  同一批里 `README.zh-CN.md` 那张停在 "v2.9.x / v3.0" 的版本表也已删除，
  三个 README 现在一律只链到本文。

  这条笔记本身当时还引了一个**已经不存在的 README 行号** —— 记录这个问题的文档，
  比它记录的问题更陈旧。这才是值得记住的教训：**自查笔记也会腐烂，所以它同样需要门禁**。
  `tests/test_doc_line_citations.py` 现在会检查全仓库任意 markdown 里的 `文件:行号`
  引用是否落在该文件的真实行数内。

### 新优先级（按"解锁面 ÷ 成本"排序）

顺序沿用蓝图审视 §6，每条的"现状"都能在仓库里查到；括号里是接手时最省力的入口。

**① provenance 可解析性门禁** ← 最高性价比（≈10 行脚本 + 1 个 CI 步骤）

- 目标：把 `source:` 的可解析性变成自动挡，而不是靠维护者逐条读。这是把第 ④ 层信任从"人工可信"
  推向"机制可信"的唯一便宜杠杆。
- 现状（2026-09-16）：`scripts/lesson_gate.py` 查结构、`scripts/injection_scan.py` 查注入、
  DCO 查签核——**没有一个验证来源真伪**。
- **已完成（2026-09-16，PR #1768）**：`scripts/check_provenance.py` + `tests/test_check_provenance.py`（29 项，离线）
  + `.github/workflows/provenance-gate.yml` + `data/provenance-baseline.json`，规则文档见
  `docs/maintainer/provenance-gate-2026-09-16.md`。现有 439 篇 / 31 条外链零例外通过（`--check` exit 0），
  用 #1713 那份 404 来源做红队样例时退出码为 1。
- 验收（已达）：一个故意编造来源的新 lesson 在 CI 上红；现有语料不因历史欠债被全量拦下。
- **仍未解决**：语义真伪（一个真实但无关的链接仍会通过）。这一档只能靠人或 `scripts/faithfulness_eval.py` 那类检查。

**② 量化"命中 vs 未命中"** ← 不需要新工程线，现在就能做

- **现状（2026-09-21 更新）**：**分母已经有了**。#1779（2026-09-16 关闭）让 worker 侧的
  `misakanet_search` 把命中一起写进 D1 `search_signals`；KV 的 unsolved map 仍然只记未命中，
  那是它的职责，不是缺口——两者别混为一谈。
- **已完成（2026-09-21）**：`/api/search-signals/stats` 增加服务端聚合 `breakdown`：按天、按
  `domain` 的**计数**，**只回计数**——不带 query 文本、不带 lesson id，读取口径不变（新增的只是
  汇总，不是逐条细节）。`scripts/search_hit_rate.py` 据此打印两张 Markdown 表，按 domain 的那张
  **按命中率从低到高排**，直接回答"下一步该补哪块语料"。
- **已上线（2026-09-21）**：worker 部署完成后，`/api/search-signals/stats` 真的返回 `breakdown`，
  `python3 scripts/search_hit_rate.py --since 7` 直接打出上面两张表——验收物不再是「本地能跑」而是
  「线上能查」。
- 首次线上实测（2026-09-21，7 天窗口）：`total 259 / hit 191 / miss 68 / hit_rate 73.8%`，
  按天最低的一天是 62.2%、最高 84.7%（样本还小，别把它当趋势）。
- **仍未解决**：
  1. **复用侧的分子没接**——`/api/helpful` 票数与 `misakanet_me_events` 的 E4 信号还没进这张表，
     所以它衡量的是"检到东西"，不是"帮上了忙"；
  2. **网站检索页仍只上报未命中**（`docs/search/index.html` 在 `topScore >= 0.35` 时直接返回）。
     要补它的命中，就得让页面也发查询文本，而那正是当前刻意避免的——**这是一个隐私取舍，
     需要单独决定，不该顺手改**；
  3. 计数只覆盖走 worker 的调用：本地 stdio MCP 与页面检索不在其中（脚本的 caveat 已列）。
- 验收（已达）：一张能贴进 release notes 的表——`python3 scripts/search_hit_rate.py --since 7`
  输出里的"按天（UTC）"与"按 domain"两张表。

**③ 中文 / 自然语言的检索路径** ← 直接解锁 §2.1 的目标用户

- 现状：语料按错误文本 / 关键词索引；中文整句问句（如"如何切换识图模型"）命中≈0
  （蓝图审视 §2.1 实测，"已知≈0，未修"）。这让"傻瓜式安装"只对会用英文错误串的人成立。
- **✅ 已落库并接线**（本条曾长期写着 "in progress, 尚未落库"，那是错的）：别名表在
  `data/query-aliases.json`（约 90 条 zh→en，如 `识图模型`→`vision model`、`乱码`→`encoding`），
  接在 `misakanet/search/engine.py` 的查询改写里，并内嵌进 worker 默认开启。
  设计记录仍在 `docs/maintainer/query-alias-design-2026-09-16.md`；
  实测 top-1 40%→70%、top-3 50%→80%、线上零查询词 11/20→0/20（同文件 `:8-9`）。
- 可接手内容：别名表 → 查询改写；FAQ 前置（`misakanet_search` 已有 FAQ 命中路径，返回
  `type="faq"` + `issue_url` + `answer`）；注意 `data/synonyms.json` 与
  `tests/test_synonym_expansion.py` 已存在，**不要再造第二份同义词数据**。
- 验收：一组中文自然语言问句（≥20 条，含上面那条）top1 命中率从 0 抬到一个可引用的数字，
  且英文错误串检索**不回退**。

**④ 首次调用可观测** ← 把"模型听不听话"从轶事变成数字

- 现状：`packages/misakanet-setup/bin/misakanet-setup.mjs` 的 `--report` 会打印本机状态，
  但结尾两行是**留给人手填的空字段**：`tools-visible: {}` 与 `live-call-evidence: ""`
  （第 1280–1282 行，注释自述这是"the only parts this tool cannot know"）。这恰好是最重要的那两行。
- 可接手内容：在 `integrations/agent-autostart/checkpoint_reminder.mjs` 这一层记录 MCP 调用次数
  并写进 report 的**既有字段**，而不是新增一个只有内部人看的埋点。
- 验收：安装后 24h 内"是否出现过首次 `misakanet_search` 调用"变成一个数字——蓝图审视 §5 的假设 1
  （"装上就会用"）因此从"不可测"变成可证伪。

**⑤ 两页企业自托管说明** ← 把"机构有益"从潜力变成可谈判材料

- 现状：**零材料**。`docs/rfc-280-90-day-roadmap.md` 的 Vision 4 只提过 Enterprise / Internal
  deployment，无 PRD、无实现。机构会问的三件事（数据不出域 / 可审计 / 配额可见）逐条对照见
  蓝图审视 §2.4。
- 可接手内容：两页 Markdown——一页边界（哪些数据留在本地、哪些必须出网：远端 MCP、D1、KV），
  一页问答（事件表 `misakanet_me_events` / `/api/search-signal` 的聚合能回答什么、**不能**回答什么，
  因为当前没有 tenant / actor 维度；配额现状是 IP 级 5 次/天）。
- 明确不做：**不承诺不存在的自托管部署形态**。`DEPLOYMENT.md` 写的是公开服务的部署路径，
  不等于机构私有部署，两页里要把这条说清。
- 验收：一页边界 + 一页问答，能被机构拿去当谈判材料且不含未实现承诺。

**⑥ 多 agent 的最小协同语义（任务认领 + 回执 + 租约）**

- 现状：现在是"同一个知识库被多个 agent 读"，**不是协同**。缺任务层语义、缺冲突检测；
  `agent_type` / `client_id` 是自声明、不可验证（`AGENTS.md` §3.3 已自认"不把它当作归属证据"）。
- 可接手内容（全部建在现有事件表上，不新增存储）：以 `misakanet_me_events` 的事件骨架加
  `task_id` / `claim` / `lease_until`；回执复用 `misakanet_submit_intake` 已有的 `receipt` 字段形状；
  语料里已有 `lessons/en/idempotent-task-claim.md` 与
  `lessons/contrib/shared-json-needs-atomic-write.md` 两篇可直接当设计输入。
- 顺序约束：**先解决"这是谁"（可核验的 actor），再做冲突检测**——否则协同层建在自声明身份上。
- 验收：两个 agent 并发认领同一任务时，第二个拿到明确的"已被占用 + 租约到期时间"，
  而不是各自闷头做一遍。

**第 7 步（非技术用户 GUI）明确排在 ① 与 ③ 之后**：`docs/install/index.html` 已是落地页，
但按蓝图审视 §6 第 6 条，① 与 ③ 未完成时 GUI 只会把摩擦放大到更多不会用的人身上。

### 本轮仍然不做

- 不新增 badge-only / listing-only 的 PR（旧策略不变，且现在更需要把力气花在 ① 上）
- 不为"多 agent 协同"扩检索工具面——缺的是协同语义，不是更多工具
- 不把 393 / 440 写成"已验证课程"（`lessons/verified/` 里一篇正式课程都没有）
- 不为了对齐路线图而改任何受门禁保护的生成物（`data/lessons.json` 只能由
  `update_lessons_json.py` 生成，见 AGENTS.md §6）

### 附录：本节数字的复现命令

```bash
# ① 公开索引语料 / 节点 / domain（读 data/lessons.json，与门禁同一口径）
python3 scripts/sync_lesson_count.py --check

# ② lessons/ 下的 Markdown 总数（蓝图审视 §3 用的是这个口径）
find lessons -name '*.md' -type f | wc -l

# ③ 版本
grep -m1 '^version' pyproject.toml && cat .release-please-manifest.json
python3 -c "import json;print(json.load(open('packages/misakanet-setup/package.json'))['version'])"
python3 -c "import json;print(json.load(open('server.json'))['version'])"

# ④ 远端 / 本地 MCP 工具数
grep -o 'name: "misakanet_[a-z_]*"' workers/register-proxy-sw.js | sort -u | wc -l
python3 -c "from misakanet.server import TOOLS; print(len(TOOLS))"

# ⑤ 安装器支持的 agent 目标
sed -n '72p' packages/misakanet-setup/bin/misakanet-setup.mjs

# ⑥ 信任层覆盖：provenance / evidence_level / evidence_refs（2026-09-16 输出 440 399 98 3）
python3 - <<'PY'
import re, pathlib
fm = []
for p in pathlib.Path('lessons').rglob('*.md'):
    t = p.read_text(encoding='utf-8', errors='ignore')
    m = re.match(r'\s*---\s*\n(.*?)\n---', t, re.S) or re.match(r'\s*\{(.*?)\n\}', t, re.S)
    fm.append(m.group(1) if m else '')
key = lambda k: sum(1 for b in fm if re.search(rf'(?m)^\s*"?{k}"?\s*:', b) or f'"{k}"' in b)
print(len(fm), key('provenance'), key('evidence_level'), key('evidence_refs'))
PY

# ⑦ 其他计数
ls lessons/core/*.md | wc -l; ls lessons/verified/; ls tests/*.py | wc -l; ls workers/*.test.mjs | wc -l
python3 -c "import json;d=json.load(open('data/regression_queries.json'));print(len(d['queries']),'queries /',len(d['categories']),'categories, updated',d['updated'])"
```

---

## Current baseline

> ⚠️ **2026-08-22 快照，已过时**：版本 2.18.0 → 2.30.2，语料 377 → 393，本地 MCP 3 → 9 个工具，
  PyPI 名从 `misakanet-core` 改为 `misakanet`。逐条裁定见上方 2026-09-16 章节。

- Release/distribution: PyPI `misakanet-core`, GitHub release `v2.18.0`,
  Glama indexed/scored, MCP Toplist badge live, Remote MCP endpoint.
- **v2.18.0 done (2026-08-21): Agent-first registration, preflight guardrails, Remote MCP intake): Remote MCP, pairing code, Identity Aura, Voice Prompts, evidence levels, security hotfixes.
- Test suite: passing.
- Public site is online: homepage, `/search/`, journey page, Worker APIs, and
  lesson data endpoints are healthy.
- Corpus wording baseline: **377 indexed failure lessons**; avoid claiming
  all are verified unless also stating the verified count separately.
- Local MCP server exposes three tools: `misakanet_search`,
  `misakanet_get_lesson`, and `misakanet_submit_usage`.
- PR governance: DCO is mandatory. Do not deep-review or merge DCO-failing PRs.
- External listing posture: Glama/MCP Registry/MCP Toplist are stable; Smithery
  and GitHub `/mcp` inclusion are deferred until the product loop is stronger.

## August 2026 - v2.17.0: Trust & Curation Hardening

> 状态（2026-09-16）：Lesson Lint、Duplicate governance、定位固化（**文件在 `docs/CONCEPTS.md`**）
> 已完成；**GX1 闭环已放弃**（commit `42e374345` 显式回滚，只留安全修复）；版本漂移清理已过时
> （改由 `sync_lesson_count.py --check` 自动维护——原文还写了 `update_status.py`，该生成器与
> `STATUS.md` 已于 #2095 一并删除）；DoD 里的
> `scripts/site_health.py` 已改名 `site_health_check.py`；289 这个数字已前移。

Goal: 把 v2.16.0 的增长势能收敛成"可信、可维护、可审计的 failure-memory 网络"。

| Track | Priority | What to ship | Gate |
|---|---:|---|---|
| **Lesson Lint** | P0 | `scripts/lesson_lint.py` 非阻塞试运行 | 0 high issues, CI job running |
| **GX1 闭环** | P0 | #968 合并, lessons.json 同步 | README/STATUS/lessons.json = 289 |
| **版本漂移清理** | P0 | STATUS/ROADMAP 同步到 v2.17 | 无版本号矛盾 |
| **Security 收尾** | P0 | #969 合并, #964 关闭 | Release notes 包含安全修复 |
| **定位固化** | P1 | "这不是什么" + Git-backed 到 CONCEPTS.md | 文档一致 |
| **Duplicate governance** | P1 | 重复 lesson 处理流程 | docs/duplicate-governance.md |
| **Regression queries** | P1 | `data/regression_queries.json` | 覆盖 6 个核心 failure 类型 |

### v2.17.0 Definition of Done

```bash
python scripts/lesson_lint.py --lessons-dir lessons --fail-on high
python scripts/lesson_gate.py <changed lessons>
python scripts/site_health.py
```

并且：
- README / STATUS / ROADMAP 数字一致（289）
- `data/lessons.json` 已重新生成
- 没有无关未跟踪文件
- Lesson lint 0 high issues

## August 2026 - v2.16.0: Remote MCP + Security hardening

> 状态（2026-09-16）：`POST /api/intake`、classifier、demand board、`--feedback` 路径**均已完成**
> （脚本见 `scripts/intake_classify.py`、`scripts/demand_board.py`）。**"3 个工具"已过时**（远端 7 个）；
> **intake 分类轴已分叉**：MCP 侧 kind 现为 `missing_lesson` / `stale_lesson` / `new_lesson_candidate`
> / `question`，与脚本侧的 lesson/rescue/bug/noise 并存。PR hygiene（#623/#624/#622）**未验证**。

Goal: a sandbox, agent, or human can submit a private redacted failure report;
maintainers can classify and route it without exposing raw logs or prompts.

| Track | Priority | What to ship | Gate |
|---|---:|---|---|
| **Curl-first intake** | P0 | `POST /api/intake` for explicit opt-in, private, redacted feedback | `curl` smoke test returns an intake id; no raw log/prompt/file content stored |
| **Classifier integration** | P0 | Route intake into `lesson`, `rescue`, `bug`, or `noise` | Unit tests cover redaction, empty payloads, and category routing |
| **Demand board** | P0 | Maintainer-facing board of intake clusters and next actions | Board shows pending/reviewed/routed items from fixture data |
| **Feedback CLI path** | P1 | Search/CLI `--feedback` path that reuses the same policy boundaries | Local JSONL or API submission is explicit and documented |
| **MCP tool clarity** | P1 | Keep tool descriptions aligned with side effects, auth, rate limits, input/output schema | `tools/list` exposes all 3 tools with operating-contract descriptions |
| **PR hygiene** | P1 | Work through DCO-clean intake PRs in order: #623 -> #624 -> #622 | No DCO, no merge; competing PRs use first clean + scoped + tested wins |

### v2.13.0 milestone requirements

**Release blocker requirements:**

- `POST /api/intake` accepts a minimal payload from plain `curl` without any
  GitHub account, browser session, or API client SDK.
- Intake payloads are redacted before persistence; stored records must not keep
  raw logs, prompts, file contents, tokens, or environment dumps.
- Every accepted intake receives a stable id, timestamp, source type, redaction
  summary, and initial routing category.
- Classifier output is constrained to `lesson`, `rescue`, `bug`, or `noise`,
  with an `unknown`/low-confidence path that does not crash the pipeline.
- Demand board can show at least: new, reviewed, routed, and rejected items.
- Maintainer can manually override the classifier category without editing raw
  JSON by hand.
- Tests cover: empty body, oversized body, secret-like strings, invalid JSON,
  duplicate submission, and one valid end-to-end fixture.

**Definition of done:**

```text
curl -> /api/intake -> redacted private record -> classifier category -> demand board row
```

A release is not ready until that chain is demonstrated in docs or CI evidence.

Out of scope for v2.13.0:

- Auto-publishing public lessons
- Auto-opening GitHub issues
- Auto-submitting PRs
- Full Danmaku launch
- Re-publishing Smithery or bumping registry versions just for listing polish

## September 2026 - v2.17.0: curation and trust quality

> 状态（2026-09-16）：**本节的版本号与上一节重复，两者都写 v2.17.0**，记录时需注意。
> regression queries / duplicate governance / trust semantics 均已完成——**信任三词（indexed / published /
> verified）与 E0–E4 证据等级已由 `docs/trust-semantics.md` 定义**，README 与之一致；
> regression queries 为 11 条 8 类（原表写 20+，未达到）且 `updated: 2026-08-13` 后停滞；
> 另外 `lessons/verified/` 目录里**只有 README，没有一篇正式课程**，所以"verified"这一档
> 至今不可对外声称；review queue 的四态状态机**已被 `scripts/maintainer_review_queue.py`
> 的只读标签模型 + `docs/maintainer/intake-triage.md` 取代**。

Goal: turn intake into trustworthy public knowledge without metric drift or
lesson spam.

| Track | Priority | What to ship | Gate |
|---|---:|---|---|
| **Review queue** | P0 | Intake review states: private, accepted, rejected, needs-repro, converted | Maintainer can trace one intake to one lesson/rescue/issue decision |
| **Lesson trust semantics** | P0 | Clarify `indexed`, `published`, and `verified` wording across README/docs/site | README, site counters, and generated data agree on counts and labels |
| **Regression queries** | P1 | `data/regression_queries.json` for DCO, GitHub token, pip timeout, MCP, Feishu, FANUC, WSL | Search tests include representative real failure queries |
| **Duplicate governance** | P1 | Continue duplicate/stale lesson policy without blocking useful contributions | New lessons pass quality checks and do not duplicate existing lessons silently |
| **Frontend health** | P1 | Keep search, registration, journey, and API health in every public UX change | `site-health` green before release notes |
| **Docs cleanup** | P2 | Remove or archive stale generated/runtime artifacts and obsolete examples via separate small PRs | Each cleanup PR has one purpose and no generated data churn |

### v2.14.0 milestone requirements

**Release blocker requirements:**

- Review queue has explicit states and a documented transition path:
  `private -> accepted/rejected/needs-repro -> converted`.
- Each converted intake links to exactly one public artifact type first:
  lesson, rescue card, GitHub issue, docs fix, or duplicate/no-action note.
- Trust wording is consistent across README, homepage, generated data, and
  release notes: `indexed`, `published`, and `verified` do not mean the same
  thing.
- Regression query fixtures exist for the recurring failure classes that bring
  users to MisakaNet: DCO, GitHub token/auth, pip timeout, MCP setup, Feishu,
  FANUC/RAG, WSL/Windows encoding, and CI cache/build failures.
- Duplicate governance gives maintainers a clear decision: merge, link,
  supersede, reject, or ask for reproduction.
- Search/demand-board changes include empty, loading, error, and no-result
  states, not just the happy path.

**Definition of done:**

```text
intake cluster -> maintainer review -> trusted public artifact or explicit rejection
```

A release is not ready if intake accumulates without a review path.

## October 2026 - v2.18/v3.0 readiness: distribution confidence

> 状态（2026-09-16）：registry 元数据已完成（`server.json` 2.30.2 + 新描述）；MCP runtime verification
> 在仓库侧成立（7 个工具 + `tools/list` 测试），但 `workers/register-proxy-sw.js:447` 的版本回退字面量
> 仍是 `"2.27.1"` 而发布已是 2.30.2，且没有任何 workflow 注入 `MCP_VERSION`——**线上实际返回值未验证**。
> Glama / GitHub `/mcp` / Smithery 三条需要外部证据，本轮**未验证**。
> 另注：本节标题与下一节都提到 v2.18，而 v2.18.0 早在 2026-08-21 就已发布。

Goal: make external discovery channels reflect a stable product, not a vanity
badge collection.

| Track | Priority | What to ship | Gate |
|---|---:|---|---|
| **MCP runtime verification** | P0 | Verify deployed/listed runtime `tools/list` sees all intended tools | Evidence from local smoke + listed runtime scan or Glama refresh |
| **Registry metadata refresh** | P1 | Next real release may add clearer `server.json` title/description and aligned counts | Only publish a new version when there is a real release, not duplicate-version churn |
| **Glama quality follow-up** | P1 | Improve MCP tool coherence/completeness where it maps to real behavior | Glama score page updates without breaking existing install path |
| **GitHub `/mcp` candidacy** | P2 | Reconsider email nomination after v2.13 loop is live and metadata is clean | Official Registry active + Glama evaluated + concise use-case evidence + no version mismatch |
| **Smithery** | P2 | Keep paused unless there is a real `.mcpb` or public MCP endpoint with no 403 scan blockers | No placeholder URLs; no duplicate-version publish attempts |
| **Adoption evidence** | P2 | Separate traffic metrics from lesson-use evidence | Release notes say what was measured: views/clones/helpful/intake, without overclaiming adoption |

### v2.15/v3.0 readiness milestone requirements

**Release blocker requirements:**

- Local MCP smoke test proves `tools/list` exposes all expected tools and each
  tool has side effects, auth, rate-limit, input, output, and error semantics.
- At least one external scanner/listing reflects the current runtime metadata;
  stale Glama or Registry snapshots are documented rather than silently ignored.
- `server.json`, README badges, PyPI package version, GitHub release, and Glama
  wording do not contradict each other in a user-visible way.
- Registry metadata refresh only happens with a real versioned release; duplicate
  version publish attempts are explicitly avoided.
- GitHub `/mcp` nomination remains optional and requires evidence: Official MCP
  Registry active, Glama evaluated, working quickstart, clear one-sentence use
  case, and at least one demonstrable intake-to-lesson loop.
- Smithery remains paused unless there is either a valid `.mcpb` release artifact
  or a public MCP endpoint that automated scanners can initialize without 403.

**Definition of done:**

```text
local MCP contract -> external listing metadata -> user can install/search without version confusion
```

A release is not ready if it improves badges while making installation or
runtime verification less clear.

## November 2026 - v2.18: Agent Memory Quality Loop

> 状态（2026-09-16）：**#1162–#1167 全部已实现，但落点与下表文件名不同**，照表去找脚本会找不到：
> `#1162` → `scripts/faithfulness_eval.py`；`#1163` → `misakanet/freshness.py`（**不是**
> `scripts/freshness_scorer.py`）；`#1164` → `scripts/demand_board.py` + `data/search_gaps.jsonl` +
> 远端 `/api/search-signal`（**不是** `scripts/gap_analyzer.py`）；
> `#1165` → `misakanet_memory_context`（**只在本地 stdio 服务器，远端 7 工具里没有**）；
> `#1166` → `misakanet/watcher.py`；`#1167` → 远端 `detail=compact|summary|full`。
> 下面的 DoD 三条命令里有两条脚本不存在；且 `data/usage_log.jsonl` 在仓库里不存在，
> 所以"usage log 有 ≥1 条 `was_used=True`"**未达标 / 不可验证**。

Goal: close the loop from "lesson exists" to "lesson is used and stays fresh".
Inspired by competitive research into TeamMemory (MCP team memory) and WeKnora
(Tencent RAG platform). See #1162-#1168.

| Issue | Priority | Track | What | Gate |
|---|---:|---|---|---|
| #1162 | P0 | Faithfulness | RAGAS-style auto-detect lesson usage via LLM judge | `faithfulness_eval.py` runs on usage_log, `was_used` count > 0 |
| #1163 | P0 | Freshness | Quality decay with configurable lifecycle (14d protection, −1/day) | `freshness_scorer.py` runs, stale lessons flagged |
| #1164 | P1 | Demand Board | Gap analysis: track zero-result queries, surface unmet needs | `gap_analyzer.py` outputs top 20 gaps, demand board has Gaps tab |
| #1165 | P1 | MCP | `misakanet_context` tool: proactive lessons at task start | Tool registered in `tools/list`, returns compact context ≤500 tokens |
| #1167 | P1 | Search | Progressive disclosure: compact→summary→full detail levels | `misakanet_search` accepts `detail` param, compact ≤80 tok/lesson |
| #1166 | P1 | Intake | Memory dump watcher: auto-extract lessons from agent logs | `misakanet watch` monitors dir, creates drafts with `pending_review` |

### v2.18 Definition of Done

```bash
python scripts/faithfulness_eval.py --batch data/usage_log.jsonl --threshold 0.5
python scripts/freshness_scorer.py --lessons-dir lessons --report
python scripts/gap_analyzer.py --input data/search_gaps.jsonl --top 20
```

并且：
- `misakanet_search` supports `detail=compact|summary|full`
- `misakanet_context` tool in `tools/list`
- Freshness scores in lesson metadata
- Demand board shows Gaps tab
- Usage log has ≥1 entry with `was_used=True`

### Quality Loop Architecture

```text
Agent searches → compact results → uses lesson → faithfulness eval → was_used
    ↓                                                                       ↓
    └── freshness boost ←───────────────────────────────────────────────────┘
        ↓
    Lesson stays fresh → appears higher in search → more usage → flywheel
```

### Competitive Insights Applied

| Source | Insight | MisakaNet Action |
|---|---|---|
| TeamMemory | RAGAS faithfulness eval auto-detects usage | #1162 LLM judge on usage_log |
| TeamMemory | Quality decay (14d protection, −1/day, slow below 50) | #1163 freshness lifecycle |
| TeamMemory | Obsidian Watcher auto-extracts from vault | #1166 memory dump watcher |
| WeKnora | Progressive skill loading (L1→L2→L3) | #1167 compact→summary→full |
| WeKnora | 29 MCP tools with scoped runtime | #1165 context tool for proactive lessons |


## External channel policy (external amplifiers)

> 状态（2026-09-16）：表里的立场**基本不变**，仅是 MCP Registry 元数据已随 2.30.2 更新。
> "不为 listing polish 单独 bump 版本"这条继续有效。Glama 分数、GitHub `/mcp` 提名状态、
> Smithery 现状**均未验证**（需要外部页面）。

External surfaces help users discover MisakaNet, but they must not drive rushed
architecture changes.

| Channel | Current stance | Do next | Do not do |
|---|---|---|---|
| **Glama** | Keep stable | Maintain score badge and improve real tool descriptions | Do not churn versions only to chase score |
| **MCP Registry** | Published | Update metadata on next real release | Do not republish duplicate `2.12.2` |
| **MCP Toplist** | Badge live | Treat as discovery signal | Do not call it official recommendation |
| **Smithery** | Paused | Revisit only with real bundle/endpoint | Do not publish placeholder URL or break Glama path |
| **GitHub `/mcp`** | Deferred | Reassess after v2.13 intake is demonstrable | Do not email before value proposition and metadata are clean |

## Standing principles

> 状态（2026-09-16）：**全部保留**。第 7 条"Evidence over hype"在本轮拿到了一个反例：
> DCO + lesson gate + CI **挡不住编造来源**——PR #1713 的 24 项检查全绿，`source:` 却指向一个
> 404 的仓库（见蓝图审视 §3）。因此新增优先级 ①（provenance 可解析性门禁）来补这个缺口。

1. **Root cause first.** Fix the implementation problem before changing tests.
2. **Explicit consent.** External submission must be opt-in, redacted, and private by default.
3. **No silent collection.** No raw logs, prompts, file contents, or secrets.
4. **Git as source of truth.** Markdown/JSON first; databases and dashboards are derived surfaces.
5. **Small PRs win.** One bounded change with a test beats broad rewrites.
6. **No DCO, no merge.** DCO is a release-safety gate, not paperwork.
7. **Evidence over hype.** Every milestone needs a command, page, check, issue, or release artifact.

## Contribution focus

> 状态（2026-09-16）：下面的清单里 **Intake endpoint / Classifier / Demand board 三项已交付**
> （见上方裁定表），继续做它们的边际收益已经很低。**当前想直接上手，请看 2026-09-16 章节的
> 「新优先级」①②③**——那六条才是按"解锁面 ÷ 成本"排过序的。

Good next contributions:

- Intake endpoint tests and redaction fixtures
- Classifier routing fixtures
- Demand board states and empty/error UI
- High-signal lessons from real failures with verification commands
- MCP tool description and runtime-scan evidence
- Small docs fixes that reduce newcomer friction

Avoid for now:

- More badge-only PRs
- New public listing submissions without product evidence
- Auto-publication of private feedback
- Large hub rewrites not needed for the intake loop
