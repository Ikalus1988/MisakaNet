# D1 读放大：为什么"逐条修"是打地鼠，以及三层机制（2026-11-24）

这件事在这个仓里**已经发生第二次**了。第一次 2026-10-21（handoff §118.5）：一条前缀枚举查询
每次扫 68,892 行、24 小时 203 万行；那次的收尾是 `tests/test_d1_read_hotspots.py` —— 一个**为那条
查询手写的** replica 测试。第二次 2026-11-24：ladder 的 used-read 用了跨三列的 `OR` join，
**每次 1,040 万行、一个月 195.6 亿行（账户读总量的 90%）**，而那个测试没有覆盖它。

结论不是"机制缺失"，而是**机制是逐条登记式的**：一条查询一个测试、一个 marker、一份 replica。
仓里有 **70 个 `prepare(` 站点**，这个模式永远只覆盖被想起来的那几条。

## 为什么"再小心一点"和"给每条查询加 plan 断言"都不是答案

- **计划是版本相关的**：2026-11-24 实测，**同一条改写后的 SQL** 在本机 SQLite 与 CI 的 SQLite 上
  给出两种不同的执行计划（一个从 `search_signals` 驱动，一个从 `lesson_authors` 驱动），两者都是
  线性的。用 `EXPLAIN QUERY PLAN` 做通用门会随版本翻红。
- **失败是静默的**：结果正确、延迟可接受、不报错。它只在账单上现形。
- **成本不在代码所在的地方**：配额是账户级的，代码是语句级的，中间的对应关系没人记录。

## 三层，按"不需要有人想起它"排序

### L1 运行时计量（唯一能覆盖每一条语句的层，未做）

一个 seam：`workers/lib/sql.js` 导出 `run(env, id, sql, params)`，执行后读 **`D1Meta.rows_read`**
（D1 的结果 meta 自带，仓里那篇
`lessons/contrib/cloudflare-quota-is-per-account-so-the-second-service-needs-its-own-gate.md`
已经记过这一点），按 `id` 累加进 isolate 内的 `{calls, rows}`，每 N 次落一行到
`counters(scope='query_cost')`；`/api/insights/query-cost` 回前 20 名。

为什么是它：**成本和语句在同一个地方**，所以不需要有人预先知道哪条查询会出事。代价是 70 个站点
要迁到 seam 上，可分三批（先 `/mcp` 热路径，再 cron，最后其余），每批可单独验证。

### L2 声明门（已落地：`tests/test_worker_join_is_indexable.py`）

规则两条，都是"语法级"、与版本无关：

1. **`JOIN … ON … OR …` 一律禁止**。`OR` 跨列没有任何 SQLite 能用索引，计划必退化为笛卡尔积。
   这个形状在 SQL 里没有正当用法；`WHERE … OR …` 不受影响，测试里也钉住了这一点。
2. 跟进项：每个 JOIN 在 `workers/sql-joins.json` 里声明「谁给它索引」——照抄
   `tests/test_tool_naming_convention.py` 的**冻结名单**做法（既有条目冻结，新增的必须声明）。
   `indexed_by` 是**审阅提示，不是证明**；证明仍留在逐条的 replica 测试里。

这条能接住的是"形状"类错误（今天这次）。接不住"在没索引的列上 join、但没有 OR"——那需要 L1。

### L3 夜间 offender 报告（未做，约半天）

`scripts/d1_cost_report.py` 用 `d1QueriesAdaptiveGroups`（就是这次定位用的那个数据集：
**自带 `query` 维度**，不需要 `wrangler d1 insights`），每天读出 top 10：

- 按 `sum.rowsRead` 排序；
- 派生 **rows/call**（比总量更能说明"形状坏了"，今天的数字是 10,444,076）；
- 与昨天比，**只报新出现的条目**，否则同一条会天天占满列表。

超过阈值（例如 rows/call > 100k）就开/重开**一条** issue，附查询文本。前提：一个
`Account Analytics: Read` 的 API token 进 CI secret。

它不需要改 worker，所以能接住 L1 看不见的东西（迁移脚本、一次性 `wrangler d1 execute`）。

## 不做什么

- **不把 plan 断言做成通用门**（版本相关，见上）。
- **不追求"零全表扫"**：`SCAN` 小表经常是对的（16k 行 vs 400 行，驱动方向反过来更好）。
  要管的是**行数**，不是关键字。
- **不再加"一条查询一个手写测试"**：那是这次漏掉的原因，不是解药。

## 现状

| 层 | 状态 |
|---|---|
| L2 `JOIN…ON…OR` lint | **已落地**（`tests/test_worker_join_is_indexable.py`），并用"真实上线过的那段 SQL"验证它确实会红 |
| L1 运行时计量 | **第一批已落地**：`workers/lib/d1-cost.js` 包在 `d1Binding()` / `opsD1()` 这一处，所以 **70 个调用点一个都不用改**；每个结果读 `D1Meta.rows_read`/`rows_written` 累加到语句哈希；15 分钟 cron 把超过 5,000 行/次的前 25 条写进 `counters(scope='query_cost')`（`:calls` / `:rows` 两行，原子加法，多 isolate 会累加而不是覆盖）；`GET /api/insights/query-cost`（维护者 token）返回本 isolate 的 top 25。**已知盲区**写在模块头注释里：`first()`/`raw()` 不返回 `meta`（只计调用不计行），以及新 isolate 从零开始 |
| L2 JOIN 声明表 | 未做（`workers/sql-joins.json` 的抽取需要按 SQL 字面干净地把 JOIN 挑出来；试过两版抽取器都不够干净，宁可先只留形状门） |
| L3 夜间报告 | **已落地**：`scripts/d1_cost_report.py` + `.github/workflows/d1-cost.yml`（每天 05:17Z；报 rows/call、总量、**新出现的语句**；exit 2 = 读不到，workflow 会为它单独写一句话）。需要仓库 secret `CF_ANALYTICS_TOKEN`（**Account Analytics: Read**）—— 已配置 2026-11-24 |
