# Cloudflare 与 Google 免费/付费能力的落地判断（2026-10-31）

> 一次"哪些该做、哪些别做、按什么顺序"的决策记录。每一项都带仓库里的证据；
> 没有证据的写"未验证"，不写成结论。上一份评估在 `.cache/cf-paid-plan/EVALUATION.md`（本地、
> gitignored），本文是它可以入库的续篇：只回答"现在做不做、第一步是什么"。

## 0. 结论（按杠杆排序）

| # | 事项 | 判断 | 第一步 | 状态 |
|---|---|---|---|---|
| 1 | SSE 首字节（#4072） | **做，最高杠杆** | 让首个事件先于计算发出 | 未开始 |
| 2 | 邮件回执给"提交过的人" | **做，但触发点不是 intake** | 见 §1：邮件渠道已有回执；缺的是"变成课程后通知" | 方案已定 |
| 3 | AI Gateway 观测语义路径 | **做，一行 + 一个 var** | 已提交：`MISAKANET_AI_GATEWAY`（默认空 = 今天行为） | 本 PR |
| 4 | Analytics Engine 事件面 | **做，但排在 3 之后** | 1 个 dataset + 3 个写点（search / get_lesson / intake） | 设计完成 |
| 5 | Gemini 免费档 | **只做 benchmark**（与你的判断一致，仓库已在这么做） | 保持 `release` environment 持有 key，不进 Worker | 已符合 |
| 6 | Search Console | **做，最小 3 步** | DNS TXT 验证 + 提交 sitemap + 每周拉一次 API | 待凭据 |
| 7 | Colab 复现 notebook | **做，最便宜的可信度** | 一个 notebook：下载公开 BigQuery 数据集，复现 R@1 | 未开始 |

## 1. 邮件：回执**已经存在**，缺的是另一件事

先把事实摆清楚，因为它决定了要不要搬 outbox：

| 能力 | 现状 | 证据 |
|---|---|---|
| **入站**（`bot@`/`rescue@`/`lessons@`/`join@`） | 4 条路由 LIVE → `email-register`，转发给维护者并**回信** | `workers/email-register/wrangler.jsonc`；`src/index.js:172-187`（`new EmailMessage(...)` → `message.reply(reply)`） |
| **回执内容** | intake id / 类型 / node id / **GitHub issue 链接** / MCP 已给出的答案 | `buildReplyText({ intakeId, intakeType, nodeId, issueUrl, answer })` |
| **入站 → MCP intake** | 走 service binding，不需要 GitHub token | `src/index.js:327-333` |
| **出站主动发信**（Sending API） | 已部署但**不在仓库里**：`.cache/cf-paid-plan/email-outbox/`（`.cache/` 被 gitignore）；`send_email` 三个发件人 + Queue + DLQ + D1 台账 | 部署配置在 `.cache/.../wrangler.toml` |
| **实际量** | `email_sends` **8 行，全部 sent**；`subscribers` **0 行**；**没有任何自动化调用它**（只有人 curl） | D1 `misakanet-email` |

**所以"intake 收到时发一条回执"这件事，对邮件渠道已经做完了。** 匿名 MCP intake 没有邮箱地址，
按设计不可能发邮件——它拿到的回执是 GitHub issue 里的评论 + `misakanet_me_inbox` 轮询。

真正缺的那件、也是 #4106 故事的邮件版，是**"你报的东西变成课程了"**这一封：

> 2026-10-30 我关掉的 5 条 done-but-open（#3923–#3926、#3962）就是它：课程已经合入，报料者
> 不知道。邮件渠道有地址，所以这一封发得出去；MCP 匿名渠道发不出去，只能靠回执评论。

### 建议的迁移形态（不是"把目录搬过来"）

1. `workers/email-outbox/`（进仓库，`--dry-run` 平台）：从 `.cache` 迁 `wrangler.toml` + `src/index.js`
   + D1 schema，补 `node --test`（现在一行测试都没有），Deploy 走 `deploy-worker.yml` 的同款门禁。
2. **触发点**：一个 GitHub Action，在 `lessons/**` push 后——拿新课程的 `provenance.issue` →
   找该 issue 是否是 `[email/...]` 审计 issue → 从正文的 `**From:**` 取地址 → `POST /` 到 outbox
   （`SEND_TOKEN` 放 release environment）→ outbox 落 D1 台账后入队发送。
3. 隐私边界：地址只从**我们自己的**审计 issue 里取，不建立独立名单；每封邮件带一次性退订链接
   （`subscribers` 表已经预留）。
4. 不做的事：不搬"订阅/群发"那条路径（0 订阅者，写了也没人收）。

## 2. `rbc-telemetry` / `telemetry-db`

你另一个仓库的 worker（统计遥测），**不是本仓的遗留物**——本次审计照实记录，避免下次再被当成
异常。唯一相关的数字：它 7 天 1,302 请求、`telemetry-db` 94 KB，对 Workers 10M/月、D1 5 GB 的
额度影响可以忽略（合计 < 1%）。**不需要处理**，建议在账户清单里加一行注明归属。

## 3. AI Gateway：本 PR 已接上（默认关）

- 账户上 `misakanet-bench` 网关 2026-08-28 就存在（`cache_ttl 300`、`collect_logs true`），
  **最后一次日志 2026-10-12**——因为只有暂停的 benchmark 指向它，生产直接 `env.AI.run`。
- 改动：`semanticFallbackHits` 在 `MISAKANET_AI_GATEWAY` 非空时给 `env.AI.run` 加
  `{ gateway: { id } }`；默认空 = **今天的行为逐字节不变**（有测试钉住"未设置时不传第三参"）。
- 为什么用 var 而不是直接打开：这是唯一一条生产推理，且是延迟预算最紧的路径（BM25 无结果时才走，
  或 CJK 融合臂）。打开应当是一次 dashboard 编辑 + 一行回滚，而不是一次 deploy。
- 打开后要测的三件事（一天的日志就够）：语义路径 p50/p95、cache 命中率、token 花费。
- 成本上限：在网关上调 cost limit，**不要**先写代码。

## 4. Analytics Engine：值得做，但先让网关跑一天

- 现状：**0 实现**——没有任何 config 里有 `analytics_engine`，没有 `writeDataPoint`。
  今天的观测是 D1 counters + 7 天 Workers Logs。
- 它回答的是日志答不出的问题："上个月哪类查询没命中、哪个工具调用最慢、哪门语言的 misses 最多"。
  心跳面板 1 空着，正是因为没有事件面。
- 最小实现（一个 PR 的量）：
  - `[[analytics_engine_datasets]] binding = "EVENTS" dataset = "misakanet_events"`；
  - 三个写点：`search`（query_hash、结果数、命中 id、延迟）、`get_lesson`（id、是否 truncated）、
    `submit_intake`（kind、来源）；
  - 一条查询脚本 `scripts/ae_query.py`（SQL API），先只出三个数：miss 率、p95 延迟、按来源分布。
- 免费额度 $5 内含 10M 点/月；按现在 ~20k 请求/天、每请求 1 点，约 60 万点/月（6%）。

## 5. Gemini 免费档：只跑 benchmark（与你的判断一致）

仓库已经是这个形态，**不需要新决定**：

- `scripts/embed_vertex.py` 用 `gemini-embedding-001`（Vertex）产出离线 A/B 的向量臂；
  `docs/benchmarks/embedding-ab-2026-10-27.md` 里 gemini 0.727 vs bge-m3 0.636 的那一栏就是它。
- 生成路径**没有**用它：`scripts/backfill_structured_fields.py` 有 `--provider gemini`，但实测质量
  （泛化措辞、不可执行的 verify）不足以入库；2026-10-29 的回填仍然停在 Workers AI 的额度上。
- 规则（写进凭据文档）：`GEMINI_API_KEY` 只放 `release` environment；**绝不放 Worker secret**，
  因为免费档是 "Unpaid Service"，提示与输出会被用于改进产品并可能被人工审阅。

## 6. Search Console：最小三步

1. **验证**：DNS TXT（`_google-site-verification`）——用 Cloudflare API 加一条 TXT，或在 dashboard
   粘一条。没有验证就没有数据，这一步没有替代。
2. **提交 sitemap**：`https://misakanet.org/sitemap.xml`（`docs/sitemap.xml` 已由
   `build_lesson_pages.py` 生成）。
3. **每周拉一次**：Search Analytics API（1,200 QPM/站点），存成 `data/gsc/*.json` 或直接进 D1；
   关注两类：真实搜索词（这是"需求"的第一个外部信号）与 **2026-08-31 起可用的生成式 AI 表现报告**
   （AI Overviews / AI Mode 的曝光）。
- 它不设 cookie、不加载脚本，所以不违反 `docs/privacy/index.html` 的承诺——这点是选它而不是 GA4
  的唯一理由，也足够。

## 7. Colab：一个 notebook，换来"可引用"

公开数据集与查询集已经发布了（`scripts/publish_bigquery.py`，`allAuthenticatedUsers: READER`），
缺的是**别人能点开就跑**的那一页。最小实现：

- `notebooks/reproduce-r1.ipynb`：`pip install google-cloud-bigquery` → 查公开数据集 → 复现 267 条
  查询的 R@1（或直接读 `data/lessons.json`，不依赖 Google 账号）→ 打印一张表；
- README/benchmark 文档里加一行链接；
- 触发条件现成的：`docs/maintainer/resource-leverage-2026-10-28.md` 已经把它列为"等外部有人问
  怎么复现时再做"——这一条现在就可以提前做，因为它是**新增流量**的最便宜入口。

## 8. 不做清单

Hyperdrive（无外部 SQL）、Zaraz（无第三方脚本）、DEX（静态站收益低）、GA4（与隐私承诺冲突）、
AdSense（信任受损换不到钱）、Gmail SMTP（对不上 `misakanet.org` 的 SPF/DKIM，且 Cloudflare 邮件
已经能发）、给 AI Search 建生产实例（与"可审计 BM25"的产品身份冲突，只配做 baseline）。

## 9. 落地顺序（与 §0 一致）

1. SSE 首字节 → 2. 邮件"变成课程了"通知（§1）→ 3. AI Gateway 打开并测一天（本 PR 已就绪）→
4. Analytics Engine 事件面 → 5. Search Console 三步 → 6. Colab notebook。

前两项都直接命中"新东西被看见"：一个让搜索结果及时返回，一个让报料者知道自己的报告没有石沉大海。
