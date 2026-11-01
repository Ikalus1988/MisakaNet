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

## 4. 下一轮入口

1. **F4 按正确定义做**（§1 第 2 条）：缓存 `canonical_lessons()` 的文件清单，别在读 L1 前先做 765 次 `stat`。
   先量 `scripts/bench_search_latency.py` 的当前值，再改，改完同一条命令复量。
2. **F3 要方案不要补丁**：`register-proxy-entry.js` 已经存在，拆分是把路由/处理器搬进 `workers/*.mjs`，
   每搬一块跑 `node --test 'workers/**/*.test.mjs'` + 部署后验一次搜索。
3. **F5/F7/F9/F11** 一起决定（它们都是"要不要把它变成门禁"），别一条一条改。
4. 上一卷 §4 的 2/3/4/5 条（`[Lesson]` 剩 10 条、融合之后改名/词表、11-14 strict、365 回填）状态未变。
