# The daily heartbeat

One comment per UTC day on the long-lived issue labelled **`heartbeat`**, answering exactly three
questions about the traffic — **who is calling, what they asked, and whether it helped** — plus a
fourth panel about the **intake pipeline**: issues in, lessons out, and where the backlog is oldest
(see [Panel 4](#panel-4--the-pipeline-issues--lessons)). The owner reads one
notification and does nothing — there is no vote, no button and no manual dispatch in the loop.
The point is the frame the project is built on: MisakaNet earns its keep as the owner's own
cross-agent failure memory, so the numbers that matter are calls, topics, and reuse.

| | |
|---|---|
| Composer | [`scripts/heartbeat_report.py`](../../scripts/heartbeat_report.py) |
| Sender | [`.github/workflows/heartbeat.yml`](../../.github/workflows/heartbeat.yml) |
| Schedule | `12 0 * * *` (00:12 UTC), plus `workflow_dispatch` for a re-run while testing |
| Comment | one per UTC day, on the issue labelled `heartbeat`; the marker `<!-- heartbeat-day:YYYY-MM-DD -->` is what makes a re-run **edit** that comment instead of posting a second one |
| Day reported | **the day that just ended.** A digest composed mid-day would be a partial count wearing the word "today", and would need a caveat on every number |

Running it by hand:

```bash
# the same thing the workflow does, against the live sources (needs the Cloudflare credential for D1)
python3 scripts/heartbeat_report.py --fetch --out /tmp/heartbeat.md

# a day already collected, or a fixture: no network, no credential
python3 scripts/heartbeat_report.py --day 2026-10-16 --counters-json rows.json \
  --analytics analytics.json --funnel funnel.json --e4-json search_signals.json
```

## Panel 1 — who is calling

Reads `counters` rows with `scope='traffic'`, split into the four classes the worker classifies
every request into (`mcp`, `agent`, `crawler`, `pageview`) and the per-client buckets
`mcpclient:<name>`.

**The names are self-declared, and the panel says so in the comment itself.** A bucket is built
from MCP `initialize`'s `params.clientInfo.name` (or `.title`), falling back to the `User-Agent`,
lowercased, `[^a-z0-9._-]+` → `-`, trimmed to 32 characters and `unknown` when empty
(`workers/register-proxy-sw.js:6639`). So the panel answers *what name was claimed* — it is not an
identity, not a user count, and one agent with many names looks exactly like many agents sharing
one. `claude-code: 412` printed without that sentence would be a lie of emphasis, which is why a
test fails if the sentence is removed.

**Our own traffic is labelled and never counted as adoption.** `SELF_PRODUCED_NAMES` and
`SELF_PRODUCED_PREFIXES` in the composer are a reviewable parameter: the house prefix
`misakanet-` plus the bare names this repository's own tests and smoke paths declare. Those rows
are marked `self-produced (ours) — not adoption` and excluded from the **external, unclaimed**
number, which is the only number that could be evidence somebody outside called. A day whose named
calls are *all* ours says so in one sentence — that sentence is the single most valuable output
this digest has, because it is the one that stops an echo from reading as a pulse. Runtime names
(`node`, `curl-8.5.0`, `python-requests-2.31`, `unknown`) are labelled separately again: they are
external *and* unattributable, and calling them either "ours" or "callers" would be a guess.

## Panel 2 — what they asked

- **Top searches, rolling** — `/api/analytics`'s `top_searches`, which is `lesson_usage` rows with
  `event='search'` grouped by the query text. The window is whatever the endpoint uses (7 days at
  the time of writing), not the reported day, and the panel says so.
- **Generic strings are marked, not averaged in.** `top_searches` is a `GROUP BY` over whatever a
  caller sent, and the live top ten on 2026-10-16 carried `npm run build` (21 calls), `init` (12)
  and `start` (8) beside real topics. A count that blends them measures the blend. They stay
  visible with a `generic string — not a failure topic` note rather than being filtered out
  silently, because a hidden filter is the same dishonesty pointed the other way.
- **Declared intents** — `event='intent'` rows, usually empty. That is a reading of the store, not
  evidence that nobody had an intent, and the panel says which one it is.
- **Unanswered on the day** — `counters` rows with `scope='gap'`: searches that matched nothing
  (`workers/register-proxy-sw.js:3775`), with rows deleted once a lesson covers the query
  (`workers/register-proxy-sw.js:7028`). This is the demand the corpus failed to meet.
- **A prompt is not a query.** A `gap` bucket is `query.toLowerCase().trim()` with no length
  bound, which is exactly why `/api/analytics` withholds `knowledge_gaps` from anonymous callers
  (`workers/register-proxy-sw.js:7765`). This digest is a comment on a **public** issue, so only
  short, query-shaped text is repeated; anything newline-bearing, longer than 60 characters, or
  carrying a prompt marker renders as `<withheld: prompt-like text, not a query>`. Counts still
  include it — the miss is real even when the text is not printable. The full rows remain
  readable with the maintainer token.

## Panel 3 — whether it helped

**It is not measured, and the panel says that instead of implying otherwise.** `top_lessons` is
`lesson_usage` rows with `event='get_lesson'` — *how often a lesson was retrieved*. Fetched is not
fixed: nobody records whether the caller's problem went away. The panel prints retrieval counts,
states that no help number exists, and names the intended next step:

> **failure recurrence** — a normalized query that comes back on a later day is a signal the
> earlier answer did not stick.

That signal needs no identifier, no vote and no client change: the `gap` counter already stores
one row per normalized query per day, and `lesson_usage.query` carries the matched searches with
their `created_at`. It is **not implemented here**. The open item is a decision, not a blocker:
which series is authoritative (unanswered `gap` rows or matched searches), what normalization is
applied to compare two days, and what recurrence threshold is worth reporting. Until that lands,
the panel stays a retrieval count with the paragraph attached.

#### 2026-10-28 决定：复发率的三个决议，以及第一个数字

上面那段把复发率写成"三个未决问题（哪个序列权威 / 什么归一化 / 什么阈值）"。三个都有答案了，
依据是一次对着两张表实测（命令在下面）。

**① 权威序列 = `lesson_usage`（匹配到的检索），不是 `gap`。**

`gap`（未命中）看起来更贴题——"没答上来的查询又回来了"——但实测它算不出这个指标：

| | `gap`（ops 库） | `lesson_usage`（serving 库） |
|---|---|---|
| 行 / 去重查询 | 1,911 / 1,666 | 9,801 / 4,604 |
| 其中"查询形状"（12–120 字符、无换行） | 1,584 | 4,231 |
| **≥3 天复发** | 57，但 **48 个是粘贴的整段 prompt** | **79（1.9%）** |
| 复发里最典型的 | `"0"`（8 天 ×17 次）、`"x"`、`"[]"`、`"run"` | `pip install timeout`（**46 天**）、`database is locked`（28）、`npm run build`（22）、`Error response from daemon: exit code 137`（21） |

两边一对比结论很硬：`gap` 被客户端当垃圾桶用（整段上下文、字面量 `0`、`x`），去掉 blob 后剩下的
9 条里还有 6 条不是查询；`lesson_usage` 记的是**真的匹配到了课**的检索，正是"上一条答案没生效"能
被定义的population。所以复发率读 `lesson_usage`，`gap` 留作"从未被覆盖"的另一个指标。

**② 归一化 = 沿用 `toLowerCase().trim()`，外加一条形状谓词**：`12 ≤ length ≤ 120` 且不含换行。
不再做词形归一（复数/时态）——那会把 `pip install timeout` 和 `pip install timeouts` 合并，而它们是
两个不同症状的可能性大于同一个。

**③ 阈值 = 30 天内出现 ≥3 个不同日期**。当前落在阈值上的是 **79 条 / 4,231 = 1.9%**，所以它现在
应该是一张**可以逐条读完的清单**，不是一个百分比仪表盘。等它涨到读不完再谈告警。

**这个 KPI 现在能回答什么**：`pip install timeout` 在 46 个不同日期被搜到，说明这条课存在、被匹配到，
却仍然反复被问——要么答案没有前瞻性（只讲了镜像），要么用户在**预防**阶段就该拿到它而现在拿不到。
这正是里程碑 2（先查再动手）要回答的问题，也说明里程碑 1 的最后一环不是加埋点，而是**读已经有的**。

```bash
# ① gap 侧的污染
#    SELECT COUNT(*) FROM counters WHERE scope='gap' AND (LENGTH(bucket)>120 OR INSTR(bucket,char(10))>0)
# ② 复发率（SSOT 查询）
#    SELECT COUNT(*) FROM (SELECT query FROM lesson_usage
#      WHERE LENGTH(query) BETWEEN 12 AND 120 AND INSTR(query,char(10))=0
#      GROUP BY query HAVING COUNT(DISTINCT date(created_at))>=3)
# ③ 清单
#    SELECT query, COUNT(DISTINCT date(created_at)) d FROM lesson_usage
#      WHERE LENGTH(query) BETWEEN 12 AND 120 AND INSTR(query,char(10))=0
#      GROUP BY query ORDER BY d DESC
```

### Panel 3's vote reading — panel votes vs other votes (#3510)

Beside the retrieval counts, the panel prints the `helpful-source` counters for the **7 UTC days
ending on the reported day**: one table row per day with **panel votes** (the constant `dsh-web`
label the DSH panel posts), **other votes** (every other `bucket` in the scope), **retrievals**,
and **votes / retrievals**. A day with no counter row keeps its row and prints `0` — the worker
writes one row per source-tagged vote, so an absent row *is* a zero, which is the one place in
this digest where an empty read is a measurement rather than a broken store.

The denominator is stated as **retrievals** and the rate is named **votes over retrievals**, never
a "helpfulness" rate: a vote says a human judgment got recorded, not that the lesson fixed
anything. Both vote columns re-derive from the `counters` table alone
(`scope='helpful-source'`, `period=<day>`, `bucket` = the vote's `source` label), and the digest
names the source (`dsh-web`) so a reader knows which surface the panel column counts. `source` is
a **constant label** — the same string for every person, install and session — so the reading
groups by day and label only; no per-person and no per-session dimension exists or is introduced.
A vote that carried no `source` writes no row at all (the behaviour before 2026-10-16), so the
columns count **source-tagged** votes only.

The ratio's denominator comes from `lesson_usage` (`event='get_lesson'`, per day, over the same
window) rather than from `/api/analytics`'s `top_lessons`, which is capped at ten lessons and is
therefore not a total. That is one more D1 read with the credential this digest already holds — no
public route, no counter write, and no change to the withhold policy.

## A separate reading — how dense the `E4` rung is

`E4` is the top rung of the evidence ladder: a lesson retrieved by **two distinct clients**
(`COUNT(DISTINCT client_hint) >= 2`, the worker's `E4_MIN_DISTINCT_CLIENTS`). It is conferred by an
observation and cannot be typed into a lesson, and until this reading nobody had measured it against
the real table.

It is a section of its own, **not one of the three panels**, because it is a *stock* and the panels
are a *day's flow*: a cumulative number printed next to daily counts reads as part of them. One more
D1 query answers it, next to the counters query and with the same credential:

```sql
SELECT
  (SELECT COUNT(*) FROM search_signals) AS rows_total,
  (SELECT COUNT(*) FROM search_signals WHERE solved = 1) AS rows_solved,
  (SELECT COUNT(DISTINCT top_id) FROM search_signals) AS lessons_seen,
  (SELECT COUNT(*) FROM (
     SELECT top_id FROM search_signals
      WHERE client_hint IS NOT NULL AND client_hint <> ''
      GROUP BY top_id
     HAVING COUNT(DISTINCT client_hint) >= 2
   )) AS e4_lessons;
```

The three denominators are what make a `0` readable: `search_signals` rows, hit rows (`solved=1`),
and the distinct lessons those rows name. The rendered sentence is
`**E4 lessons: <n> of <lessons_seen>.**`, and when `n` is `0` the panel says so as a **finding about
the design** — the rung is empty because two distinct `client_hint`s are required and only a caller
that sends a `client_id` writes one, so the number under-counts by construction. That direction is
the point: a trust signal may be wrong by staying silent, but nothing written inside a lesson can
inflate it. **The `0` is never softened** into "no data yet": a real zero is the more interesting
answer, and a failed read is a different sentence entirely (rule 4 — the one place where confusing
the two would matter most).

The framing is [`product-evaluation-lens.md`](product-evaluation-lens.md)'s rule — **a dead signal is
evidence about the design, not a promotion problem** — so the panel reports the number and stops. It
does not suggest that more people should vote, or that callers should send a `client_id`: the fix for
an empty rung is a better instrument or a different rung, and neither is a thing to ask of a reader who
came for a failure memory.

`tests/test_heartbeat_report.py` runs this exact SQL text against `sqlite3`, with the table created
from the worker's own `ensureSearchSignalsTable` DDL, so the selection semantics are pinned even
though the production table itself is reachable only from CI.

## Panel 4 — the pipeline (issues → lessons)

Added 2026-10-30, after a one-off pass over the backlog (`pipeline-funnel-2026-10-30.md`) had to be
computed **by hand** to answer a question the digest could not: is anything moving? The numbers that
answer it are not labels — a "converted" issue is known only from a lesson's provenance, and "open for
31 days" is a fact about a timestamp — so the panel is computed by `scripts/pipeline_status.py` and
rendered as one table:

| | created (7d) | converted | open now (oldest) |
|---|---|---|---|
| `[Question]` | new questions | how many are cited by a lesson | open + age, never-commented count |
| `[Intake]` | new reports | how many became lessons | open + age, auto-rejected count |
| `[Lesson]` | new submissions | how many became lessons | open + age |
| our own issues | new | — (they are the repo's work, not the corpus's) | open + age, never-commented count |

Plus four lines: **issue → lesson** median/p90 days (over lessons created in the last 30 days),
**questions answered** (all-time, `answered` label), **auto-rejected salvage** (how many rejected
reports still became lessons), and the window's own caveat.

**What it refuses to claim.** `converted` is provenance — a lesson that names the issue through the
shapes `scripts/intake_receipt.py` already owns (`#N`, `intake-N`, an issue URL) — and a number
appearing in a lesson's prose is not a citation. `answered` is the label, not a claim that the answer
helped. Both sentences are in the panel, and `tests/test_pipeline_status.py` fails if the caveat is
removed.

**The read is a network call to the GitHub issues API** (paginated, `GITHUB_TOKEN`/`GH_TOKEN`). It is
part of `--fetch`, so the scheduled run reads it; an offline render (`--issues-json`) takes a saved
payload instead. A failed read follows [Rule 4](#rule-4--a-day-with-no-data-says-so): the panel prints
`Could not be read for this run — <reason>`, never four zeros.

## Rule 4 — a day with no data says so

A source that could not be read and a source that was read and held nothing are two different
answers, and neither is `0`:

| state | how it renders |
|---|---|
| could not be read (`None`) | `⚠️ … could not be read for YYYY-MM-DD (reason). This is not a zero.` |
| read, empty (`[]`) | `… recorded no rows for that day` / `no traffic-class rows for …` |
| read, non-empty | the counts, with the day named |

The same rule is applied to the funnel: a day missing from `/api/funnel`'s window is reported as
absent, not as zero. The rule is the one `/api/funnel` already applies to its own `visit`
denominator ("a counter that cannot be read and a counter that is genuinely empty are two
answers", `workers/register-proxy-sw.js`), and the composer keeps the distinction at the source:
`traffic_class_counts(None, day) is None` but `traffic_class_counts([], day) == {}`.

## Sources, credentials, and what is deliberately not here

| source | what it is | its limit |
|---|---|---|
| `counters` (D1) | traffic classes, `mcpclient:` buckets, `gap` buckets, `helpful-source` vote buckets | the client dimension exists only where a client sends `initialize`; `gap` text is caller-supplied; a vote with no `source` writes no `helpful-source` row, so those columns are source-tagged votes only |
| `GET /api/analytics` | rolling `lesson_usage` aggregates | `knowledge_gaps` and `mcpClients` are withheld there on purpose — read from D1 instead, without changing that policy |
| `search_signals` (D1) | rows, hits, distinct lessons, and lessons at the `E4` rung | a lesson is counted only when **two distinct** `client_hint`s retrieved it, and `client_hint` exists only for a caller that sent a `client_id` — so the number is a floor by construction |
| `lesson_usage` (D1) | per-day retrievals (`event='get_lesson'`) — the vote ratio's denominator | every retrieval writes one row, so an absent day is zero retrievals; the API's `top_lessons` is capped at ten and is not used as a total |
| `GET /api/funnel` | `visit` / `register` / `authorize` / `pair` / `search` | `visit` counts only pageviews *this* worker serves (`/` and `/search/` come from `misakanet-web`); `register` counts **nodes**, and a client that omits `client_id` creates one per call, so it is neither people nor agents; `drop_off_rate` divides two different units and is deliberately unclamped, so the digest omits it and quotes its value rather than printing it as a rate |

- **No new endpoint, no change to what any counter records, no change to the withhold policy.**
  The composer is a reader.
- **`env.MCP_TOKEN` appears in no workflow.** The D1 read uses the Cloudflare credential the
  counters report already uses (`.github/workflows/d1-counters-report.yml`), and the job sits in
  the `automation` environment — reviewer-free, D1-scoped, and branch-restricted to `main`. The
  deploy-capable `release` credential is not used here: a cron behind a required reviewer does not
  become safer, it stops (`docs/maintainer/credentials-and-environments.md` §3).
- **A failed read does not fail the job.** The digest reports it in the comment and the step emits
  a `::warning::` annotation; turning it into a red run would give the owner a second notification
  that asks for an action, which is the thing a heartbeat must not do.
- **The four honesty rules are tested** in `tests/test_heartbeat_report.py`, each against a
  deliberately unprotected copy of the composer so the failure has been seen rather than assumed.
