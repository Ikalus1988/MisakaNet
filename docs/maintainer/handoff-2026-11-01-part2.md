# Handoff — 2026-11-01（第 24 卷，承接 `handoff-2026-11-01.md`）

> 上一卷：`docs/maintainer/handoff-2026-11-01.md`　·　下一卷：（本文件为最新）
>
> 本卷记两件事：**上一卷 §2.4 的 F841 收干净并进了门禁**（是 39 处，不是 25），以及
> **上一卷 §2.1 的积压数字没有一处对得上**（实测 20 / 49 / 220 / 141，而今天凌晨 03:50 之后
> 没有任何 issue 被关闭——差额不是"有人处理了"）。

## 1. 当前状态（每条都带命令，别人可以重跑）

- `main`：`f332b8a5a`（`#4266`）。`ruff check --select F821,F811,F841 .` = **clean**；合入前在
  `git archive HEAD` 的导出上同一个命令是 **39**。
- 语料 **750** lessons / **50** 个规范 domain（`data/lessons.json`、`data/domains.json`）——本卷不动语料，
  这两个数字与上一卷相同。
- 安装器 **0.9.0**，`pyproject.toml` **3.2.0**；**发版 PR `#4263`（3.2.1）开着没人合**，它的 body 里
  已经带上了本卷的修复（release-please 每天重写它）。
- 积压（2026-11-01 14:16 实测）：

  ```bash
  gh issue list --state open --limit 1000 --json number,title,labels   # open = 337
  #   [Lesson] 前缀：20（这 20 条全部带 pending-review）
  #   [Question] 前缀：49
  #   intake 标签 220 ／ needs-human-review 141 ／ pending-review 72（其中 [Lesson] 20、[Question] 49、其他 3）
  ```

## 2. 跨卷悬账

### 2.1 F841 已结；门禁现在只覆盖三种形态（这是取舍，不是遗漏）

`tests/test_python_undefined_names.py` 的 `SELECT` 是 `F821,F811,F841`，控制用例分别造出三种形态并断言
每条都被报出来。**没有**加进来的仍然是 `E`/`I`/`N`/`UP`（上千条，会变成一个没人能维持绿灯的门禁），
也没有加 `F401`（当前 193 处，绝大多数是测试文件里的历史遗留）。**判据**：只有当一条规则"红了是因为
真问题"、且清干净的成本可一次付完时，才配进这个门禁——上一卷 §3.1 那条对 Windows 腿的判据，同样适用于规则。

### 2.2 积压数字没有 SSOT（新账，下一轮排期前先读这条）

上一卷 §2.1 写"`[Lesson]` 还有 **42** 条、**77** 条 `[Question]`、**148** 条 intake（**105** 条
`needs-human-review`）"。本卷用三种口径实测（open 全量 / `[Lesson]` 前缀 / `pending-review` 标签）都是
**20 / 49 / 220 / 141**；而按 `sort:updated-desc` 取已关闭 issue，最新一条是 `#4189`
（`2026-10-31T19:50Z` = 11-01 03:50 +08），**此后一条都没关**。所以差额不是"有人处理掉了"，
是那个数没量对（或者是从更早一卷抄下来的）。

**行动**：下一轮按 **20 条**排期，不要按 42 条；并且积压数字从此**要么带命令，要么不写**。

### 2.3 发版在等人（上一卷的设计仍未实现）

`#4263` 就是那个现场：release-please 每天重写它，`stale.yml` 按"最后更新时间"算所以永远不旧，而它被
**故意**排除在自动合并之外。上一卷 §2.6 的建议（按 `autorelease: pending` 且创建超过 3 天提醒一次，
幂等标记、不刷屏）**还没有人写**。本卷没有实现，也不该由收账的这一轮顺手做。

### 2.4 `client_id` 宽限期（日期不变，仍是 2026-11-14 前后）

代码已上线，宽限期内只带名字续期返回 `deprecated`；`MISAKANET_CLIENT_ID_PROOF=strict` 是 dashboard
变量，打开不需要部署。**到点要做的两件事**：设 `strict`、删掉 `AGENTS.md` §3.3 与 `docs/mcp.md` 的宽限期措辞。
本卷没有碰它们。

### 2.5 审计剩余 15 条（本卷没有碰其中任何一条）

已结 / 记录在案 / 明确不做 / 还没人碰 四类划分见上一卷 §2.3，**没有变化**。本卷唯一相关的一条是
`F16`（ruff 风格 2,265 条不进 CI）——门禁加了 `F841` 之后这个数会小幅漂移，但不改变"不进 CI"的决定。

### 2.6 融合归一化：已修，但**生产效果还没量**（本卷改口）

根因就是上一卷 §2.5 那条：`fuseRankings` 用 `covered`（**本通道**命中的查询词占比）当权重，而分母是
"这个查询在该通道里展开成几个词"——CJK 查询 ~2 个英文词、~9 个 bigram，于是"英文 2/2"压过"中文 3/9"。
`#4293` 把权重改成纯 RRF（`1/(k+rank)`，一个通道一票），并写了会在 `HEAD` 上失败的用例（两个通道都把
正确答案排第一时，decoy 靠 4/9 > 3/9 反超）。

**量到的**：英文集 18/20 hit@1、19/20 hit@3 不变；CJK hit@3 **19/22 → 18/22**（地板 18），掉的那一行是
`中文乱码怎么解决`（top-3 → rank 5）——被去掉的那个权重以前正好压住它 bigram 通道里的 archive/fanuc 结果。
**没量到的**：`hit1-misses-2026-10-30.md` 里那 6 条生产行。它们需要部署后的 worker 与 D1 的富索引文本
（线上 `avgDocLen` 167.6，本地快照 122），本地量不出来。

**下一轮验收**：worker 下次部署后跑 `scripts/bench_production_recall.py` + CJK 集；6 行若没改善、或那一行
在生产上更差，就单独 revert `2f7555e0c`（一个可独立回滚的小提交）。**没做这个验证之前，不要把
"hit@1 修好了"写进任何汇报。**

### 2.7 其余（状态未变）

365 篇结构化字段回填（等模型额度窗口）· AE / Search Console / Colab（文档给了最小步骤，未执行）·
`#4072` 剩余（`recovery_hint` 指向持久 `client_id`、setup 落盘注册 id、孤儿节点 `Misaka38493`、SSE 长尾未量）。
邮件回执的结论也不变：先把"你的报料成了课程"这个触发点做出来，再谈搬家。

### 2.8 提案类 intake：路由有了，根因还欠一个决定（新账）

`#4251`（Glama 排名三个月计划）暴露的是一**类**问题：MCP 的 `kind` 只有
`missing_lesson / stale_lesson / new_lesson_candidate / question`，**没有"提案"这个值**，
所以计划只能按课程候选提交，再在正文里跟关键词分类器讲理。它于是被打成
`lesson-candidate` + `type:bug` + `priority:high` + `pending-review` —— 前两个说错它是什么，
第三个把它塞进"等落库的课程"队列。量过：当时 220 条开着的 intake 里，自述"不是失败报告"的**只有这 1 条**
（kind 分布 `missing_lesson` 126 / `question` 49 / `new_lesson_candidate` 43 / `stale_lesson` 2）。

**已做**：分类器按**提交者自述**分流（`proposal` / `type:feature`，摘掉 `type:bug` 与
`pending-review`），SOP §1/§2 各加一行，行为门禁 `tests/test_intake_proposal_route.py` 把工作流里那段
JS 真跑一遍（proposal / lesson-candidate / question 三条路 + 重跑改口 + 首次路径）。`#4251` 已实际
重跑分诊，标签从 `type:bug/pending-review` 变成 `type:feature`，评论改口为"由 lesson-candidate 改为
proposal"，并在 issue 里给了逐条判定（哪些值得做、哪些要决定、以及对 `me_events` 用 `anyOf` 的纠正）。

**已完成（同一天）**：`proposal` 进了 `kind`，五处读取（worker 的 `INTAKE_KINDS`、`scripts/intake_kind.py`、
`scripts/intake_pipeline.py`、stdio 的 `submit_intake.inputSchema.enum`、`docs/mcp-intake-guide.md` 的表）
由 `tests/test_intake_kind_parity.py` 逐处**解析**后比对，正文自述作为旧客户端的兼容路径保留。
顺手发现并修的一处同类漂移：stdio 的 `kind` 枚举**从来没有 `question`**——文档、worker、脚本都是四种，
只有客户端会校验的那份是三处，于是"用本地 server 提问"这件事在会校验 schema 的客户端里根本发不出去。

### 2.9 发版链路里三处"门禁在说错话"（新账，本卷收掉两处）

`3.3.0` 发出去之后逐条核对线上结果，发现三处**报告与事实相反**的地方：

1. **`Publish to MCP Registry` 从 2.50.0 起每次发版都红，而每次 publish 都成功了。** 校验步骤读
   `/v0/servers?search=…` 的 `servers[]`——**一页 30 条**——然后断言"registry 里没有这个版本"。
   实测 3.3.0 在第 2 页、`isLatest: true`。已修：跟随 `metadata.nextCursor`（20 页上限），HTTP 错误与
   "版本不存在"分开报，并且把读了几页写进输出。
2. **`Publish @misaka-net/misakanet-setup` 每次 push main 都生成一个审批请求。** `release`
   environment 有 required reviewer，而 `tag` job 在"release-please 已经建好 tag"这条路径上无条件
   dispatch；npm 早就有那个版本，审批批了也只会 `cannot publish over`。**实测 55 个**（同日手动取消）。
   已修：把"npm 上有没有这个版本"的检查搬到**没有审批门**的 `tag` job，没有才 dispatch；npm 不可达时
   仍然 dispatch（一个多余的审批比一次发不出去的版本便宜）。
3. **`Deploy Cloudflare Worker` 与 `Publish dataset to R2` 会一直挂在审批队列里没人批。** 前者
   10-31 20:09 就挂着，线上 `serverInfo.version` 因此停在 3.0.0 而 main 是 3.2.0；后者从 10-31 05:50
   挂到现在，R2 数据集比 `data/lessons.json` 落后一天多。**这两个需要 owner 点，不是代码问题**。

**更正（同一天晚些时候）**：上面那句原本写的是"没有'挂超过 N 小时就提醒'的东西"——**是错的**。
`approval-watch.yml` 从 2026-09-27 就在做这件事：`status=waiting`、6 小时阈值、单个跟踪 issue、
"集合变化或过阈值就评论"（它自己记着 #2416 正文准确却不通知人的教训，257 条评论都是它发的）。
它**一直在正常工作**，直到今天 11:34 还在评论。真正错的只有两处：

* **触发端**：同一个 npm 版本被 dispatch 了 55 次（§2.9 第 2 条），于是"集合变化"变成 55 次噪音；
* **路由端**：#2416 是 2026-09-28 建的，标签是 `needs-ac`（"这条需要验收标准"——它需要的不是这个），
  所以它从没进过任何人类分诊窗口。已改成 `needs-human-review`（`dependency-vuln-audit.yml` 的
  digest 用的就是这个标签），workflow 建/更新这个 issue 时也会补上。

**判据（替换掉原来那句错的）**：一个"没人看"的现象，先查**已有的观测**是否在工作——它的日志、
它的输出去了哪里、那个输出有没有被路由到人会看的地方。今天差点因为"没东西在盯"而新建第二个
watcher，而第一个一直在响，只是响在一个没人订阅的房间里。

## 3. 可复用的判据（本卷新增）

1. **量门禁必须用门禁自己的命令。** 上一卷数 F841 用的是 `ruff --select F841 scripts/` → 25 处；门禁跑的
   是 `ruff --select F841 .` → **39**（25 + `misakanet/scripts/` 4 + `tests/` 10）。差那 14 处足以让
   "把 F841 加进 SELECT"当场变红。**判据：门禁跑什么，量就用什么；范围写窄了，数字就是假的。**
2. **"算了没用"有四种，只有第一种是删掉就完事。** (a) 纯遗留 → 删；(b) **判据没生效** → 接上
   （`score_lessons` 量了"验证节有没有写预期结果"却不使用，于是 `docs/quality-score.md` 里
   "命令 **和** 预期输出"那一档在只有命令时就给了满分）；(c) **同一规则两个读者** → 合并到一处
   （`clean_pipeline` 的模式列表与内联正则）；(d) **文档承诺、代码没实现** → 删承诺（`verify_task` 的
   `--sandbox` 印在 usage 里，变量没人读）。判的时候先归到这四类里，再动手。
3. **测试钉住一个时钟，就必须让被测函数接受那个时钟。** `test_reputation` 算出 `now = datetime(2026,7,7)`
   却传不进去（`compute_reputation` 自己取 `datetime.now()`），于是它断言的是 CI 当天。给参数一个
   `now=None` 默认值即可，调用方一行都不用改。**判据：测试里出现一个没人使用的固定时间，先假设它是想固定时钟。**
4. **同一函数在同一行出现两次，先怀疑它。** `content_quality_signals(body)["hard"], content_quality_signals(body)["soft"]`
   是同一个调用做两遍、只用一半；F841 抓不到多余的那次调用，但清死的动作会把它暴露出来。
5. **Windows 检出上编辑文件，整篇会变 CRLF。** `git diff --stat` 里"整文件重写"就是这个，不是逻辑改动；
   `git diff --check` **看不出来**（它只查空白错误），要逐文件 `grep -cU $'\r'`。本卷的实际形态：
   35 个文件显示 5385/5412 行改动，归一化行尾后真实改动是 83/110 行。**提交前做这一步，否则 reviewer 看到的是噪音。**
6. **线上重跑通过，不证明"首次路径"也对。** `#4251` 的重跑看起来完美（标签摘对了、评论改口了），
   但那是因为 `pending-review` 那条标签**原本就在**——首次提交的提案会先被加上、再因为删除循环
   拿的是加之前的标签快照而永远删不掉。同一天补的离线用例（标签集合里没有那个标签）才把它照出来。
   **判据：验证一条"摘标签/摘字段"的规则，必须构造一个"它本来不存在"的输入。**
7. **重跑要说自己改了什么。** 分类器的评论守卫原来只问"有没有评论过"，于是规则变了、标签变了，评论还
   停在旧结论上——bot 前后矛盾比不评论更糟，因为读者信任的是那句旧结论。改成按**分类值**判重，
   改口时明写 `from X to Y`。
8. **提交者已经把话说清楚时，别让分类器猜。** `#4251` 正文里写着"这不是失败报告"，分类器却按
   `error`/`fail` 两个词把它判成 bug。新增的规则只认**自述**（外加结构化的 `kind=proposal`）、不认
   "读起来像计划"——后者正是刚判错的那类关键词猜测。**判据：能由提交者声明的东西，就不要从主题词推断。**
9. **读一个 API 之前先问"这个接口一次给几条"。** registry 的校验步骤默认 `servers[]` 就是全部，
   实际是 30 条一页 + `nextCursor`；于是"没有这个版本"其实是"这一页没有"。**判据：分页接口上的
   "不存在"结论，必须先证明你读完了所有页。**
10. **审批门在 job 层时，步骤层的"已经发布就跳过"救不了它。** `misakanet-setup-publish` 的 publish job
    里早就有"npm 已有这个版本就 stand down"的步骤，但那一步跑在人点过"Approve"之后——所以它挡住的
    只是浪费的执行，不是浪费的审批。**判据：要挡审批，判断必须放在没有审批门的那个 job 里。**
11. **同一个事实有第二个 surface 时，让测试去解析第二个 surface，别抄。** stdio 的 11 个工具原本一个
    annotation 都没有，而 worker 的 8 个早就有；现在两张表由 `tests/test_mcp_annotations.py` 逐处解析
    比对（含"写工具不许自称 readOnly"）。**判据：跨 surface 的一致性要靠解析对方的文件，抄一遍就是两份契约。**

## 4. 下一轮入口

1. **发版收尾**：`#4263` 已合并（`3.3.0`，PyPI / npm / GHCR / MCP Registry 都已发；registry 的校验红是
   §2.9 第 1 条那个分页 bug，已修）。`Deploy Cloudflare Worker`（`57068cbb`）还在审批队列里，批了线上
   `serverInfo.version` 才会从 3.2.0 变成 3.3.0。§2.3 那个"发版在等人"的提醒**仍是设计**。
2. **`[Lesson]` 落库**：playbook 已合（`#4292`），队列实测 **24** 条，其中 **11** 条能过门禁、9 条卡 400 字符
   地板、4 条卡命令词表。批量 3 正在跑（worktree `feat/lesson-batch-3`）；跑完还要按 SOP §3 给报料者回执并关单
   ——**回执那一步没人自动化，也最容易漏**。
3. **融合归一化的生产验收**（§2.6）：代码已合（`#4293`），**6 条生产行还没量**。worker 下次部署后跑
   `scripts/bench_production_recall.py` + CJK 集；没改善就 revert `2f7555e0c`。
4. **2026-11-14 前后**：`MISAKANET_CLIENT_ID_PROOF=strict` + 删宽限期措辞，见 §2.4。
5. **365 篇字段回填**（等额度窗口）；AE / Search Console / Colab（文档已给最小步骤，未执行）。
6. **`proposal` 进 `kind` 枚举**（§2.8）：**已完成**，5 处读取由 `tests/test_intake_kind_parity.py` 守着。
7. **审批队列**（§2.9 第 3 条）：观察者（`approval-watch.yml` + #2416）本来就在，已把它路由进
   `needs-human-review`；触发端那 55 次噪音也修了。**剩下的是"点"本身**——`Deploy Cloudflare Worker`
   现在每次发版都会等一次人（release-please 会改 worker 里的版本字面量）。要么接受这个节奏，要么把
   worker 部署挪到不需要人点的路径（只在 tag 上部署），这是 owner 的取舍，不是维护者能自决的。
