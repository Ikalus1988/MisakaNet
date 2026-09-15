# 评审评估（2026-09-15）：一份"全部基于实测读代码"的外部 README 评审

> 触发：外部评审给出 9 条结论（2×🔴 事实性错误、3×🟠 中等、4×🟡 次要、5 条 ✅），
> 开头声明"以下结论全部基于实测读代码，没读的不下判断"。
>
> **结论先说：9 条里没有一条作为"对当前仓库的事实陈述"完全成立。**
> 1 条方向成立（"零依赖"表述需要限定词）、3 条部分成立（domain 词表混乱、静态计数、
> provenance 不可核验）、5 条不成立或指错了对象。
> 但这份评审真正的价值不在结论，而在**它踩中了四个"会让读者读到过期状态"的表面**——
> 其中两个当时**确实是坏的**，而且**我们自己的门禁全绿**（§3）。那才是这轮真正要修的东西。

---

## 1. 逐条核对

| # | 评审的说法 | 实测（HEAD `245bf6a73`） | 判定 |
|---|---|---|---|
| 1 | "README 明确说 searches **249** indexed failure-recovery lessons"，而实测 398 个 `.md`，差距 60% | README 全文**没有 249**。README:13 写 `393+ failure lessons`，`data/lessons.json` = **393** 条，`sync_lesson_count.py --check` 绿。249 确实存在于**别处**：gitignored、停在 2026-07-14 的生成物 `STATUS.md`（`\| 📚 Lessons \| 249 篇 \|`）、`docs/trust-semantics.md:52`（词表示例 ✅/❌）、`lessons/contrib/ssot-marker-replacement-runs-once.md:47`（历史漂移对照表，其副本进了 `data/lessons.json` 的 `preview`）。398 是 `lessons/**/*.md` 全量（含 templates、根目录散落文件、未索引的翻译），与"indexed"不是同一个量 | **不成立**（对象错；但 249 曾是某个文件里的真数） |
| 2 | "Zero-dependency 是误导：必须 `pip install misakanet-core`；`misakanet` 在 PyPI 上根本不存在" | 依赖为真（`requirements.txt:3`、`pyproject.toml:13` 硬钉 `misakanet-core>=2.7.0`）。但：`misakanet-core` 在 PyPI 上 `requires_dist = None`——**它自己就是零依赖**，summary 原文 *"The zero-dependency core protocol engine"*；`misakanet` 在 PyPI 上**存在**且已到 2.30.0 | **部分成立**（"零依赖"需限定词，但两条事实断言都错） |
| 3 | domain 体系混乱：43 "archive"、16 "ops"、9/10 个加不加引号的 devops；`_SYNONYM_MAP` 是硬编码补丁 | 混乱为真：376 篇有 `domain:`，**68 种原始写法 / 61 种归一写法**（devops 75、contrib 40、fanuc 36、ops 24…），24 篇给 domain 加了引号；`lesson_gate.py:202-220` 的白名单是**自放宽**的（把 `core/contrib/en` 里已用过的域名全并进来），`queue_lesson.py:350` 的 `--domain` 是自由文本（`--status` 反而有 choices）。但评审的数字逐字来自 **gitignored 的 `.pnpm-store/v11/tmp/_tmp_*/lessons` 快照**（2026-08-26）；`_SYNONYM_MAP` 不在 `search/engine.py`（无此路径），而在 `misakanet/search/engine.py:32`，且它是**检索词扩展**、没有一条是 domain 标签 | **部分成立**（结论对、证据错位） |
| 4 | `mcp_server.py` 有工具无实现：`handle_submit_usage` 永远返回 `logged` | 仓库根**从来没有** `mcp_server.py`（`git log --all --diff-filter=A` 为空）。部署面是 `workers/register-proxy-sw.js`（实测 `tools/list` = **7** 个工具，**不含** `submit_usage`）；本地 stdio 是 **9** 个工具。`handle_submit_usage` 现在真的 POST 到 `/api/helpful` 与 `/api/feedback`（抓到实际出站请求），返回值有 `submitted` / `error` / `logged` 三种可区分状态；`scripts/usage_meter.py` 真实存在（8863 B）并被 `status.py` 调用；工具描述自带 `[Experimental]`。评审引用的是 **2026-08-29 修复前**的代码与 **2026-07-29** 的 4 工具状态 | **不成立**（引用了历史代码） |
| 5 | 产品定位在"工具"与"竞赛平台"之间摇摆 | README:210 起是工具定位，:407 起是网络/贡献者定位，:332 有明确的 ❌/✅ 边界表（"A general-purpose memory system" ❌ / "Failure-recovery knowledge layer" ✅）。双受众是**设计**，不是事故 | **不成立**（判断类，非事实错误） |
| 6 | "Stats 数字没有刷新机制：README 硬编码 Registered Nodes — 60 assigned IDs" | README（en/zh-CN/ja）**没有** node 计数，也没有 `60`。同类问题确实存在，但在别处：`README.zh-CN.md:11` 硬编码 `nodes-59` badge（同一行还硬编码 `lessons-358`）、`STATUS.md:14` 与 `docs/llms.txt:21` 的 `52+`；而 `sync_lesson_count.py` 的 docstring 早就把节点数写成 *"Deliberately NOT managed"*。线上真值是 `/api/counter` 驱动的（`data/counter.json` = 72） | **部分成立**（模式真、对象错） |
| 7 | 表格设计不一致（emoji 表 / ASCII art / 纯文本混用） | 纯主观，未评 | **未评** |
| 8 | "lessons come from real debug sessions" 无法验证：没有 lesson 标 `source`，只有 `dco-auto-fix-workflow.md` 标了 `source: codewhale` | 前提错：**338/440** 篇有 `source:` 键；`source: codewhale` 出现在 **8** 个文件；**397/440** 篇有 `provenance:` 块（`docs/provenance.md` 是它的规格）。但结论方向对：那是脚本批量回填的同质占位值——`evidence: post-publication` ×384、`source: community` ×289、`merged_at: 2026-08-23` ×365，最大的真实值是 `unknown` ×68。README:496 的四个渠道**无法逐条核验** | **部分成立**（结论可辩护、前提错） |
| 9 | Agent Nodes 表把 `ci` 和 `zeroknowledge0x` 列为不同 agent，其实是同一人 | 仓库里**没有**这样一张表（en/zh-CN/ja README、CHANGELOG、`docs/index.html`、history 都查过），git 全历史 95 个身份里**没有 `ci`**。旁边倒有一个真缺陷：`zeroknowledge0x` 一人 **3 种名字 / 2 个邮箱**（`rkhandrianto17@gmail.com` 同时挂在 "Muhammad Rakha Qushayyi Andrianto" 名下），且没有 `.mailmap` | **不成立**（对象不存在） |

---

## 2. 四条硬错来自同一个地方：**读到的不是 HEAD**

| 评审的结论 | 它实际读到的东西 |
|---|---|
| "README 说 249" | 最可能是 `STATUS.md`（gitignored 生成物，停在 2026-07-14，`\| 📚 Lessons \| 249 篇 \|`）；同一数字也在 `docs/trust-semantics.md:52` 的✅示例、讲历史漂移的 lesson（`ssot-marker-replacement-runs-once.md:47`）以及 `data/lessons.json` 对它俩的复制里 |
| "398 个 .md 没有统一质量门槛" | 文件数包含 `lessons/templates/`、根目录散落文件、`hi/id/ru/tr/vi` 五个翻译目录、29 篇未索引的 `en/`。**索引口径**是 393 = contrib 349 + en 32 + core 10 + user-rescue 2；README 用的正是 "indexed" 这个词 |
| "根目录 mcp_server.py 是 stub" | 2026-08-29 之前的 `misakanet/server/handlers/submit.py`（`cee58141f^`），以及 2026-07-29 的 `scripts/mcp_server.py`（4 工具）。**根目录那个文件从未存在** |
| "43 archive / 16 ops / 12 fanuc / 6 development" | gitignored 的 `.pnpm-store/v11/tmp/_tmp_*/lessons`（2026-08-26）：`lessons/_archive/` 已于 `91c8ae379`（2026-09-05）删除 |

**这四条里有一条不是评审的错，是我们的错**：`misakanet/server/tools.py:181-183` 至今写着
`"Side effects: currently returns a local placeholder report only."`——修复提交（`cee58141f`）没有同步
工具 schema，于是**任何读 schema 的人都会得出"这是 stub"的结论**。评审就是这么错的（§4 第 1 条）。

---

## 3. 已修（本轮提交）

1. **README:275 的活漂移**：`385+ **verified failure-recovery lessons**` → `393+ **indexed failure-recovery lessons**`。
   两处都错：计数早已是 393（`data/lessons.json`），且 `verified` 是 `docs/trust-semantics.md` 明令
   只能用于"人工核对过原文"的词。
2. **把它注册进 SSOT**（`scripts/sync_lesson_count.py`）：Glama 段此前**不受任何门禁管辖**，
   所以能静默漂移；同一个提交还把 `JOIN.md` 的 Version-Info 块（`384+ lessons`）一并纳入。
3. **补上门禁的洞**：`tests/test_lesson_count_ssot.py` 的 `FORBIDDEN_TRUST_CLAIM` 原本是
   `verified (failure|debugging) lessons?`——**连字符形式 `verified failure-recovery lessons` 匹配不到**，
   所以那句违反词表的句子能在这道测试下**全绿通过**。已收口为 `(?:-recovery)?`。
   回灌验证：把上面两处漂移原样放回，`sync_lesson_count.py --check` 精确报出
   `README.md:275` 与 `JOIN.md:186` 并 `exit 1`。
4. **`docs/llms.txt` + `docs/.well-known/llms.txt:28`**：`queries that return verified lessons` → `indexed`
   （同一词表，面向 agent 的表面）。
5. **`JOIN.md` 的版本行**：`v2.29.0` → `v2.30.0`（`align_versions.py --registry 2.30.0`）。
   版本门禁只约束"文档不得**超前**"，落后是允许的，所以它安静地落后了两个版本。
6. handoff P0.2：`package.json` 的 `files` 加入 `.codex-plugin/**`（tarball 10 → 14 文件、37.3 kB → 1.0 MB，
   Codex 插件清单引用的 3 个资产随包发出）。

---

## 4. 待决定（评审顺手指出的真问题，本轮未改）

1. **`misakanet/server/tools.py:181-183` 的过期描述**（"returns a local placeholder report only"）。
   这是 agent 面的事实错误：它**低估**了真实副作用（会写 `helpful:<id>` KV）。
   修复提交没带 schema 一起改，`git blame` 显示这两行仍是修复前的文本。
2. **远端工具面在文档里不一致**：`docs/integrations/mcp-remote.md:268,272` 把**未部署**的
   `submit_usage` / `usage_status` 列为远端可用工具；`docs/mcp.md:70-73` 只列 3 个远端工具（实际 7）。
   只有 README 与 `AGENTS.md` §3.2 是准的。`docs/mcp-eval-20260903.md:150` 早已记录了这个分叉。
3. **中文本地化的静态 badge**：`README.zh-CN.md:11` 的 `nodes-59` 与 `lessons-358`，无任何机制刷新。
4. **domain 词表治理**：68 种写法；门禁白名单自放宽（等于无约束）；`queue_lesson.py --domain`
   自由文本；`data/synonyms.json` 是 34 条同义词的**死副本**（没有任何代码读它）。
5. **provenance 的同质回填**：批量脚本写入的 `post-publication` ×384 / `community` ×289 让
   "渠道级"来源声明失去信息量——要么补更强的证据链，要么把 README:496 的措辞改弱。

---

## 5. 对评审 ✅ 项的复验（没白夸）

| 评审说 | 实测 |
|---|---|
| SAG-Lite / BM25 分层，SAG 不可用自动回退 | ✓ `misakanet/search/engine.py:1116-1139`，两种来源返回同形 dict |
| quota：新节点 5 次免费 | ✓ `scripts/usage_meter.py:25-26`（匿名 5/天、注册 20/天） |
| heal mode 四级级联签名提取 | ✓ `misakanet/cli/heal.py:77-108`（Level 1 traceback / 2 ERROR 标记 / 3 exit code / fallback 尾行） |
| L2 SQLite WAL 缓存 | ✓ `misakanet/search/engine.py:98` `PRAGMA journal_mode=WAL` |
| `_SYNONYM_MAP` 有效弥补标签混乱 | ✗ 位置错（应为 `misakanet/search/engine.py:32`），且它是**查询扩展**而非 domain 同义词——"弥补标签混乱"的因果不成立 |

---

## 6. 方法论（这才是要留下的一句）

> **"实测读代码"不等于"读对了版本"。** 这份评审的四条硬错，没有一条是凭空编的——
> 每一条都能在仓库里找到字面出处，只不过出处是 gitignored 快照、别人的示例文本、
> 修复前的代码、以及一份历史报告。

对我们的直接含义：**凡是"数字 / 工具面 / 词表"这类会被外部读者当作事实引用的表面，
要么进 SSOT 与测试，要么在文档里标明快照日期**——二者都没有的，就是这次被抓到的那种表面。
本轮的第 1–3 项（注册 SSOT + 收口词表正则 + 版本对齐）就是往这个方向补。
