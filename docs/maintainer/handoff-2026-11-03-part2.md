# Handoff — 2026-11-03-part2（第 27 卷，承接 `handoff-2026-11-03.md`）

> 上一卷：`docs/maintainer/handoff-2026-11-03.md`　·　下一卷：（本文件为最新）
>
> 上一卷 §5 的前两条做完了，代价是先发现**其中两条 issue 描述的东西早就修好了**：真正缺的不是修复，
> 而是**让那种失败形状能被看见**。这一轮三件事的共同判据只有一句：**颜色和状态必须携带它们声称携带的信息**。

## 1. 这一轮定下来的判断（是决定，别再重新论证）

1. **「0 作业失败」是独立的一类失败，不是某个 workflow 的毛病。** GitHub 拒绝一个它解析不了的文件时，
   run 在创建任何 job 之前就结束——没有日志、没有 annotation，check-suite 的名字退回文件路径。
   #3232 / #2957 都是它；修文件的是 #3308（2026-10-16），**让这个形状能被看见**的是
   `scripts/automation_output_audit.py` 的新规则（#4377）。
2. **检测的窗口要跟它的用途一致。** 这条规则问的是「现在有没有东西被拒」，所以用自己的 **7 天**窗口，
   不是审计的 30 天。第一版 30 天把 2026-10-07 的旧事故又报了一遍，而那个事故早就修好了。
3. **采样必须写在报告里。** 一个窗口里有 400+ 条失败 run，只探 12 条；`examined 12 of 443 … sampled,
   not exhaustively probed` 写在表格里，因为「没看」不能读成「干净」。
4. **stdio 的 `me_inbox` 从来没有问对地方。** 它 GET 的 `/api/inbox` 在 worker 里**从来不存在**
   （`git log -S 'api/inbox' -- workers/` 为空），所以除本地队列外一切查询都答 `not_found`；
   hosted 对同一个 id 答的是 `unknown` + 理由（#3577）。修法不是造第二个契约，而是走
   `misakanet/remote.py` 调 hosted 的 `misakanet_me_inbox`（和 `me_events` 同一条路）。
5. **`pr-agent` 的颜色不再承诺「被评审过」。** `synchronize` 上 pr-agent 自己 `Skipping action` 然后
   exit 0（绿）；fork 的 `pull_request` run 拿不到 secret（红）。同一个未改动的 fork PR 当天三条 run
   红-绿-绿（#2972）。触发里删掉 `synchronize`，fork 显式 skip；重评走 `/review`。
6. **测试要 patch 代码真的用的接缝。** `test_me_inbox.py` 前两代分别 mock 了一个**不存在**的函数和一个
   **404** 的 URL，两代都绿着。现在的接缝是 `remote.call`。
7. **ruleset 的必需检查是 5 条，不是 4 条。** 第 5 条是 `test (windows-latest, 3.11)`（2026-11-01 起）。
   `docs/agents/repo-operations.md` 的「四项」这一轮改正了；`docs/ci-gates.md` 一直是对的。

## 2. 数字（本卷拍摄，判据同时给出）

| 项 | 值 | 怎么复核 |
|---|---|---|
| `main` | `9451de7df` | `git log --oneline -1` |
| 语料 | **800** 篇 | `python3 -c "import json;print(len(json.load(open('data/lessons.json'))))"` |
| 开放 issue | intake **173** / question **50** / 其他 **93** | `gh issue list --state open` 按标题前缀分组 |
| code scanning | open **0** / dismissed **155**（上一卷记 30，本卷是全量 `--paginate --slurp` 数，口径不同）（**11 条**是 2026-11-01 之后 dismiss 的；**4 条没有 dismissal 理由**：#324 / #323 `docs/_redirects`、#320、#49） | `gh api --paginate .../code-scanning/alerts?state=dismissed` |
| 7 天失败 run | **443**，探 **12**，**0** 个 0 作业 | `python3 scripts/automation_output_audit.py`（CI 里也在跑） |
| 本地 worker 测试 | **983 pass / 3 fail**（`agent-autostart-hook.test.mjs`，本机环境，与上一卷相同） | `node --test 'workers/**/*.test.mjs'` |
| 本地 Python | 4 个针对性批次 300+ 条断言全绿；唯一失败是**已知环境问题**（本机装的旧 wheel `2.48.0` vs `pyproject 3.5.0` 导致的 `serverInfo.version`） | 见 §4 第 6 条 |
| 生产 worker | 已部署 `7f67c861c`（`tools/list` 里 `me_inbox` 描述已是 8 位 FNV、无 `not_found`） | `curl .../mcp` + `tools/list` |

## 3. 悬着的账（按「谁卡住了」分组）

### 3.1 只有 owner 能决定

* **11-14 的 `strict` 切换**：`MISAKANET_CLIENT_ID_PROOF` 由空串改 `strict`，撤掉 grace 措辞，验
  `client_id_proof_required`。已排提醒（`schedule-1440dd0b…`）。
* **`verify` 字段回填的模型预算**：约 350 篇需要模型起草（若用 Workers AI 则要 `CLOUDFLARE_API_TOKEN`）。
* **Glama 的 relevance 权重**（0.60）。
* **F3 worker 拆分**：缺的是方案而不是补丁。

### 3.2 门禁看不见的洞

本卷清了两条（#3232 / #2957 的「0 作业失败」形状有了检测；#3577 的跨传输回执与 #2972 的颜色）。
仍开：

* **#2972 的残留**：一条「这次运行**真的**调用过模型」的运行期断言。静态门禁做不到——可行做法是读
  job 日志里的 `Reviewing PR`，但仓内没有消费运行期日志的机制。模型端超时造成的红（PR #4377 的
  `pr-agent`：`APITimeoutError` ×2 → `Failed to review PR`，跑满 15 分钟）仍需人读日志。
* **dismissed 告警里有 4 条没有理由**（`#324` / `#323` `docs/_redirects`、`#320`、`#49`）。上一卷
  §1.5 的规矩是「可以 dismiss，但必须换一条能自己失败的检查，且理由写进 comment」。这 4 条只有
  `dismissed_reason`、没有 comment——不是本卷造成的，但按规矩该补或该重开。
* **`#4052`**（搜索偶发 35–62s）本卷仍未量。

### 3.3 已知但有意留着

* **三个裸 `npx wrangler`**（`cf-diagnostics` / `d1-bootstrap` / `publish-dataset`）。
* **`/api/helpful` 的读-改-写**（上一卷 §1 第 3 条）。
* **`#3323`** Glama listing 与实发工具不一致。
* **产品设计三条**（`#3539` / `#3541` / `#3543`）。

### 3.4 语料侧

* **173 条 intake**：绝大多数缺 `## Root Cause`；模型起草 + 人终审仍是唯一可行路径。
* **50 条 question**：答复即回执，不需要 PR。
* **`#2957` 的 508 条历史 push run** 仍留在 Actions 历史里——那是数据，不修。

## 4. 可复用的判据（比结论更值钱，下轮直接用）

1. **「本地绿」里最常见的假绿是 mock 了不存在的接缝。** 同一个文件里两次（`_query_d1` 从未存在；
   `urlopen` 打一个 404 的路由）。判据：`grep` 一下被 patch 的名字/URL 在生产代码里是否真的存在。
2. **一个形状修好 ≠ 这类形状能被看见。** #3308 修了两个文件，但没有任何东西会注意到「0 作业失败」再次
   发生。收单前问一句：如果它明天以另一种原因复发，谁会发现？
3. **只读 API 的 `status=` 过滤器决定样本有没有意义。** 不分页过滤时，100 条 run 只覆盖约 3 天
   （本仓每天约 35 条失败 run）。
4. **窗口是判据的一部分。** 问「现在坏没坏」的规则用 30 天窗口，会把已修好的事故算成当前故障。
5. **测一个 `if:` 要真的求值它**（`tests/test_workflow_author_association.py` 的做法）；字符串包含检查
   会放过「守卫写在注释里」的那类改动。
6. **本机全量 pytest 不可用，别拿它当判据。** `tests/` 收集要 2 分钟、跑起来约 6s/条（本机环境），
   而且三个 `mcp` 相关模块装的是旧版（`requirements: mcp>=2.3.0`，本机 1.28.1）。可用的做法是
   **按改动面挑批次**，全量交给 CI 矩阵。
7. **部署是异步且可能需要环境审批。** `deploy-worker.yml` 的 `release` 环境要 owner 批准
   （`pending_deployments` API）；批准后要**回头验线上**（本卷用 `tools/list` 验描述、用 `handle_request`
   验端到端）。

## 5. 下一轮入口（按优先级，逐条可独立开工）

1. **`#4052` 搜索偶发 35–62s**：先量再改。`scripts/bench_search_latency.py` 是唯一测量入口。
2. **173 条 intake 的根因补写**：模型起草 + 人终审；表单侧不用再改。
3. **50 条 question 的答复**：不需要 PR，答复即回执。
4. **11-14 strict 切换**：到点执行 §3.1 第一条。
5. **4 条无理由的 dismissal**：补理由或重开，并指向能自己失败的检查（上一卷 §1.5）。
6. **`#2972` 残留**：一条「真的调过模型」的运行期断言，或至少把「超时红」与「代码红」在报告里分开。

## 6. 本卷没有做的事（免得下轮误以为已覆盖）

* **没有**动 `#4052`。
* **没有**写 intake 根因、**没有**答 question。
* **没有**把 `/api/helpful` 迁到原子计数。
* **没有**做 `verify` 字段的模型回填。
* **没有**修 §3.3 的三个裸 `npx wrangler`。
* **没有**读 job 日志做「真的调过模型」的运行期断言。

## 9. 补记（2026-11-03 16:00，本卷合并后两小时）

§3.2 与 §6 写「`#4052` 本卷仍未量」——这一条在本卷合并后又被推进了一次，补记在此，**以本节为准**：

* **量了**：20 次连续 `tools/call`（`pip install timeout`，top=2）——`p50 3.17s`、`max 10.87s`（冷的第一次）、
  0 次 ≥30s、20/20 `source=worker-bm25`。尾巴是偶发的，当天没复现。
* **插桩了**（#4384、#4386，均已合并 + 已部署并验证）：`search_signals.latency_ms` 现在真的有值；
  `GET /api/search-signals/stats` 返回 `latency` 直方图（桶，不是 p95，因为这个分布是双峰的）；
  `scripts/bench_search_latency.py --remote` 量客户端视角并把冷启动单列成 `cold_ms`。
* **根因仍未定位**，issue 保持打开。下一次尾巴出现时，看 `latency.s_30_60` / `gt_60s` 与 `servedBy`、
  `builtAt`、`lastRefresh`，就能区分「冷 isolate 的索引加载」「D1/KV 抖动」「边缘节点」三种候选。

### 一条可复用的判据：列里有值 ≠ 有测量

旧绑定是 `Number.isFinite(Number(latencyMs)) ? Number(latencyMs) : null`，而 **`Number(null) === 0` 且
`Number.isFinite(0) === true`**——于是 2026-09-19 到 2026-11-03 的每一行都写着「0 毫秒」。第一次读直方图时，
它看起来是「4564 次检索，全都 <1s，最大 0ms」，也就是**「一切都很快」**，而这正是 #4052 那个窗口里最不该说的话。

判据：**一个字段第一次被真正写入时，先看它的「空」长什么样**——是 `NULL`、是 `0`、还是上一版留下的默认值。
这次三样同时存在，唯一的办法是把它们分开读（`latency_ms > 0`），并让写入端不再制造假的 0。
