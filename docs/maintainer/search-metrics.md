# 检索命中率（search metrics）

> issue #1779。这一页只讲一件事：worker 记录了什么、怎么把命中率算出来、这个数字能说明什么。
> 结论先放这里：**在改动部署并积累出样本之前，本项目没有任何可信的命中率数字**，第 5 节写的就是当前的真实状态。

## 1. 为什么会有这个文件

`workers/register-proxy-sw.js` 以前只在检索**未命中**时写**信号**（gap 计数器 + 未命中失败地图 `/api/search-signal`），
命中的检索在信号侧什么也不留 —— 结果是"命中率"这个唯一能支撑"能提效"说法的数字根本没有**分母**，
`docs/maintainer/blueprint-and-strategy-review-2026-09-16.md` §4.3 里给"提效"打 0.5/1 就是因为这个。
（严格说，命中的检索**确实**在 `lesson_usage` 里留了一条 `event='search'`，但它不能用来算命中率：见第 2 节末尾。）

现在：**每一次 worker 侧完成的检索都写一行信号**（命中与未命中同一张表、同一套字段），
聚合脚本把它算成 `total / hit / miss / hit_rate / legacy_rows`。

## 2. 字段定义

表 `search_signals`（D1）。一行 = 一次**完成的**检索（`misakanet_search` 返回了结果对象）。

| 字段 | 含义 | 取值 |
|---|---|---|
| `id` | 自增主键 | INTEGER |
| `solved` | 这次检索是否命中 | `1` = 返回了 ≥1 条结果；`0` = 走了 `no_match` |
| `query` | 查询文本，截断 200 字符 | 与既有 miss 路径同一口径（见下） |
| `top_id` | 第一条结果的 id（没有 id 时用 path） | 未命中为 `NULL` |
| `result_count` | 响应里实际带了几条结果 | 未命中为 `0` |
| `domain` | 调用方传的 `domain` 过滤参数 | 没传为 `""` |
| `created_at` | 写入时间 | DB 默认 `datetime('now')`（UTC），与 `lesson_usage`/`counters` 一致 |

**写入位置**：检索结算处，命中分支与 `no_match` 分支各一处，每次检索**恰好**写一行。
写入用 `ctx.waitUntil` 投递（不阻塞响应），并且整段包在 try/catch 里 ——
**记录失败绝不影响检索本身**（和 `trackUsage` / `logSearchGap` 同一条规矩）。

**什么时候不写行**：被限流（429）、`query` 缺失、课程加载失败等**提前返回**的请求。
这些请求不在分母里，所以分母 = "worker 结算过的检索"，不是"所有请求"。

**隐私口径**：`query` 存原始文本（截断 200），这**不是**新口径 ——
既有 miss 路径的 `counters.bucket`（`logSearchGap`）与 `lesson_usage.query`（`trackUsage`）本来就是原文。
只读端点（第 3 节）**不外发 query**，只回 `solved` 与 `created_at`。
（`POST /api/search-signal` 那条对外通道维持原样：分类后丢弃原文，只存派生的 family + reason。）

**表的创建**：worker 在首次写入前执行一次 `CREATE TABLE IF NOT EXISTS search_signals`（每个 isolate 一次，幂等），
这样"只推 worker"就能上线，不需要先跑 schema 工作流。`workers/d1/schema.sql` 里**暂时没有**这张表的声明
（本 issue 的改动范围不含该文件）；想把它补进 schema 的话，在 `workers/d1/schema.sql` 里加同名 DDL 再手动跑
`.github/workflows/apply-d1-schema.yml`（`workflow_dispatch`）即可，两边 DDL 必须一致。

**为什么不在 `lesson_usage` 上加一行**：旧路径其实**已经有**命中行（`event='search'`）和未命中行（`event='no_match'`），
但那张表没有 `solved` / `result_count` 列，加列就要改 `workers/d1/schema.sql`（本 issue 文件范围外）；
而且公开的 `/api/analytics` 只给按 query 的 top-10 分组计数，同一个 query 可能同时出现在 `top_searches` 和
`knowledge_gaps` 里（`no_match` 是在 FAQ 合并之前结算的），两边加起来算不出可信的命中率。
所以新表存在的理由是：**命中与未命中由同一段代码、用同一套字段写下来**。

## 3. 怎么取数

### 3.1 聚合脚本（推荐）

```bash
python3 scripts/search_hit_rate.py                  # 最近 7 天，人类可读
python3 scripts/search_hit_rate.py --since 30       # 最近 30 天
python3 scripts/search_hit_rate.py --json           # 机器可读（同样五个数字 + caveats）
python3 scripts/search_hit_rate.py --url http://127.0.0.1:8787/api/search-signals/stats   # 本地 wrangler dev
```

- 只用标准库；除了一次 GET 之外不碰服务端，**只读**。
- 窗口由服务端在 SQL 里过滤（`created_at >= datetime('now','-N days')`），脚本不自己筛时间。
- 令牌可选：`--token` 或 `$MISAKANET_TOKEN`。端点目前是**开放的**（与 `POST /api/search-signal` 同一姿态，
  因为只回 `solved`/`created_at`，没有 query 文本）；脚本仍会带上令牌，方便以后收紧时不用改脚本。
- 取数失败时**退出码 2 并明确说"测不出"**，不会打印 0%。

### 3.2 只读端点

```
GET https://misakanet.org/api/search-signals/stats?days=7
→ {"days":7,"source":"d1:search_signals","limit":10000,
   "rows":[{"solved":1,"created_at":"2026-09-16 10:00:00"}, ...],
   "truncated":false,"generated_at":"..."}
```

- `days` 默认 7，钳在 1–365。
- 行数上限 10000；超过时 `truncated: true`，此时算出来的只是**下界**。
- 首次检索记录之前表还不存在，端点回 `rows: []`（200，不是 502）—— 这是"还没有样本"，不是故障。
- 没有绑定 D1 时回 `503 {"error":"D1 not configured"}`。

### 3.3 直接查 D1（维护者本地）

```bash
npx wrangler d1 execute misakanet-db --remote --command \
  "SELECT solved, COUNT(*) FROM search_signals \
   WHERE created_at >= datetime('now','-7 days') GROUP BY solved"
```

## 4. 这个数字是什么、不是什么

**是**：我们的语料（当前约 400 篇课程 + FAQ）能回答**我们的检索流量**里多大比例 —— 一个 worker 侧口径的检索质量数字，
它可以用来判断"补课程/改关键词/改相关性下限"有没有效果。

**不是**：

- ❌ **不是终端用户的生产力，也不能证明"提效"**。它测的是"我们答了自己的问题"，不是"agent 因此少花了时间/少失败了一次"。
  要支撑"提效"，需要的是复用证据（`misakanet_me_events` 的 helpful 票、基准引用、跨节点确认），不是命中率。
- ❌ `solved=1` 只表示"返回了 ≥1 条结果"，**不表示结果有用**；低相关性的命中同样是 1。
- ❌ 分母不含被限流/失败的请求（见第 2 节）。
- ❌ 不能和 `/api/analytics` 的旧口径**直接比较**：那里按 query 只给 top-10 分组计数，而且同一 query 可能既有
  `event='search'` 又有 `event='no_match'`（`no_match` 是在 FAQ 合并**之前**结算的），所以两边的数不是一回事。
- ❌ 缺 `solved` 的旧格式行按**未命中**计（保守），所以 `legacy_rows > 0` 时命中率被低估。

## 5. 第一个数字

```
状态：样本不足，等待数据
```

**今天（2026-09-16T16:48Z）实测**：`https://misakanet.org/api/search-signals/stats` 返回 **404**（本次改动尚未部署），
脚本的输出是：

```
取数失败：HTTP Error 404: Not Found
没有拿到任何行，因此这次**测不出**命中率（不是 0%）。
```

所以**现在没有任何可引用的命中率**，一个数字都不要写。补上它的步骤：

1. 改动合并到 `main` → `deploy-worker.yml` 自动部署（异步，先在线上确认
   `GET /api/search-signals/stats` 返回 200 而不是 404）。
2. 等窗口里积累出行（默认窗口 7 天，但第一天就有数；行数太少时**别下结论**）。
3. 跑 `python3 scripts/search_hit_rate.py --json`，把**原样输出**贴到这一节，并注明日期与窗口。

按现状估一下量级（**不是命中率，只是量级参考**）：同一时刻 `/api/analytics`（旧 `lesson_usage` 口径）
的 `top_searches` top-10 合计 110 次、`knowledge_gaps` top-10 合计 39 次、日事件量 24–102 条/天。
也就是说上线后一周大概能拿到**几百行**的量级 —— 够看趋势，**不够**支撑任何对外宣传。

## 6. 回滚

1. **先试 kill switch**：把 worker 变量 `MISAKANET_SEARCH_SIGNALS` 设为 `0`（wrangler vars / dashboard），
   记录立刻停止，检索路径不受任何影响（这就是它存在的意义：不用等一次部署）。
   删掉这个变量即恢复记录。
2. **完整回滚**：`git revert <commit>` 后 push 到 `main`。worker 改动 push `main` 即自动部署
   （`.github/workflows/deploy-worker.yml`），不需要手工 `wrangler deploy`；**部署是异步的**，回滚后要验证线上。
   回滚后 `/api/search-signals/stats` 路由消失，脚本会报 404（"测不出"），不是打印 0%。
3. **数据**：回滚不动表，留下的行不影响 worker；要清就
   `npx wrangler d1 execute misakanet-db --remote --command "DROP TABLE IF EXISTS search_signals"`。

## 7. 已知局限 / 待办

- 网站检索页、本地 stdio MCP 的检索不经过 MCP 工具结算处，**不在**这套记录里。
- 一个"先判 miss 记 gap、后因 FAQ 合并变成命中"的请求，会在 gap 计数器里留一条未命中痕迹（旧行为，本次未改），
  但信号行记的是调用方**实际拿到**的结果，所以两边偶尔会不一致；以信号行为准。
- 本表新建，所以 `legacy_rows` 在现实中通常是 0；只有把聚合脚本指向混有旧格式的数据（例如手动导出的旧行）时才会 > 0。
- `workers/d1/schema.sql` 的补录见第 2 节末尾。
- 测试：`node --test workers/search-signals.test.mjs`、`python3 -m pytest tests/test_search_hit_rate.py -q`。

## 8. 相关文件

- `workers/register-proxy-sw.js` — 记录处（检索结算分支）、`recordSearchSignal`、`GET /api/search-signals/stats`
- `scripts/search_hit_rate.py` — 聚合脚本
- `tests/test_search_hit_rate.py` — 聚合算术与 CLI 契约（离线）
- `workers/search-signals.test.mjs` — 检索路径写行、kill switch、失败不影响检索、端点契约
- `docs/maintainer/blueprint-and-strategy-review-2026-09-16.md` §4.3 — "能提效"的成色评估（本 issue 的由来）
