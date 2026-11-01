# Handoff — 2026-11-01（第 25 卷，承接 `handoff-2026-11-01-part2.md`）

> 上一卷：`docs/maintainer/handoff-2026-11-01-part2.md`　·　下一卷：（本文件为最新）
>
> 本卷只记一件事：**第二轮审计报告到货，我逐条核了一遍**——哪些是真的、哪些被高估了、
> 哪些需要 owner 决定。收口状态在上一卷 §1，这里不重复。

## 1. 报告里被**高估**的两条（下次别再照抄）

### F1（报为"高"）不是"零测试证据可合入"

报告说 `pr-checks.yml:389` 的 pytest 被 `scope == 'full'` 挡住，所以改门禁的 PR 可以无测试合入。
**不成立**：`ci-cross-platform.yml` 对**每个** `pull_request` 都跑 `pytest tests/`，没有 scope 条件也没有
path filter，而 `test (ubuntu-latest, 3.11)` 与 `test (windows-latest, 3.11)` 是 **required** context。
真正错的是**那句话**：`pr-checks` 在 ci-only 上跳过自己的 pytest 后打印
「✅ CI-only gates passed. Ready for merge.」——读起来像"这个 job 验过一切"，审计大概就是这么复报的。
已改（`#4302`）：verdict 现在点名测试证据在 matrix 那边，跳过那一步也写明了理由（那一步的独有价值是
`--cov=misakanet --cov-fail-under=20`，而 lessons-only / ci-only / js-deps 动不了 Python 覆盖率）。

### F4 的措辞不准，但底下有个真问题

"每次查询仍逐文件 `read_text`"——**不是**：`_load_docs_cached` 走 L2 sqlite `file_cache`（按 `mtime,size`
比对），只有变动的文件才重新解析（`misakanet/search/engine.py:156-200`）。
真的是**每个文件每次 `stat()`**（765 个），以及 L1 命中前仍要先过这一轮。所以 F4 的正确定义是
"每次搜索有 765 次 `stat` 的固定开销"，修法是**按 lessons 目录的 mtime 缓存文件清单**，不是"再加一层 doc 缓存"。

## 2. 报告里**核实为真**的（已修 / 已记录）

- **F12**（四处鉴权口径）：三处不对（`CONTRIBUTING.md` 的"lifts the per-IP read cap"、worker 两处
  "5 free reads/day per IP"），`README.md` 那句 "anonymous and unlimited" **本来就是对的**（policy 是
  per-address burst window、无日配额）。三处已改（`#4302`）。
- **F13**（旗舰数字）：三处全真。`trust-semantics.md` 改用生成块里的数字、不再在正文手抄；
  `ARCHITECTURE.md` 69 → **88**（带日期与"谁拥有这个清单"）；`CLAUDE.md` 从 3 个工具补到 8 个托管工具 +
  两个 surface 的差异说明（`#4302`）。
- **F16**：门禁确实只到 F821/F811/F841；`CONTRIBUTING.md` 的"ruff 零告警"确实没东西在守。已改口径。
  **但报告给的 6,498 条复现不出来**：今天 ruff 0.17.3 只 `E501` 是 **5,575**，`E,I,N,UP` 合计 6,095。
  报数字要带命令与版本。
- **F15 / F11 / F3 / F17**：核实为真。F15（`data/lessons.json` 与 `docs/data/lessons.json` 字节相同）、
  F11（`pre-commit run` 不出现在任何 workflow）、F3（worker 10,692 行）、F17（`cli/typo.py` 两处
  `except Exception: pass`，已收窄为 `OSError` / `UnicodeDecodeError`）。
- **Q3**（拆分是否受构建链限制）：**不受限**——`workers/wrangler.toml` 的 `main = "register-proxy-entry.js"`，
  entry 合法 import 实现模块。所以 F3 可做，但那是 10.7k 行、服务生产搜索的文件，要的是方案不是顺手改。

## 3. 需要 owner 定的三件事（维护者做不了）

1. **Q2：`scripts/` 是投资还是债务？** 它决定 F5（coverage `omit = ["scripts/*"]`）与 F9（`--cov-fail-under=20`）
   是"记录在案的取舍"还是"该还的债"。目前的口径是取舍，写在 `pyproject.toml` 的注释里。
2. **Q7：34 个 cron 里哪些是哨兵、哪些只是负载？** 答案决定 F10（88 个 workflow）能砍多少。
3. **增长侧三件**（我一直没动，仍在等决定）：Glama listing 文案加 GitHub、telemetry hook、25–35 篇改
   `domain=github`。立场不变：文案是定位、出站调用是隐私契约、词表迁移要过 bench——都不是维护者能自决的。

   **本条有一个新事实（2026-11-01 晚）**：Glama 的服务器页当天重扫了，**TDQS 4.2 → 4.4**（`Scored 2026-11-01
   15:25 across 11 tools`），Behavior 从"没有注解可引"变成 **5/5**（"annotations already declare read-only,
   idempotent, open-world, non-destructive"）——就是 `#4284` 那 11 个工具的注解被看见了。**Disambiguation 仍
   3/5**：`search` / `memory_context` / `preflight` 三个检索形状的工具从不说明"该用哪个而不是哪个"，
   这是下一个具体可做的项（写文案，不需要决定）。榜单侧仍 **#13 / 51.2**（页脚 `Updated 2026-10-26`，周重建）；
   0.60 那个 relevance 乘数没动，原因见 §3 正文。里程碑与这篇推荐已写成博客：
   `Ikalus1988/Ikalus1988.github.io` 的 `cases/ranked-13th-of-2074.html`。

## 3.5 两个"该由谁决定"的问题，按第一性原理量出来是数据题

owner 说这两条他回答不了、要我用第一性原理判断。做法是量，不是表态。

**Q2 `scripts/` 是投资还是债务？** 量 195 个脚本各自被谁引用（workflow / test / doc / 另一个脚本）：
**被引用不到的有 2 个，另有 1 个重复孪生**——`create_issue.py`（硬编码一条早已办完的 issue 正文）、
`retrieval_noise_bench.py`（`retrieval_noisebench.py` 的旧孪生，测试 imports 的是后者）、
`lesson_reuse_agent.py`（252 行，唯一提及它在某篇 2026 课程的正文里）。结论：**资产 + 三条尾巴**，删掉
（`#4311`，470 行）。`pyproject.toml` 的 `omit = ["scripts/*"]` 是**记录在案的取舍**（这些是 CI 胶水，
由调用它的 workflow 练着），代价正是"够不到的脚本 CI 看不见"，所以尾巴要手动剪。

**Q7 34 个 cron 哪些是哨兵？** 量 35 个带 `schedule:` 的 workflow 的**产出形态**（issue / commit / 判定）
与**触发情况**（按 event 查，不按 run list 抽样）：

- **生产者**：update-lessons、sync-d1、build-feed、update-badges、update-smithery-badge、auto-sync-prs、
  arch-review、nightly-mirror-consistency、d1-backup、install-smoke、misakanet-setup-ci。
- **哨兵**：site-health（10-30 抓到 `/register/` 丢 `node_name` 标记，红了两天后自愈——真的在看）、
  approval-watch、heartbeat、question-autopilot、registry-drift-watch、dependency-vuln-audit、
  provenance-gate、deploy-freshness、intake-kind-audit、intake-salvage-digest、stale、
  check-documented-gates、workers-builds-watch（CF 构建守望）、codeql、dsh-client-e2e、ttfb、
  gate-mutation-audit、guarded-repository、field-report-schema、external-asset-integrity、
  claim-enforcer、pr-audit-watch。
- **纯负载：0 个。** 两个"看起来死了"的都是抽样假象——`workers-builds-watch` 最近 100 次里 99 次是
  `check_suite` 跳过事件，它的**定时**运行（GitHub 对 `*/30` 节流成约 3 小时）是绿的；
  `decision-queue-digest` 只是 10-28 建成、还没到第一个周一 09:23。**"从 run list 抽样下结论"正是
  审计 F1 犯的错，这次没犯。**

真正的发现是第三条：**`sync-question-answers` 这个生产者已经不生产了**——`permissions: contents: read`
却调用 `gh issue edit --add-label`，403 让回填步退出 1，而**同步是下一步**，所以自 10-28 起答案就没进过
D1。修好（`#4310`）+ 加了门禁 `tests/test_workflow_permissions_cover_writes.py`，它当场又抓出两个同类
（`pr-audit-watch` 用 `pull-requests: read` 去评论 fork PR；`shadow-branch` 用 `2>/dev/null || true`
偷偷给 PR 打标签而根本没申请 `pull-requests` 权限）。派发验证：9/9 打上 `answered`、同步 success、
答案已能从公开搜索取到（`faq-issue-3574`、`faq-issue-4090/4091/4092`）。

## 4. 下一轮入口

1. **F4 按正确定义做**（§1 第 2 条）：缓存 `canonical_lessons()` 的文件清单，别在读 L1 前先做 765 次 `stat`。
   先量 `scripts/bench_search_latency.py` 的当前值，再改，改完同一条命令复量。
2. **F3 要方案不要补丁**：`register-proxy-entry.js` 已经存在，拆分是把路由/处理器搬进 `workers/*.mjs`，
   每搬一块跑 `node --test 'workers/**/*.test.mjs'` + 部署后验一次搜索。
3. **F5/F7/F9/F11** 一起决定（它们都是"要不要把它变成门禁"），别一条一条改。
4. 上一卷 §4 的 2/3/4/5 条（`[Lesson]` 剩 10 条、融合之后改名/词表、11-14 strict、365 回填）状态未变。
