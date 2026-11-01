# `[Lesson]` → 课程：落库 playbook（维护者）

> 适用：标题以 `[Lesson]` 开头、带 `pending-review` 的 intake（这些 issue 同时带 `lesson-submission`，
> 转换器按后者取队列）。目标：把一条 intake 变成 `lessons/contrib/<slug>.md` 并合进 `main`，
> 让下一个人**不必重新推导流程**——批 1（47 篇，`#4185`）与批 2（44/47 篇，`#4205`）走的就是这条路。
>
> **本文的每个数字都是从代码读出来的，行号跟着数字写在括号里。** 与代码不一致时以代码为准，并回来
> 改本文：一份被手抄过两遍的阈值，第二遍就是错的。分类与回执的规矩不在这里，在
> `docs/maintainer/intake-triage.md`（本文只补它 §2 那条 bullet 没写的"怎么做"）。

## 0. 先现读队列（不要信本文的数字）

```bash
gh issue list --repo Ikalus1988/MisakaNet --state open --label pending-review --limit 200 \
  --json number,title,labels --jq '.[] | select(.title|startswith("[Lesson]")) | "#\(.number) \(.title)"'
```

**2026-11-01 实测 24 条**。数字每天变，命令不变；`--limit 200` 必须写，默认只给 30 条，
队列会被截成"看起来只剩 30 条"。

## 1. 一条 intake 里有什么

| 位置 | 内容 | 转换器怎么用 |
|---|---|---|
| `**Kind:**` / `**Source:**` / `**Node:**` / `**Contributor:**` | 投稿元信息 | `Source` 进 `provenance.source`（`scripts/intake_lesson_to_file.py:219`, `:241`） |
| `**Domain:**` | **提交者自己填的** topic | 过 `DOMAIN_MAP` 再对词表，见 §5 |
| `**Title:**` | 标题 | 超 120 字符会被截断（`:194`） |
| `## Problem` / `## Root Cause` / `## Fix` / `## Verification` | 正文四段 | 三段（Problem/Root Cause/Fix）缺一段就**跳过该 issue**（`:197-198`） |
| `**Tags:**` | 逗号/空格分隔 | 没有就从标题派生 3 个（`:139-157`） |

> 正文末尾那段 Opire 横幅（`<details>…</details>`）由 `clean()` 整段剥掉（`scripts/intake_lesson_to_file.py:79`），
> 不用手工删。

2026-11-01 这 24 条实测：四个正文段、`**Tags:**`、`**Domain:**` **全部齐全**。所以当前队列的瓶颈
不是"缺字段"，是 §2.3 与 §4 的两条硬阈值。

## 2. 三分法：真课 / 重复 / 太薄

**实测 2026-11-01**：24 条里 **11 条**按转换器的输出没有撞任何硬阈值，**9 条**卡 400 字符正文地板，
**4 条**卡"命令名词表"（两组不重叠）。算法：用 gate 自己的两个函数
（`scripts/lesson_gate.py:426`, `:1018-1021` 的 400 字符判定、`:396-417` 的命令名判定）逐条跑，再抽 4 篇端到端跑
`lesson_gate.py` 核对（3 红 1 绿，与预测一致）。其余字段由转换器保证（§3）。

### 2.1 真课（默认）

判据只有一句：**读到这条报错的人能不能照它动手**。Fix 里要有命令/枚举/配置项之一，
Verification 里要有"看什么输出算好了"。gate 能校验结构（§4），校验不了这句话——这句话是人判的。

### 2.2 重复

- **整课重复**：标题（空白归一、小写）命中 `data/lessons.json` 里任一条 → 转换器打印
  `duplicate of lessons/<id>` 并跳过（`scripts/intake_lesson_to_file.py:249-256`, `:322-324`）。
  批 1 的 4 条重复就是这么发现的（`:18-20` 有实测记录）。处置：按重复关单 + 指向那篇课。
- **一条 intake 只能换一篇课**：新的课若 `provenance.issue` 里的编号已被别的课占用，gate 硬失败
  （`scripts/lesson_gate.py:684-714`, `:717-754`, `:1077-1088`）。这条规则存在的原因写在
  `:1060-1071`：两篇课关同一条 intake 会让回执指向错的那篇，而回执是报料者唯一能收到的东西。
- **近重复**（正文 Jaccard ≥ 0.55）只是 `[warn]`（`scripts/lesson_gate.py:836-839`, `:1090-1098`），
  不拦合并——但看到它就说明该合并、不该新增。
- **同 stem 的镜像**（`core/x.md` ↔ `en/x.md`）不算重复，两处检查都豁免（`:648-668` 与 `:730-737`）。

### 2.3 太薄：正文 < 400 字符

gate 对新文件要求正文 ≥ **400** 字符（`scripts/lesson_gate.py:426`, `:1018-1021`），而转换器自己的
地板是 **120**（`scripts/intake_lesson_to_file.py:207`，它的报错文案还写成 "the gate's 100-character
floor"，两头都不对）。**转换器过了不等于 gate 过**——这一条是批量落库最常撞的墙（9/24）。

三条出路，按优先级：

1. **把 issue 里已有的证据搬进正文**：版本号、报错原文、改前/改后的命令、复现条件。这是补，不是编。
2. **合并兄弟 intake**：`provenance.issue: "#4146 + #4157"`。解析器认一个值里的多个 `#N`
   （`scripts/lesson_gate.py:679-714`），一篇课换多条 intake 合法；反过来不合法。
   合并的对象要是同一个失败形状，不是同一个目录里的两条。
3. **补不出来就留在队列**，在 issue 上写清缺哪一段、谁欠的。**不要为过 400 加空话。**

**不许编 Verification**：这一节缺失时转换器写 `Not recorded by the submitter.`
（`scripts/intake_lesson_to_file.py:199-206`），这是唯一允许的占位；gate 另有假验证检测
（`scripts/lesson_gate.py:762-775`, `:1100-1105`），`echo … | wc -l` 一类会被点出来。

## 3. 转换

```bash
# 1) 取队列（REST 形状：脚本读的是 body 与 number 两个键）
gh issue list --repo Ikalus1988/MisakaNet --state open --label lesson-submission --limit 200 \
  --json number,title,body > /tmp/issues.json
# 2) 先干跑：读 notes 与 skip，确认没有任何一条被静默丢掉
python3 scripts/intake_lesson_to_file.py --issues-json /tmp/issues.json \
  --overrides /tmp/overrides.json --slugs /tmp/slugs.json
# 3) 真写
python3 scripts/intake_lesson_to_file.py --issues-json /tmp/issues.json \
  --overrides /tmp/overrides.json --slugs /tmp/slugs.json --write
```

- **`--overrides`** = `{"<issue number>": {"domain": "...", "title": "..."}}`，逐条修正
  （`scripts/intake_lesson_to_file.py:285`, `:167-193`）。它存在是因为提交者的 domain 是对**这条投稿**
  的猜测，不是词表：4 条 `packaging` 里有的其实是 iOS 签名（`mobile`），把 `packaging` 写进
  `DOMAIN_MAP` 会让另一条永远错。键是**字符串**（JSON object key）。
- **`--slugs`** = `{issue number: file stem}`，给回执/关单做配对（`:287-288`, `:342-344`）。
  **仓库里没有第二个读者**（`grep -rn slugs` 只命中它与页面生成器另一套 slug 逻辑）——写了它不等于
  回执已发，回执仍按 `docs/maintainer/intake-triage.md` §3 走。
- **`--fetch`** 需要 `GITHUB_TOKEN`/`GH_TOKEN`，`per_page` 夹到 100 且只读一页（`:259-270`）。
  队列过 100 条要自己分页，脚本不做。
- 转换器**不做**三件事（`:31-34`）：不关 issue、不跑门禁、不判断内容对不对。它写死
  `status: "published"` 与 `evidence_level: "E1"`（`:231-232`）——见 §10 第 1 条。

## 4. gate 的硬阈值（逐条有出处）

`python3 scripts/lesson_gate.py <file>`：任一非 `[warn]` 行 = 退出 1（`scripts/lesson_gate.py:1171-1182`）。
下表的"新课"列回答"这个发现拦不拦合并"。**`--existing`（或 CI 的 modified 列表）会把所有发现降级成
`[warn]`**（`:1145-1149`），那是批 1/2 那种元数据批量的通行证，**不是新课的**——新课不要加这个开关。

| 项 | 阈值 / 取值 | 出处 | 新课 |
|---|---|---|---|
| 必填 frontmatter | `title` `domain` `tags` `status`，加 `evidence_level`（或 `provenance.evidence`） | `scripts/lesson_gate.py:122-134` | 硬 |
| 标题 | 4–120 字符（`len()` 按字符，不按字节） | `:43-44`, `:137-145` | 硬 |
| tags | 1–10 个，每个 ≥2 字符，互不重复，必须是 list | `:45-46`, `:148-160` | 硬 |
| status | `published` / `draft` / `archived` / `active` / `stale` / `superseded` | `:40`, `:163-166` | 硬 |
| evidence_level | `E0`–`E4` | `:41`, `:169-172` | 硬 |
| 正文长度 | 新课 ≥ **400** 字符；任何文件 ≥ 100 | `:42`, `:426`, `:1013-1021` | 硬 |
| 四节 | `Problem` / `Root Cause` / `Solution`(`fix`) / `Verification`，二级或三级标题，别名按**子串**匹配 | `:420-436`, `:1022-1026` | 硬 |
| 结构化字段 | `summary_plain` ≤120、`trigger` ≤160、`verify` ≤200，单个字符串、单行 | `:462-463`, `:486-520`, `:1035-1037` | 硬 |
| 路径 | 必须在 `lessons/{core,contrib,en}/` 下 | `:49`, `:927-971` | 硬（仅新增时检查） |
| domain | 必须在 `data/domains.json` 的 `canonical` 里 | `:610-626`, `:1051-1056` | 硬 |
| 重复标题 | 跨 `core/contrib/en` 查重，同 stem 镜像豁免 | `:648-668`, `:1057` | 硬 |
| 一条 intake 一篇课 | `provenance.issue` 的编号已被别的课占用 | `:1077-1088` | 硬 |
| 命令名（public surface） | 语料从未出现过的命令名；出口是 `data/public-vocabulary.json` 的 `allowlist`（读工作区）或 frontmatter 的 `public_analogue:` | `:396-417`, `:341-346`, `:1107-1111` | 硬 |
| 近重复 | Jaccard ≥ 0.55，最多列 5 条 | `:839`, `:1090-1098` | 告警 |
| 假验证 | `Verification` 只有 `echo`/`wc -l`/`grep -c` 一类 | `:762-775`, `:1100-1105` | 告警 |

> **public surface 是第二个常撞的墙**（4/24）。实测 2026-11-01 被点到的词：`create-dirs`、
> `one-dir`、`pyinstaller`、`pyz`、`cdp-driven`、`douyin`——它按**词的形状**猜"这是命令"
> （反引号里有参数、shell 围栏里、或正文里同一 token 后跟单词 ≥3 次，`:250-312`），
> 所以产品名、flag、连字符短语都会中。处置二选一：确认是公开工具 → 加进
> `data/public-vocabulary.json` 的 `allowlist`（重建时保留，`scripts/export_public_vocabulary.py:97`）；
> 是内部/私有名字 → 改写并用 `public_analogue:` 声明公开等价物。**不要靠删句子绕过**。

## 5. domain 怎么选

- `data/domains.json` 的 `canonical` 有 **50** 个值（`data/domains.json:4-55`）。gate 只读这一半
  （`scripts/lesson_gate.py:610-626`）。
- 不在表里 = 硬失败（`:1051-1056`）。**aliases 不是合法值**：它只被
  `normalize_domains.py --write` 消费去改语料（`scripts/normalize_domains.py:88-98`），`--check` 把
  仍带别名的文件算作"非 canonical"（`:158-175`）。课后想改 domain 就走那条 `--write`。
- 转换器有**自己一张** `DOMAIN_MAP`（`scripts/intake_lesson_to_file.py:60-74`），不读 aliases。
  实测：`**Domain:** ops`（`domains.json` 里是 `devops` 的别名）会被跳过，报
  `domain 'ops' has no canonical form`。用 `--overrides` 补，别去改 `DOMAIN_MAP`。
- 选法：先在**已用过**的值里找最贴的。公开的 domain 计数是**推导值**（`scripts/sync_lesson_count.py:256-268`），
  当前 **49**——50 个 canonical 里只有 `integrations` 0 篇，而它被 `domains.json` 自己标成
  "待确认的保留位"（`data/domains.json:122`）。用一个新的 canonical 值会改这个公开数字，
  所以只在真没有贴的值时才用。
- 判据是**检索**：会来找这堂课的人会输入什么词，不是这堂课属于哪个学科（`data/domains.json:3`）。

## 6. 生成物：谁写、谁守、PR 必须带哪些

lesson PR 的 `gate` 会在跑完生成器后断言"`main` 保留的生成物没有一个是脏的"
（`.github/workflows/lesson-gate.yml:161-168`，清单在 `scripts/ci/check_dist_diff.py:64-84`）。

| 文件 | 生成器 | 谁守 |
|---|---|---|
| `data/lessons.json` + `docs/data/lessons.json` + `docs/data/lessons-lite.json` | `scripts/update_lessons_json.py`（三个一起写，`:342-347`, `:388`） | `gate` 的 main-side + `tests/test_docs_data_copy.py:58` |
| `data/okf/lessons.jsonl` | `scripts/export_okf.py` | main-side + `tests/test_okf_export_freshness.py`（只看覆盖率，不逐篇） |
| `docs/index.html`、两份 `llms.txt`、`docs/_lessons_count.txt` | `scripts/sync_lesson_count.py`（由 `update_lessons_json.py` 调起，`:314-316`） | main-side + 必需 job `audit` 的 `--check` + `tests/test_lesson_count_ssot.py` |
| `lessons/index.md` | `scripts/rebuild_lessons_index.py` | main-side（清单第 80 行） |
| `data/public-vocabulary.json` | `scripts/export_public_vocabulary.py` | **只有** `tests/test_public_vocabulary.py:26-31` |
| `docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml`、`docs/_redirects`、`docs/.generated-pages.json` | `scripts/build_lesson_pages.py` | `tests/test_lesson_page_generator.py:39` |
| `tests/fixtures/ranking-snapshot.json` | `python3 scripts/gen_ranking_snapshot.py` | `tests/test_ranking_snapshot.py`（31 个查询的 top-N 与分数逐条钉住） |
| `docs/trust-semantics.md` 的 E0–E4 分布表 | `python3 scripts/evidence_distribution.py`（**只打印，要自己粘进去**），再用 `--check docs/trust-semantics.md` 验 | `tests/test_evidence_distribution.py` |

五条容易踩的（后两条是批量 3 用 CI 换来的：第一次跑时 `evidence_distribution` 与
`gen_ranking_snapshot` 都不在清单里，三条测试腿一起红——语料一变，这两处**必然**跟着变，因为它们的
输入都是整个语料）：

1. **`public-vocabulary.json` 不在 lesson-gate 的步骤里**（`.github/workflows/lesson-gate.yml:161-168`），
   它的门禁只有那条逐字节比对的测试。它必须**最后**跑：输入是整个语料，先跑就会漏掉刚加的课。
2. **`docs/**` 的页面现在仍在 `main` 上被追踪**（751 个文件），所以要跑 `build_lesson_pages.py` 并提交；
   `check_dist_diff.py:48-62` 的 `DIST_ONLY` 已经把它们划给 `dist`，切过去之后由 `publish-dist.yml` 重生成。
   在那之前，漏跑它会让必需测试 `test_repo_pages_match_the_index` 红。
3. 页面生成器的 URL 是**粘的**：它按 `docs/.generated-pages.json` 保留旧 slug，改名不换 URL。

## 7. 一次批量的落地序列

```bash
python3 scripts/intake_lesson_to_file.py --issues-json /tmp/issues.json \
  --overrides /tmp/overrides.json --slugs /tmp/slugs.json --write
python3 scripts/lesson_gate.py lessons/contrib/<新文件>…      # 逐个；不要对整目录 --all
python3 scripts/injection_scan.py --dir lessons               # high 级 → 退出 1
python3 scripts/update_lessons_json.py
python3 scripts/export_okf.py
python3 scripts/rebuild_lessons_index.py
python3 scripts/build_lesson_pages.py
python3 scripts/gen_ranking_snapshot.py                       # 排名快照：语料一变，分数就变
python3 scripts/evidence_distribution.py                      # 打印 E0–E4 分布（粘进 docs/trust-semantics.md）
python3 scripts/evidence_distribution.py --check docs/trust-semantics.md
python3 scripts/export_public_vocabulary.py                   # 最后：输入是语料本身
python3 scripts/sync_lesson_count.py --check
git status --porcelain                                        # 生成物必须已提交，不是"已生成"
```

> `lesson_gate.py` 慢（每篇都要跟 750 篇算相似度），一批 24 篇是分钟级，别用短超时。
> 只改既有文件时加 `--existing`，否则历史欠账会把 PR 染红。

## 8. 合入前必须绿的检查

**必需上下文只有 5 条**（实测 `gh api repos/Ikalus1988/MisakaNet/rulesets/23826057`，2026-11-01）：
`DCO / Signed-off-by`、`test (ubuntu-latest, 3.11)`、`test (windows-latest, 3.11)`、`gate`、`audit`。
`docs/agents/repo-operations.md` 里的清单是文档，不是判据。

- **`gate`**：新增文件严格（`.github/workflows/lesson-gate.yml:99`），既有文件 advisory（`:117`），
  然后跑生成器 + main-side（`:161-168`），最后自测 `tests/test_lesson_gate.py`（`:177`）。
- **`audit`** 跑 `pytest tests/`，§6 那几条生成物测试都在里面。
- **`lesson-security`** 跑 `scripts/injection_scan.py --dir lessons`（high → 1）。它不是必需上下文，
  但红了别合。
- **`provenance`**：`evidence_level` 是 E2/E3 的新课，一个引用都没有就是失败
  （`scripts/check_provenance.py:14-23`）；写 E1 的课不走这条。死链（404/410）任何级别都失败。
- **自动合并通道用不上**：`auto-merge-lesson` 要求**全部**改动路径都在 `lessons/` 下
  （`scripts/lesson_pr_mergeable.py:72-86`），而 `gate` 要求 PR 带上 §6 的生成物 → 批量 PR 只能人工合。

## 9. 合入之后

- 关 issue + 回执，模板与判据在 `docs/maintainer/intake-triage.md` §3。回执靠
  `source:` / `provenance.issue` 这两处引用（`scripts/intake_receipt.py:48-51`），转换器正好写了
  `provenance.issue: "#N"`（`scripts/intake_lesson_to_file.py:239-240`）。
- 自动回执脚本只认 `contrib_id`（`scripts/emit_intake_receipt.py:111`），转换器不写它——这些课的
  报料者拿到回执走的是"MCP 原样重发同一条 problem"那条路，不是 issue 评论。
- `scripts/done_but_open.py` 只报告"课已上、单还开着"，不代替回执，也不关单。

## 10. 本文没有定的事

1. **E 级别的真伪**。gate 只校验枚举（`scripts/lesson_gate.py:41`, `:169-172`），而转换器无条件写
   `E1`（`scripts/intake_lesson_to_file.py:232`），E1 的定义是 "Maintainer reviewed — a maintainer
   accepted the intake"（`misakanet/evidence.py:30-34`；intake 的默认是 E0）。所以"没读就转换"会产出
   一份声称被审过的文件，没有任何门禁能发现。**转换这一步就是你读它的那一步**；没读就改成 `E0`。
   要让它可判，得让 converter 从 review 动作拿级别——现在没有这个输入。
2. **`--slugs` 的下游**。仓库里没有消费者；要它有用得先写一个（比如按 slug 给每条 issue 留回执）。
3. **批 1/2 的耗时与返工率**没有记录在任何文件里；判"下一批要多久"只能自己计时。
4. **队列分布是快照**：24 条 / 9 条太短 / 4 条命令名，都是 2026-11-01 的一次读数，
   下次要用 §0 的命令重数。
