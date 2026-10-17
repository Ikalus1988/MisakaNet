# `dist` 分支切换：把生成物搬出 `main`

> **决定（owner，2026-10-16）**：`main` 只承载「源 + 门禁 + worker」。生成产物搬到 `dist` 分支，
> Cloudflare **Workers Builds** 的 production branch 从 `main` 改指 `dist`。
>
> **状态（2026-10-17）**：发布器与门禁改造已落地；**B1（production branch → `dist`）与 B2（build token
> 复核有效）已完成**，`dist` 与 `main` 的树当时逐字节相同；**B3（对 `dist` 触发一次构建并等绿）仍未做**
> —— 切换后 `dist` 头上只有切换前那次构建（build `a770f4c9`）。**`Site build watch` 已改为只看 `dist`**
> （`workers-builds-watch.yml` + 脚本默认值）：留在 `main` 上它会一直读到最后一次绿、从此沉默。
> 本文件 §4 的清单里带 🧑 的步骤**只能由有 Cloudflare 控制台权限的人做**（Workers Builds 是 Git
> 集成，配置在 CF 控制台，不在本仓——见 `docs/agents/repo-operations.md` §3 的 `misakanet-web` 行）。
>
> **本文件代替不了规则集**：必需检查的权威列表是 `docs/ci-gates.md`（`scripts/check_documented_gates.py`
> 会拿它和线上 ruleset `23826057` 对比）。

## 0. 一句话机制

`dist` **不是**一个有人编辑的分支。每次 push 到 `main`，发布器把 `main` 检出、按文档顺序跑六个
生成器、把结果提交在新分支上，然后 force-push。所以：

```
dist = main 的树 + 生成物（唯一的差异）
```

推论：`dist` 总是 `main` 的祖先关系的后代（superset），随时可以整条重建、丢弃、回滚。

---

## 1. 分类：每个生成路径能不能离开 `main`（逐行证据）

**判定规则**（照任务书）：一个路径只要有**必需检查**（ruleset `23826057`：`DCO / Signed-off-by`、
`test (ubuntu-latest, 3.11)`、`gate`、`audit`）或运行期脚本从 `main` 的树里读它，就**不能**离开
`main`——除非先把那个读取者改掉。判定分两档：

- **留** = 读取者是「为了别的性质而需要这个文件」（SSOT、计数面、测试夹具、clone 期输入）。
  搬走它会**削弱那个门禁本身**，所以它不能离开 `main`。
- **可离开** = 读取者只是「关于生成树自身」的门禁，断言可以搬到发布器/dist 侧。**注意这不等
  于"现在就能删"**：按同一条规则，这 7 个路径**今天在 `main` 上仍然被必需检查读取**，所以
  **本次 PR 一个都不删**；"可离开"的含义是"**改掉那些读取者之后**它就可以离开"，§9.3 逐条给出
  必须先改什么。没有一档是「随便」：每一行都给出 `file:line`。

| # | 路径 | 生成器 | `main` 上的读取者（证据） | 判定 |
|---|---|---|---|---|
| 1 | `docs/lessons/**`（485 个页面） | `build_lesson_pages.py` | `tests/test_lesson_page_generator.py:53`（`blp.check(files, root=REPO)`，缺页报 `missing (would be created)`）· `tests/test_lesson_page_generator.py:385`（`corpus_page_problems`：逐课验证磁盘上有页）· `tests/test_site_pages_are_reachable.py:157`（`assert len(pages) > 400`，扫的是 `docs.rglob("*.html")`）· `scripts/build_lesson_pages.py:716`（`check()` 读 `root/rel`） | **可离开**（三个读取者都是「生成树自身」的门禁，见 §9 的顺序） |
| 2 | `docs/topics/**`（52 个页面） | `build_lesson_pages.py` | 同上的 `check()`——`plan_with_slugs` 把主题页放进同一个 `files` 字典（`scripts/build_lesson_pages.py:628-629`）· `tests/test_lesson_page_generator.py:143`（用的内存 `files`，不是磁盘） | **可离开**（同上） |
| 3 | `docs/sitemap.xml` | `build_lesson_pages.py` | `tests/test_sitemap_urls_resolve.py:148`（`test_the_committed_sitemap_matches_its_generator` 读**已提交**的那份） | **可离开**（该断言搬到发布器：它本来就每个 run 重新生成） |
| 4 | `docs/_redirects` | `build_lesson_pages.py` | `scripts/build_lesson_pages.py:521`（`read_redirect_sources`，被 `corpus_page_problems` 用来判断 id→slug 是否解析）· `tests/test_lesson_id_redirects.py:2` | **可离开**（它是 slug map 的**产物**，没有连续性负担） |
| 5 | `docs/.generated-pages.json` | `build_lesson_pages.py` | `scripts/build_lesson_pages.py:647`（`load_slug_map`：**这是状态，不只是产物**——sticky slug 的权威）· `tests/test_site_pages_are_reachable.py:226` · `tests/test_generated_artifact_marking.py:38,151`（`MUST_BE_MARKED` + `.gitattributes` 里每条规则必须匹配到树里的东西） | **可离开，但有前置条件**：发布器必须先播种 slug map（已实现，见 §2.3） |
| 6 | `docs/data/lessons.json` | `update_lessons_json.py` | `tests/test_docs_data_copy.py:60`（`compare_index_copies(CANONICAL, PUBLISHED)`）· `scripts/check_docs_data_copy.py:49` | **可离开**（比较关系搬到 dist 侧） |
| 7 | `docs/data/lessons-lite.json` | `update_lessons_json.py` | `tests/test_docs_data_copy.py:284`（`compare_lite_projection(cdc.CANONICAL, cdc.LITE)`）· `scripts/check_docs_data_copy.py:50` | **可离开**（同上） |
| 8 | `docs/index.html` | `sync_lesson_count.py` **只写 meta 里那一个数字** | 本体是**手写源码**：`tests/test_version_consistency.py:357,377`（版本徽章）· `tests/test_site_csp.py:5` · `tests/test_site_accessibility.py:4` · `.github/workflows/auto-merge-docs.yml:124`（**永不**自动合并）· 计数行 `scripts/sync_lesson_count.py:197`（`_META`，`min_matches=3`）· `tests/test_lesson_count_ssot.py:248` | **留**（源码 + 受管计数，同一个文件；它跟 485 个纯生成页不是一类） |
| 9 | `docs/llms.txt` | `sync_lesson_count.py` | `scripts/sync_lesson_count.py:215,366` · `tests/test_lesson_count_ssot.py:249` · `scripts/check_doc_freshness.py:37` | **留**（必需 `audit` 作业跑 `sync_lesson_count.py --check`，`pr-checks.yml:564`） |
| 10 | `docs/.well-known/llms.txt` | `sync_lesson_count.py` | `scripts/sync_lesson_count.py:217,368` · `tests/test_lesson_count_ssot.py:250` | **留**（同上，同一逻辑面的第二份） |
| 11 | `docs/_lessons_count.txt` | `sync_lesson_count.py` | `scripts/sync_lesson_count.py:131`（`COUNT_FILE`）· `tests/conftest.py:69`（**每个测试前后**对「已发布面」取戳）· `.github/workflows/pr-thank-you.yml:43`（**运行期**从 main 读） | **留**（运行期消费者在 `main`） |
| 12 | `data/lessons.json` | `update_lessons_json.py` | `scripts/sync_lesson_count.py:376`（`canonical_count()` = 计数 SSOT 的源头）· `.github/workflows/pr-checks.yml:572`（schema 校验，必需 `audit`）· `tests/test_lesson_count_ssot.py:46` · `tests/conftest.py:69` | **留**（SSOT；它一旦不在 `main`，计数门禁本身无从比较） |
| 13 | `data/okf/lessons.jsonl` | `export_okf.py` | `tests/test_okf_export_freshness.py:30` · `scripts/build_sag_index.py:67`（**使用者 clone `main` 之后**用它建 `data/sag.db`——clone 期输入，不是站点产物） | **留** |
| 14 | `lessons/index.md` | `rebuild_lessons_index.py` | `scripts/lesson_pr_mergeable.py:85`（`INDEX_PATH`：**lesson PR 自动合并门禁**按它判断"最多加一行"）· `tests/test_query_aliases.py:140` | **留**（位于语料目录 `lessons/` 之内，且是门禁输入） |
| 15 | `tests/fixtures/ranking-snapshot.json` | `gen_ranking_snapshot.py` | `tests/test_ranking_snapshot.py:48`（`FIXTURE.exists()`）· `scripts/gen_ranking_snapshot.py:55` | **留**（它是**钉住的期望**，是门禁输入，根本不是站点产物） |

**复现方式**（每个路径的读取者）：

```bash
for p in docs/lessons docs/topics docs/sitemap.xml docs/_redirects docs/.generated-pages.json \
         docs/data/lessons.json docs/data/lessons-lite.json docs/index.html docs/llms.txt \
         docs/.well-known/llms.txt docs/_lessons_count.txt data/lessons.json \
         data/okf/lessons.jsonl lessons/index.md tests/fixtures/ranking-snapshot.json; do
  echo "### $p"; grep -rIn --exclude-dir=node_modules --exclude-dir=.git -F "$p" tests/ scripts/ .github/workflows/
done
```

**结论**：**7 个可离开**（1–7），**8 个必须留**（8–15）。可离开的那 7 个正好是「只被**服务**、
不被任何门禁当作别的事实的输入」的那部分；这也解释了为什么切换必须先改门禁、而不是先删文件。

> **§1 的一个重要限定**：`docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml`、`docs/_redirects`、
> `docs/.generated-pages.json`、`docs/data/*` 现在**仍然**由必需检查读取，所以**本次 PR 一个都不删**
> （§9 是删除 PR 的范围）。删了它们而不同时改门禁，`test (ubuntu-latest, 3.11)` 会立刻变红。

### 1.1 本次分类**没有**覆盖、但同样在 `docs/data/` 的生成物（owner 待决）

`docs/data/` 下还有三个高频生成物，**不在**任务书给的清单里，但它们才是 `docs/data/` churn 的主体：

| 路径 | 生成者 | 30 天命中提交数 |
|---|---|---|
| `docs/data/feed.json` | `.github/workflows/build-feed.yml`（三小时一次） | 135 |
| `docs/data/activity.json` | `build-feed.yml` / `scripts/sync_site_activity.py` | 103 |
| `docs/data/activity-series.json` | `scripts/sync_activity_series.py` | 54 |
| 三者并集 | | **137（11.4%）** |

发布器**故意不碰**它们：它们的写入者是 `build-feed.yml`，那条流水线走 `land_change.py` 落到 `main`。
把两个作业指向同一批文件就是任务书禁止的「两个作业抢同一批文件」。**是否把它们也搬到 `dist`（或把
`build-feed.yml` 改成只写 `dist`）需要 owner 拍板**——见 §10.4。

---

## 2. 发布器做什么（`.github/workflows/publish-dist.yml`）

### 2.1 触发 / 权限 / 并发

| 项 | 值 | 与 `data` 分支先例（`update-badges.yml`）的差异与理由 |
|---|---|---|
| 触发 | `push: branches: [main]`（**无 `paths:` 过滤**）+ `workflow_dispatch` | `dist` 要跟着 `main` **到处**走：手改的 `docs/**` 页面也是站点源码，按 `lessons/**` 过滤会让站点继续服务旧页面。不增加构建频率——CF 今天本来就是每次 push `main` 都构建 |
| 权限 | `contents: write`（仅此一项） | 不开 PR、不评论、不碰 release，所以不需要 `pull-requests` |
| 并发 | `group: publish-dist`，`cancel-in-progress: true` | 与 `update-badges.yml` 同一论证：`dist` 是 `main` 的纯函数，只有最新的 run 值得跑完；被取消的 run 要发布的是更旧的语料 |

### 2.2 怎么推、怎么不回环

- **只推 `dist`**：`git push --force origin dist:dist`。`tests/test_no_workflow_pushes_to_main.py` 扫描
  本文件时不会命中（refspec 是 `dist:dist`），ruleset 也只保护 `main`。
- **force 是必须的**：每个 run 都从 `main` 的 HEAD 重建 `dist`，所以上一个 `dist` 提交**不是**本次提交
  的父提交，push 永远不是 fast-forward。`dist` 是「重建、从不编辑」的一次性分支，force 在这里是正确
  语义，不是偷懒（回滚也因此只是「改回 `main` + 删 `dist`」）。
- **没有回环**：`GITHUB_TOKEN` 触发的 push **不会**创建新的 workflow run（GitHub 的规则），而且本
  workflow 只监听 `push: main`。两条独立保证。
- **每个 run 都提交（`git commit --allow-empty`），没有"生成器没写出东西就跳过"的早退**。这条容易被
  当成无害优化，实际是个会静默冻结站点的坑：`dist` 不是"那堆生成物"，它是 **`main` 的整棵树 + 生成物**，
  所以一次**只改源码**的 push（新写一个 `docs/quickstart.md`、修一处 `docs/index.html`）会让生成器无事
  可做——在那里早退，`dist` 就永远继续服务**旧源码**，而 run 是绿的。在今天的树上它还意味着 `dist`
  **根本不会被创建**（§4 A2/A3 的前提）。
  实测 2026-10-16：在干净的 `main` 上按顺序跑完六个生成器，前后 `git status --porcelain` 逐字节相同，
  耗时 ~8 秒——也就是说生成器今天是幂等的，但"幂等"是生成物的性质，**不能**推出"这次不用发布"。
- **认证**：`persist-credentials: false` + `git remote set-url` 带 token。理由写在
  `docs/agents/repo-operations.md` §4：`actions/checkout` 会把 `GITHUB_TOKEN` 存进
  `http.extraheader` **和** 一个 `includeIf` 凭据文件，只清 header 不够。
- **提交信息里没有 `[skip ci]`**——这是唯一一处**不能**照抄 `data` 分支先例的地方。
  `update-badges.yml` / `update-smithery-badge.yml` 加它是因为 `data` 分支没人构建；`dist` **存在的
  意义就是被构建**（Cloudflare Workers Builds 从它部署）。在「必须触发部署」的那个提交里放跳过标记
  是本末倒置。而且这里本来就不需要抑制任何东西（见上一条）。

### 2.3 一个必须处理、否则会静默毁 URL 的坑：sticky slug 的连续性

`docs/.generated-pages.json` 不只是产物，它是页面生成器的**状态**：`load_slug_map`
（`scripts/build_lesson_pages.py:644-647`）读它来知道每个 lesson id 的**当前 URL**，因为 slug 是
sticky 的——按标题重新推导正是当年让 **88 个线上 URL 变孤儿**的做法。

`main` 上一旦没有这个文件，第一次运行就会以空 slug map 开始，于是所有 URL 按标题重推 → 一批页面换
地址。发布器因此有一个前置步骤：

```bash
if [ -f docs/.generated-pages.json ]; then use main's copy; else seed from the previous dist commit; fi
```

**这条在切换前是 no-op（`main` 上还有那个文件），切换后是唯一让 URL 保持稳定的机制。**
`tests/test_dist_publisher.py::test_the_slug_seed_distinguishes_no_branch_from_a_failed_fetch` 锁住
「`dist` 不存在」与「读不到 `origin`」必须被区分（`git ls-remote --exit-code` 退出 2 vs 128）：
前者空 slug map 是对的，后者如果被一并吞掉，就是**静默把所有 URL 重推一遍**。

### 2.4 跑了哪些生成器、与其它 workflow 的关系

顺序（发布器里原样，也是仓库文档的顺序：`scripts/question_autopilot.py:349-351` 给贡献者写的前三个，
`update-lessons.yml:98,134` 里的 `export_okf.py` / `rebuild_lessons_index.py`（`sync_lesson_count.py` 由
`update_lessons_json.py` 内部调用），以及 `docs/maintainer/handoff-2026-10-11.md` §80 记的最后一个——
那一节记的正是「漏了它，加一门课就让 `tests/fixtures/ranking-snapshot.json` 陈旧」）：

```
update_lessons_json.py → build_lesson_pages.py → export_okf.py
                       → sync_lesson_count.py → rebuild_lessons_index.py → gen_ranking_snapshot.py
```

**与 `update-lessons.yml` 的关系：现在是互补，切换后取代它的一半。明确说清楚：**

| 生成器 | `update-lessons.yml`（每天 + `lessons/**` push，落 `bot/update-lessons` PR → `main`） | `publish-dist.yml`（每次 push `main`，落 `dist`） |
|---|---|---|
| `update_lessons_json.py` | 跑（**必须继续跑**：`data/lessons.json` 留在 `main`，`sync_lesson_count --check` 与 schema 门禁都读它） | 跑（同一批字节；`main` 已同步时是 no-op） |
| `build_lesson_pages.py` | 跑（**切换前必须跑**，否则 `main` 上的页面陈旧、`test_repo_pages_match_the_index` 变红） | 跑（切换后**由它独占**；`update-lessons.yml` 那一步要删掉） |
| `export_okf.py` / `rebuild_lessons_index.py` | 跑（产物都留在 `main`） | 跑（no-op） |
| `sync_lesson_count.py` | 跑（`update_lessons_json.py` 内部也调） | 跑（no-op） |
| `gen_ranking_snapshot.py` | **不跑** | 跑（no-op；见 §10.6 的一条注意事项） |

**两个作业不抢同一批文件**：它们的写入目标是两条不同的分支（`main` 的 PR vs `dist`），`dist` 的 push
也不会触发任何以 `main` 为条件的 workflow。代价是一次重复计算，收益是切换前两边都正确。

**切换（§4）之后**，删除 PR（§9）必须同时把 `update-lessons.yml` 里的
`build_lesson_pages.py` 那一步删掉——否则那个每天运行的作业会**把生成页面重新加回 `main`**，
把 churn 又带回来。

---

## 3. `lesson-gate.yml` 里那条「生成物必须与语料一致」的门禁变成了什么

**原来**（`lesson-gate.yml`，`Generated files must match the corpus`）：跑
`update_lessons_json.py` + `build_lesson_pages.py`，然后 `git diff` 非空就失败。

**为什么它不能原样留着**：切换后 `build_lesson_pages.py` 写出来的页面**本来就不该**在 PR 里，
一条要求它们出现的规则等于要求把 churn 加回来；而 `git diff` 又看不见未跟踪文件，于是同一条规则会
在切换后**变成永远为真**（假绿）——「不会失败的规则」正是本仓反复记录的失效形态。

**改成了什么**（已实现）：

1. 跑**只写"留在 `main` 的文件"**的那四个生成器：
   `update_lessons_json.py`、`export_okf.py`、`sync_lesson_count.py`、`rebuild_lessons_index.py`。
2. 用 `python3 scripts/ci/check_dist_diff.py main-side` 断言：**`MAIN_SIDE` 里的路径一个都不脏**
   （看 `git status --porcelain`，因此未跟踪文件也算）。`MAIN_SIDE`/`DIST_ONLY`/`PUBLISHED` 的清单
   就在那个脚本里，是 §1 分类表的代码形式。

为什么这样在**切换前后都正确**，且不用在删除 PR 里再改一次：

- 切换前：`data/lessons.json` 就是那个「忘了重跑生成器」的哨兵，行为和原来一样会红。
- 切换后：`build_lesson_pages.py` 不在这里跑了，它写的文件（`DIST_ONLY`）也不会被要求；
  而写 `main` 侧文件的那四个生成器仍然被要求。
- **生成页面并没有因此失去保护**：`docs/lessons/**` 还在 `main` 上时，
  `tests/test_lesson_page_generator.py::test_repo_pages_match_the_index`（逐文件比对计划与磁盘）与
  `::test_every_corpus_lesson_has_a_page_on_disk`（逐课要求有页）都跑在必需检查
  `test (ubuntu-latest, 3.11)` 里，**同样能拦合并**——原来这条 shell 步骤只是更早、信息更集中地报同一件事；
  切换之后页面由发布器每次 push 重新生成，根本不可能陈旧。

`gen_ranking_snapshot.py` **故意不在这里跑**：它需要 `misakanet-core`，而这个作业是快速门禁（只装
`pyyaml`）；`tests/test_ranking_snapshot.py` 已经在必需测试矩阵里，且报错信息本身就给出重新生成命令
（`handoff-2026-10-11.md` §80 记录的正是这条）。

---

## 4. 切换清单（有序；🧑 = 只有人能做）

### 阶段 A：本次 PR 合并后（**首次必须手动触发一次**，之后自动）

- [ ] A1. 合并本 PR（发布器 + 文档 + 门禁改造）。
- [ ] A2. **手动创建 `dist`：`gh workflow run publish-dist.yml --ref main`。**
      这一步不是图省事，而是没有它 `dist` 根本不会被创建：**GitHub 不会用引入某个 workflow 的那次
      push 去触发它自己**。实测 2026-10-16（本 PR 合入当天）：`publish-dist.yml` 在 `main` 上
      `state=active`、触发块就是正确的 `push: branches: [main]`、也没有 `paths:` 过滤，而该 workflow
      的 run 总数是 **0**——它自己的引入提交没有产生任何 run。`workflow_dispatch` 本来就在文件里，
      注释也写着 "first creation of `dist`"。
      **之后**每次 push 才会自动触发，且已实测：同一天 `main` 从 `d1eeba6f` 走到 `a9e0a4b9` 时，
      `event=push` 的那次 run `completed success`，`dist` 前移到 `1f431726`（父提交 = 那一刻的 `main`）。
      所以本文档初稿写的"在合并产生的 push 上自动运行"是错的，且错法值得记住：**一个只被手动跑过一次
      的管道，不能让它承载线上站点**——切换之前必须在一次真实的 push 上见过它绿。
- [ ] A3. 确认 `dist` 分支已创建，且它确实是 `main` 的 **superset**、差异只有生成物。
      **此时两边的树应当完全相同**（`git rev-parse origin/dist^{tree}` 与 `origin/main^{tree}` 相等）：
      阶段 B 还没执行，`main` 自己仍带着全部生成物，所以发布器重跑生成器后产出字节相同、提交是
      `--allow-empty`。这不是"检查没意义"——它意味着此刻切过去，线上内容与切换前**逐字节一致**；
      这项检查要到阶段 B 把生成物从 `main` 删掉之后才真正开始承重。
      **用 tree 比，不要只用 ancestry**：`dist` 的父提交是"构建那一刻的 `main`"，所以 `main` 在构建
      之后又动了的话，`origin/main` 会暂时不是 `origin/dist` 的祖先（下一次发布器运行就追平）——

  ```bash
  git fetch origin main dist
  # main 的每个路径，dist 都必须有（期望：空输出）
  comm -23 <(git ls-tree -r --name-only origin/main | sort) \
           <(git ls-tree -r --name-only origin/dist | sort)
  # 差异清单应该只落在 DIST_ONLY 里（§1 的 1–7 条）
  git diff --name-only origin/main origin/dist | sed 's#/[^/]*$##' | sort -u | head
  # 发布器自己也每个 run 断言同一件事：scripts/ci/check_dist_diff.py diff --base "$BASE"
  ```

- [ ] A4. 用一次 `workflow_dispatch` 复跑，确认**生成物没有漂移**：它会照例产生一个新提交（这是设计，
      不是 bug——见 §2.2），但这次提交的**树**应该和上一次相同。注意不能拿 `origin/dist~1` 比：`dist`
      的父提交永远是 `main` 的 HEAD，不是上一次的 `dist`（force-push 会把它替换掉），所以要自己记 tree：

  ```bash
  git fetch origin main dist
  BEFORE=$(git rev-parse origin/dist^{tree})
  gh workflow run publish-dist.yml && gh run watch
  git fetch origin dist
  [ "$BEFORE" = "$(git rev-parse origin/dist^{tree})" ] \
    && echo "same tree — the generators are idempotent on this main" \
    || echo "the tree moved: read git diff --name-status origin/main origin/dist"
  ```

### 阶段 B：Cloudflare 侧（🧑 只能人工）

- [ ] 🧑 B1. Cloudflare 控制台 → Workers & Pages → `misakanet-web` → Settings → **Builds** →
      **production branch** 从 `main` 改成 `dist`。**这一步在仓库里做不到**：Workers Builds 是 Git
      集成，配置在控制台（`docs/agents/repo-operations.md` §3 的 `misakanet-web` 行）。
      *前置*：`dist` 必须已存在（A3），否则控制台里选不到它。
- [ ] 🧑 B2. 确认 build token 仍有效（同页 Builds → API token）。**这不是可选步骤**：仓库侧见过
      「build token selected for this build has been deleted or rolled」（2026-09-23 轮换 API token
      时作废，站点停更一天）——`docs/agents/repo-operations.md` §4。
- [ ] 🧑 B3. 在控制台对 `dist` 触发一次构建（或 push 一个空提交到 `dist`），等它绿。

### 阶段 C：验证（见 §5 的对照表；任何人可做）

- [ ] C1. 逐条跑 §5 的对照命令，确认切换前后**字节一致**。
      **注意 HTML 不能直接逐字节比**：Cloudflare 会给每个 HTML 响应注入一行
      `window.__CF$cv$params={...}`（每次请求都不同）。实测 2026-10-17：`/` 连抓三次哈希全不同，
      把含 `__CF$cv$params` 的行过滤掉后三次完全一致；而静态资源（`/data/lessons.json`、
      `/sitemap.xml`、`/llms.txt`、`/trust-semantics.md`）本来就逐字节稳定，直接比。
- [ ] C2. 确认 `dist` 上的 push 产生 `Workers Builds: misakanet-web` check-run（由 Cloudflare app
      发出，带 Version ID），且**部署的确实是 production**。注意 `main` 也不一定"完全不产生"它：
      Workers Builds 的 preview 构建对所有分支生效（切换前 `dist` 自己就有过一条 preview 构建），
      所以判据是"`dist` 的新构建存在且是 production 部署"，不是"`main` 上一条都没有"。
- [ ] C3. 确认 `Site build watch` 在切到 `dist` 后仍然会喊：手动跑一次
      `python3 scripts/workers_builds_watch.py --branch dist --dry-run`，应看到
      `site build: green …`（不是 `absent`→red）。**这一步必须做**——watcher 若仍看 `main`，
      它会在站点停更时保持沉默，而那正是 #2136 的失败形态。
- [ ] C4. 观察一个完整周期（至少跨一次 `lessons/**` 合并）：课程页面在合并后几分钟内上线，
      且**该合并的 PR 只带 `main` 侧文件**。

### 阶段 D：确认稳定之后

- [ ] D1. 开删除 PR（范围见 §9）。**在 C1–C4 全部通过之前不要开。**

---

## 5. 怎么验证切换成功

CF Workers Builds 是**异步**的，而且是**按分支**的，所以「等它绿」不够——要拿**内容**对比。

**切换前**（在 `main` 上采集基线）：

```bash
BASE=/tmp/dist-cutover-before; mkdir -p "$BASE"
for u in / /lessons/ /topics/ /sitemap.xml /llms.txt /data/lessons.json /data/lessons-lite.json; do
  curl -sSL --compressed "https://misakanet.org$u" -o "$BASE/$(echo "$u" | tr '/' '_')"
done
# 抽 5 个真实课程页与它们的 id 别名（_redirects 生效的那条路）
python3 - <<'PY'
import json, subprocess
rows = json.load(open('docs/data/lessons.json'))
print('\n'.join(f"/lessons/{r['id']}/" for r in rows[:5]))
PY
```

**切换后**：重跑同一条命令到 `/tmp/dist-cutover-after`，然后

```bash
diff -r /tmp/dist-cutover-before /tmp/dist-cutover-after && echo "site is byte-identical after the cutover"
```

**注意两件容易误判的事**（都踩过）：

- 目录式路径**没有尾斜杠会 307**（`/privacy` → `/privacy/`），不是 404——先加 `-L`（上面已经加了）。
- 站点是边缘缓存的：`curl` 立刻打可能还是旧版本。要判断"冻在哪一版"，拿一个仓库里的文件比对
  （例如 `/maintainer/dist-branch-cutover.md`，这个文件本身就能当探针）：`git show <sha>:docs/...`。

**另外三条更硬的证据**：

```bash
# 1) dist 是 main 的 superset，且差异只有生成物（发布器自己每个 run 都断言一次：
#    scripts/ci/check_dist_diff.py diff --base "$BASE"）
git fetch origin main dist
comm -23 <(git ls-tree -r --name-only origin/main | sort) \
         <(git ls-tree -r --name-only origin/dist | sort)   # 期望空

# 2) sticky slug 没被重推：id→slug 表必须逐字相同。**在删除 PR 之前**先把 main 的那份存下来，
#    删除之后 main 上就没有这个文件了。
git show origin/main:docs/.generated-pages.json \
  | python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin)["slugs"],sort_keys=True))' \
  > /tmp/slugs-before.txt
git show origin/dist:docs/.generated-pages.json \
  | python3 -c 'import json,sys;print(json.dumps(json.load(sys.stdin)["slugs"],sort_keys=True))' \
  > /tmp/slugs-after.txt
diff /tmp/slugs-before.txt /tmp/slugs-after.txt && echo "no lesson URL was re-derived"

# 3) check-run：切换后 check-run 跟着 dist 提交，不再跟着 main 提交
gh api "repos/Ikalus1988/MisakaNet/commits/$(git rev-parse origin/dist)/check-runs" \
  --jq '.check_runs[] | select(.name|test("Workers Builds")) | {name, conclusion, details_url}'
```

---

## 6. 回滚

`dist` 是**一次性的、纯派生的**分支，所以回滚是把控制台改回去，不需要动 git：

1. 🧑 控制台把 `misakanet-web` 的 production branch 从 `dist` 改回 `main`（§4 B1 的同一个设置）。
2. 🧑 触发一次构建，跑 §5 的对照（这次以 `main` 为基线）。
3. `dist` 可以留着也可以删（`git push origin --delete dist`）——下次需要时发布器会重建它。
   **不要**把 `dist` 合并回 `main`：那正是要避免的 churn。

回滚不会丢任何东西：`main` 上的一切都是源，`dist` 上的一切都能从 `main` 重新生成。
**唯一不可逆的时刻是 §9 的删除 PR**——这也是它必须排在 §4 D1、在 C 阶段全部通过之后的原因。

---

## 7. 测得的 churn 减少

窗口：`/tmp/wt-dist` 工作树，2026-10-16，`--since="30 days ago"`（该工作树是 shallow，但历史回溯到
2026-08-21，30 天窗口完整）。**先信命令、再信数字**。

```bash
T=$(git log --since="30 days ago" --format=%H | wc -l)          # → 1205
for p in docs data lessons tests scripts workers .github; do
  echo "$p: $(git log --since="30 days ago" --format=%H -- "$p" | wc -l)"
done
# docs: 475 (39.4%)  data: 241 (20.0%)  lessons: 71 (5.9%)
# tests: 411  scripts: 192  workers: 141  .github: 197
```

**任务书里的 39% / 20% / 5.9% 复现无误。**但它指的是**整个 `docs/`**，其中大部分是**别的**
文档工作，不是生成站点。生成站点的真实占比：

| 路径 | 30 天命中提交数 |
|---|---|
| `docs/lessons` | 35 |
| `docs/topics` | 31 |
| `docs/sitemap.xml` | 30 |
| `docs/_redirects` | 15 |
| `docs/.generated-pages.json` | 34 |
| `docs/data/lessons.json` | 36 |
| `docs/data/lessons-lite.json` | 27 |
| **并集（= 可离开集合，§1 的 1–7）** | **51（4.2%）** |
| 对照组：留在 `main` 的生成物（§1 的 8–15）| 122（10.1%） |

文件级（更能反映 review 体量；同一提交里重复出现的路径只算一次）：

```bash
git log --since="30 days ago" --format=">>%H" --name-only | python3 - <<'EOF'
import sys
DIST = ("docs/lessons/", "docs/topics/")
EXACT = {"docs/sitemap.xml", "docs/_redirects", "docs/.generated-pages.json",
         "docs/data/lessons.json", "docs/data/lessons-lite.json"}
seen, hits, total = set(), 0, 0
for line in sys.stdin:
    line = line.rstrip("\n")
    if line.startswith(">>"):
        seen = set(); continue
    if not line or line in seen:
        continue
    seen.add(line); total += 1
    if line.startswith(DIST) or line in EXACT:
        hits += 1
print(f"DIST_ONLY touched {hits} of {total} (commit,file) pairs ({100*hits/total:.1f}%)")
EOF
# DIST_ONLY touched 685 of 4404 (commit,file) pairs (15.6%)
```

**换一种更直白的说法**（对一个 lesson-only PR，实测 PR #3258 / #3280）：

```bash
gh pr view 3258 --json files --jq '[.files[].path]'   # 18 个文件，其中只属于 dist 的 9 个
gh pr view 3280 --json files --jq '[.files[].path]'   # 17 个文件，其中只属于 dist 的 8 个
```

两个 PR 在删除 PR 之后都只剩 **9 个文件**（8 个留在 `main` 的生成物 + 1 个 lesson 源文件）；
差的 8–9 个正是 churn 的主体：一份新页面、受影响的主题页、`docs/topics/index.html`、
`sitemap.xml`、`_redirects`、`.generated-pages.json`、以及两份浏览器副本。

**诚实的结论**：这次搬迁移除的是**文件量与 review 噪音**（一个 lesson PR 少带接近一半的生成文件、
`main` 不再承载那 537 个页面），**不是** 39% 的提交量——`docs/` 的提交绝大多数是手写文档，
生成站点实际只占 **51 个提交（4.2%）**。**真正更大的那块 churn 是 §1.1 的 `docs/data/feed.json` +
`activity.json` + `activity-series.json`（并集 137 个提交，11.4%），它们不在本次范围内，需要 owner
拍板。** 如果目标是把 `docs/` 那 39% 降下来，光靠这次搬迁达不到；能达标的下一步是 §1.1 那三个
（以及 §10.5 的计数面，但它要先改必需门禁）。

---

## 8. `data` 分支要不要并进这套方案？——**不并，保持原样**

理由（逐条有据）：

1. **它服务的是"消费"，不是"构建"。** `data` 分支只有两个消费者：shields.io 的 endpoint 徽章
   （`badges/*.json`）和 Worker 的检索代理兜底（`fetchFromGitHub(..., "lessons.json", "data")`）——
   记录在 `data/README.md` 的「`main` 的 `data/` 与 `data` 分支各自服务谁」表里。
2. **它上面那份 `lessons.json` 不是 `main` 的那份**：81 KB 的紧凑索引 vs `main` 上 1.5 MB 的规范索引
   （`update-badges.yml` 用 `canonical_count()` 生成）。把它们合成一条分支等于让两个不同形状的产物
   共用一个 URL，而 Worker 读的那个 URL 是硬编码的 `.../data/lessons.json`。
3. **它的写入者已经稳定且活着**（`SHELDON_PAT` / `GITHUB_TOKEN` 推 `data`，从不触发本仓的构建），
   没有 churn 问题——它一年也不会有人 review 一次 diff。
4. **合并会增加耦合而不是减少**：`dist` 是「`main` 的纯函数、可随时整条重建」；`data` 是
   「按 key 累积的小文件集、被外部服务按固定 URL 拉取」。把后者塞进前者意味着每次 `dist` force-push
   都要重新考虑那些外部 URL 的稳定性。

**如果以后要收敛**，正确方向不是合并，而是让 `data` 的内容改由发布器从 `dist`（或 `main`）派生并
推送——那是另一件事，需要先确认 shields.io 与 Worker 的 URL 约定。

---

## 9. 后续 PR（本次**不写**）的确切范围

**一个 PR，且必须在 §4 C 阶段全部通过之后。**顺序不是装饰：删文件和改门禁必须在**同一个** PR 里落地，
否则中间那一刻 `main` 是红的。

### 9.1 前置条件（不满足就不要开）

- `publish-dist.yml` 至少一次绿，且 `dist` 上已有一份完整的生成树。
- 控制台 production branch 已是 `dist`，§5 的对照通过。

### 9.2 删除的路径（§1 判"可离开"的 7 条）

```
docs/lessons/**           (485 个页面)
docs/topics/**            (52 个页面)
docs/sitemap.xml
docs/_redirects
docs/.generated-pages.json
docs/data/lessons.json
docs/data/lessons-lite.json
```

### 9.3 同一个 PR 里必须同时做的门禁改造（每条都写明"什么能证明它可以删了"）

| # | 要改的东西 | 改成什么 | 为什么能证明该路径可以删了 |
|---|---|---|---|
| 1 | `tests/test_lesson_page_generator.py:53`（`test_repo_pages_match_the_index`）· `:385`（`test_every_corpus_lesson_has_a_page_on_disk`） | 改成对着**发布器的产物**断言，或整体移到 `dist` 侧（发布器已经每 run 重新生成，等价断言是 `check_dist_diff.py diff` + 生成器自己的 `--check`）。**不能只是删掉**——这两条是"每个 lesson 都有页"的唯一独立证明 | 断言不再读 `main` 的 `docs/lessons/**`；`docs/` 侧由 `check_dist_diff.py diff` 与 CF 构建覆盖 |
| 2 | `tests/test_site_pages_are_reachable.py:157`（`assert len(pages) > 400`） | 门槛改成"手写页面数"的真实下界（`docs/**` 去掉生成树后的数量），或把生成树部分改为对着 `dist` 的清单断言 | 该断言不再要求 `main` 上有 400+ 个 html |
| 3 | `tests/test_sitemap_urls_resolve.py:148`（`test_the_committed_sitemap_matches_its_generator`） | 删掉"和已提交文件比对"这半，保留 `generate_sitemap()` 自身的静态条目自检；提交物比对交给发布器（它在 `dist` 上提交那一刻就已经重新生成过） | `main` 上不再有已提交的 sitemap 可比 |
| 4 | `tests/test_lesson_id_redirects.py`（读 `docs/_redirects`） | 改成对着 `build_redirects_file(...)` 的输出断言（生成器侧的纯函数），或移到 dist 侧 | 不再需要 `main` 上的 `_redirects` |
| 5 | `tests/test_site_pages_are_reachable.py:226` + `tests/test_generated_artifact_marking.py:38,151` | 前者改读 `DIST_ONLY` 的清单；后者把"标记的路径必须匹配到树里的东西"改成"匹配到树里的东西**或** `scripts/ci/check_dist_diff.DIST_ONLY` 里的模式"——`.gitattributes` 的行**必须保留**，否则 `dist` 上那 537 个文件的 diff 会全部展开 | 两条规则都不再要求 `main` 上有这些文件，同时 `.gitattributes` 仍然生效于 `dist` |
| 6 | `tests/test_docs_data_copy.py:60,284` + `scripts/check_docs_data_copy.py` | 断言改成"生成器一次运行同时写出 canonical 与 site copy"（`MISAKANET_LESSONS_INDEX` 重定向路径已有），即**生产者**属性；"两份一致"的**结果**属性由发布器每次 push 重新生成来保证 | 不再需要 `main` 上存在 site copy |
| 7 | `.github/workflows/update-lessons.yml:88-89`（`build_lesson_pages.py` 那一步） | **删掉这一步** | 否则这个每天运行的作业会把生成页面重新加回 `main`，churn 原样回来 |
| 8 | `.github/workflows/docs.yml:66`（`build_lesson_pages.py --check`，push 门禁） | 删掉该步（`sync_lesson_count --check` 保留） | 该门禁读的就是 `main` 上的生成页面 |
| 9 | `.gitattributes` | **保留** `docs/lessons/**`、`docs/topics/**`、`docs/sitemap.xml`、`docs/.generated-pages.json`、`docs/data/**` 的 `linguist-generated=true` 行 | 它们仍然描述 `dist` 的树；删掉它们会让 `dist` 的 diff 全展开（就是当初加它们的理由） |
| 10 | `scripts/question_autopilot.py:349-351`（写给贡献者的"跑这三条"）· `docs/CI.md` · `docs/agents/repo-operations.md` §2/§3 | 改成"只跑留在 `main` 的那几条"；说明生成站点由 `publish-dist.yml` 负责 | 否则贡献者会继续把 `dist` 的文件提进 `main` |
| 11 | `tests/test_dist_publisher.py`（本 PR 新增） | 补一条"贡献者不应携带 `DIST_ONLY` 文件"的断言 | 让"发布器是唯一写入者"这条在 PR 侧也有牙 |

### 9.4 删除 PR 的验证

```bash
python3 -m pytest tests/ -q            # 与 CI 同命令
python3 scripts/sync_lesson_count.py --check
python3 scripts/build_lesson_pages.py --check   # 删除后这条不再适用，随 #8 一起删
gh workflow run publish-dist.yml && gh run watch
# 线上：§5 的对照命令（这次基线是删除后的 main 与 dist）
```

---

## 10. 未验证 / 需要 owner 拍板

1. **Cloudflare 侧的一切都无法在本仓验证**：production branch 这个设置存在（Workers Builds 的
   Git 集成配置项），但本 session 没有控制台权限，**没有实测**改它之后的构建行为。§5 的
   check-run 断言是留给有权限的人的第一条证据。
2. **`[skip ci]` 在 Workers Builds 里的行为未实测**。本仓没有任何文档说明它是否被 CF 识别；
   发布器**不使用**它（§2.2），所以这是"避免踩一个未验证的坑"，不是"已知它会坏"。
3. **`fetch-depth: 1` + `git ls-remote`/`git fetch --depth=1 origin dist` 在真实仓库上的表现未实测**
   （本 session 不能推 `dist`）。`ls-remote --exit-code` 的语义已在本工作树实测确认（存在=0、
   不存在=2），但"`dist` 已存在时 fetch 一定成功"这条依赖 checkout 的凭据配置：
   `persist-credentials: false` 之后由 `Configure git credentials` 这一步显式设置远端 URL，
   仓库若转为私有也不会静默降级成空 slug map（那个分支现在是 `exit 1`）。
4. **§1.1 的 `docs/data/feed.json` / `activity.json` / `activity-series.json`（并集 137 提交，11.4%）
   要不要也搬到 `dist`**——这是本次 churn 里最大的单块，但它的写入者是 `build-feed.yml`（三小时一次，
   走 `land_change.py` 落 `main`）。**需要 owner 决定**：是让 `build-feed.yml` 改写 `dist`，还是把这三个
   生成器也搬进发布器（那样 `build-feed.yml` 就只剩采集）。在决定之前，发布器不碰它们。
5. **`docs/index.html`、`docs/llms.txt`、`docs/.well-known/llms.txt`、`docs/_lessons_count.txt` 会继续
   在每次语料变化时 churn `main`**（§1 判定"留"）。若要把计数面也搬走，前提是先改
   `sync_lesson_count.py --check`（必需 `audit` 作业）与 `pr-thank-you.yml` 的运行期读取——那是比
   §9 大一档的改动，不在本次范围。
6. **`gen_ranking_snapshot.py` 在发布器里的意义**：`main` 同步时它是 no-op；只有 `main` 的夹具陈旧
   （`test_ranking_snapshot.py` 已经红）时它才会在 `dist` 上写一份修正版。任务书要求跑它，所以跑了；
   但它是**测试夹具**、属于 `main`，`dist` 上有一份被重新生成的夹具这件事本身**没有门禁在读**。
   如果 owner 认为不该在 `dist` 上重写测试夹具，把它从发布器删掉是安全的（`test_ranking_snapshot.py`
   已经覆盖 `main`）。
