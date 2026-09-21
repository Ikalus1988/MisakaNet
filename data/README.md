# data/ — 生成物与它们的消费者

⚠️ **此目录下的文件由脚本 / CI 自动生成，请勿手动编辑。** 提 PR 时请忽略此目录的 diff。

**每个生成物必须能回答三个问题**：谁生成它、谁读它、多久更新一次。这张表就是为了让"下一个
`sync-data.yml`"在**写出来之前**被问一句"谁读它"——那个 workflow 每天把 `counter.json` 与
`lessons.json` 往 `data` 分支推，而两个文件在仓内**没有任何消费者**，触发条件又永远不会满足，
于是它自 2026-09-15 起静默死亡（#1985）。`tests/test_data_inventory.py` 让这张表与本目录无法再漂移。

**消费者一栏写"无"不是笔误**：那表示它是一个还没有人读的产物。无消费者的生成物是纯成本，
而且会伪装成一条活着的自动化；要么给它一个消费者，要么删掉它。

| 文件 | 生成者 | 消费者 | 频率 |
|---|---|---|---|
| `lessons.json` | `scripts/update_lessons_json.py`（**唯一**合法生成器，#1374）| 检索、站点、Worker、agent（本仓最重要的生成物）| CI 每日（`update-lessons.yml`）+ push |
| `domains.json` | `scripts/normalize_domains.py` | `scripts/expand_query.py`、`scripts/lesson_gate.py`、计数门禁 | 手动 / 随语料变更 |
| `synonyms.json` | 手写维护（`scripts/sync_lesson_count.py` 读）| 检索扩展 | 手动 |
| `query-aliases.json` | `misakanet/search/engine.py`、`scripts/expand_query.py` | 检索扩展、`tests/test_query_alias_wiring.py` | 手动 |
| `counter.json` | `.github/workflows/register.yml`（注册流程写 D1 后镜像）| `scripts/sync_lesson_count.py`（README/站点计数 SSOT）| 随注册 + 每日镜像 |
| `quality_scores.json` | **无现存生成者**（`scripts/check_lesson_quality.py` 已不再写它；引用它的只有 `archive/dead/` 与测试）| **无** | 快照停在 141 篇（语料已 402 篇）——待判决：删掉或重建 |
| `contributor-points.json` | `scripts/update_contributor_points.py` | `workers/register-proxy-sw.js`、`docs/contributor-points.md` | 手动 |
| `intake-kind-hints.json` | `scripts/sync_intake_hints.py` | `scripts/intake_kind.py` | 手动 |
| `provenance-baseline.json` | `scripts/check_provenance.py` | `provenance-gate.yml`（溯源门禁）| PR + 定时（周）|
| `pr-genius-stats.json` | `scripts/pr_genius_stats.py` | 站点（全站**唯一** `data/` fetch）、`workers/register-proxy-sw.js` | 手动 / CI |
| `pr-genius-observations.jsonl` | `scripts/pr_genius_observe.py` | 无（观察记录，供人工分析）| 手动 |
| `publish_rhythm.jsonl` | `scripts/publish_rhythm.py` | 无 | 手动 |
| `retrieval_noisebench_queries.json` | `scripts/retrieval_noisebench.py` | `scripts/retrieval_noisebench.py`（自用）| 手动 |
| `retrieval_noisebench_report.json` | `scripts/retrieval_noisebench.py` | 无（报告产物）| 手动 |
| `bm25_weight_benchmark.json` | `scripts/benchmark_bm25_weights.py` | 无 | 手动 |
| `lesson_reuse_benchmark.json` | 手动运行的基准产物（数据停在 2026-07）| 无 | 手动 |
| `lesson_reuse_leaderboard.json` | 手动运行的基准产物（数据停在 2026-07）| 无 | 手动 |
| `benchmark_tasks.json` | **手写输入**（不是生成物）| `tests/test_benchmark_tasks.py` | 手动 |
| `regression_queries.json` | **手写输入**；`archive/dead/scripts/verify_regression_queries.py` 是旧写入者 | `workers/query-alias-expansion.test.mjs` | 手动 |
| `leaderboard.json` | `scripts/gen_leaderboard.py`、`scripts/leaderboard_watch.py` | **无**（站点排行榜走 Worker `/api/insights/reputation-leaderboard`；见 #1919）| push 到 main |
| `bench_leaderboard.json` | `scripts/gen_leaderboard.py`、`scripts/leaderboard_watch.py` | **无**（同上）| push 到 main |
| `leaderboard_meta.json` | `scripts/gen_leaderboard.py`、`scripts/leaderboard_watch.py` | **无**（它是"上次看到的值"的落盘，供 `leaderboard-watch.yml` 自己比对）| push 到 main |
| `okf/lessons.jsonl` | `scripts/export_okf.py` | 外部 OKF 消费者 | 手动 |
| `okf-test/lessons.json` | `scripts/export_okf.py`（测试拓扑）| `tests/`（OKF 导出测试）| 随测试 |
| `dco_benchmark_result.json` | **孤儿**：写入者是 `archive/dead/scripts/dco_benchmark.py` | 无 | 已停 |
| `.gitkeep` | — （占位，保证目录存在）| — | — |

## `main` 的 `data/` 与 `data` 分支各自服务谁

| 位置 | 谁生成 | 谁读 | 说明 |
|---|---|---|---|
| `main` 的 `data/` | 上表各生成者 | 上表各消费者 | **正常工作路径**：站点、Worker、agent、测试都读这里 |
| `data` 分支 | `update-badges.yml`（**PAT** 推送，活着）| shields.io 徽章端点（README 的 Lessons / Tools / Domains / Smithery 徽章）| 只有 `badges/*.json` 被消费 |
| `data` 分支的 `counter.json` / `lessons.json` | 曾经由 `sync-data.yml` 推送 | **无** | 该 workflow 已于 2026-09-21 删除：触发条件（`push` 改动这两个文件）永远不会满足，因为写它们的 `update-lessons.yml` 用的是 `GITHUB_TOKEN`，而 **GITHUB_TOKEN 的推送不触发 workflow**（#1985）|

## 外部贡献者注意

- 提 PR 时请忽略此目录的 diff，不要手动修改任何 JSON；
- 如需新增数据文件，请把生成逻辑写进 `scripts/`、在 `.github/workflows/` 里配置更新，**并在本表补一行**
  （门禁会要求：新文件没有登记行 = 变红）。
