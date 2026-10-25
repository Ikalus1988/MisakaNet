# 门禁变异抽查 —— 这些门禁还**能红**吗？（#2045，#3837）

> 脚本：`scripts/gate_mutation_audit.py` · 测试：`tests/test_gate_mutation_audit.py`
> 接线：`.github/workflows/gate-mutation-audit.yml`（**每个 PR + 每周定时 + 手动**；PR 触发是 #3837 加的）
> 硬门清单：`docs/ci-gates.md` 的 *Hard Gates (must pass)* 表（脚本运行时解析，仓库里没有第二份清单）
> 落地日期：2026-09-22 · 覆盖全部硬门：2026-10-25（#3837）

## 为什么需要它

2026-09-21 一天之内，本仓找到 **4 处"看起来是门禁、其实永远不会红"**：

| # | 现象 | issue |
|---|---|---|
| 1 | 跨平台矩阵 8 条腿**一条测试都没跑**，仍然打印 ✅ | #2006 / #2008 |
| 2 | 工具计数徽章 grep 的正是它自己守护的那个文件 | #1822 |
| 3 | 26 条测试里有 **23 条**在生产代码回滚后依然通过 | #1999 |
| 4 | 断言环境属性（`PATH=/usr/bin:/bin`，在 CI runner 上恒真）的测试 | #2002 |

这不是四次意外，是一种**结构性的失效模式**：不能失败的门禁比没有门禁更糟——它对坏输入报 ✅，
并顺手消除了本来会发现问题的那份怀疑。

所以本仓采取的做法是：**故意证明门禁能红，并把这份证明放进仓库**，而不是留在某个人的习惯里。
这个脚本就是那份证明。

## 覆盖了哪些门禁

硬门清单不写在这里：`hard_gates()` 每次运行都从 `docs/ci-gates.md` 的硬门表解析，每个条目用
`Gate.check` 声明它证明的是哪个 required-status-check context。全量运行若发现表里有 context
没有对应变异，脚本直接失败（`--gate` 子集运行明确不声称覆盖率）。`--list-gates` 打印这份映射：

```bash
python3 scripts/gate_mutation_audit.py --list-gates
```

| 门禁条目 | 证明的硬门 context | 判据在哪（真正执行的是什么） | 变异（故意改坏的东西） |
|---|---|---|---|
| `lesson-gate` | `gate` | `scripts/lesson_gate.py` | 删掉 frontmatter 的 `title:` 行；把 `domain:` 改成不在 `data/domains.json` 里的值；把 `## Root Cause` 标题改名 |
| `dco` | `DCO / Signed-off-by` | `.github/actions/dco-audit/action.yml` 的 `Scan DCO` step，跑**真实 git 历史** | tip commit 去掉 `Signed-off-by:`；**中间** commit 去掉而 tip 已签（只读 HEAD 的写法会漏） |
| `pytest-leg` | `test (ubuntu-latest, 3.11)` | `ci-cross-platform.yml` 的 `Run Tests` + `Verify test outcome` 两步，跑**真实 pytest** | 失败测试（exit 1）；collection error（exit 2）；一个测试都收集不到（exit 5，见 #2006/#2008） |
| `audit-secret-scan` | `audit` | `pr-checks.yml` 的 `Secret Scan` step，跑**两个真实扫描器**扫临时树 | workers 里种 GitHub token；`docs/` 里种 node token（#1982 那一面） |
| `audit-worker-suite` | `audit` | `pr-checks.yml` 的 `node --test 'workers/**/*.test.mjs'` step | 让一条 worker 测试失败 |
| `audit-coverage-floor` | `audit` | `pr-checks.yml` 的 `pytest --cov-fail-under=`（装了 `pytest-cov` 就真跑插件，否则按**同一个数字**做判据级比较） | 把覆盖率压到 floor 以下 |
| `provenance-gate` | **不是硬门**（见下） | `scripts/check_provenance.py` | 引用伪造来源；把同一来源藏进 JSON 风格 frontmatter；E3 却完全无来源；引用 404 仓库（**需要网络**） |

`audit` 是唯一由三条条目覆盖的硬门：它本身是一个复合 verdict（secret scan、依赖审计、worker
套件、覆盖率门槛都在同一个 job 里）。拆开证明每个判据，比笼统地"证明 audit 能红"更有用——
issue 也指出，它是硬门里最重的一个。

### 真变异 vs 判据级 stub

- **真变异**：门禁自己的可执行文件/步骤被真的跑起来——`lesson_gate.py`、`check_provenance.py`、
  dco-audit 的 `Scan DCO`、test leg 的 `Run Tests` + `Verify test outcome`、audit job 的
  `Secret Scan` 与 `node --test`。workflow 不是"按名字声称"的：step body 用 `yaml.safe_load`
  读出来、`${{ … }}` 严格替换后交给 bash 执行，所以**删掉判据（`5) … exit 1`、
  `Signed-off-by:` grep、coverage floor）这个突变就会变绿**——这正是要抓的东西。
- **判据级 stub（只有一处）**：`audit-coverage-floor`。floor 数字从 `pr-checks.yml` 的
  `--cov-fail-under=` 读、包名从 `--cov=` 读；装了 `pytest-cov` 就跑真插件，没装（比如没装插件
  的本机）就打印 `modelled comparison` 再做同一个比较。它变异的是"覆盖率门槛这条判据"，
  **不是产品代码**，报告里会写明当时走的是哪条路。

`provenance-gate` **不在硬门表里**，保留它是因为：它是唯一会去看"课程引用的来源是否真的存在"的
门禁（`lesson_gate.py` 只看结构，从不取 URL），而它不能阻塞合并——**正好是那种悄悄坏掉、没人发现
的类型**。证明它还能红，比多证明一个必过门更接近这个机制的初衷。

判读方式只有两种结果：

* **红** = 门禁仍能失败，符合预期（这才是"通过"）；
* **绿** = 门禁无法失败 → 脚本打印 `cannot fail` 并**非零退出**，点名是哪个门禁。

审计以非零退出覆盖另外三种"证明不了"的情况：变异**没生效**（正则没匹配上 / 文件字节未变）、
基线样本**本来就是红的**（那红/绿都说明不了什么）、门禁**卡死**。workflow 驱动的门禁还有第四种：
判据**找不到或无法执行**（step 改名、输入缺值、扫描器崩了、没有 bash）时 driver 返回保留码 3，
审计仍以 1 退出，但报告写的是 `criterion could not be evaluated` —— **不算红**。把"判不出来"
读成"门禁能失败"，是这个机制最危险的假绿。

### 边界（写清楚，免得被当成全能门禁）

- **变异只发生在临时目录**（`tempfile.TemporaryDirectory`，`/tmp` 下），脚本在变异前后都断言
  目标路径**不在仓库内**；仓库里的课程/门禁文件一个字节都不会动。
- 复制出来的样本落在仓库之外，所以 `lesson_gate.py` 会对它套用**新增课程的严格档**（必需章节、
  ≥400 字符、#1783 结构化字段）。这正是 CI 对 `git diff --diff-filter=A` 的**新文件**套的那一档；
  **改已有课程**走的是 advisory 档，不在抽查范围内。
- `dead-source` 需要网络：离线时它是 `unknown`，而 provenance 门禁**只凭证据失败、不凭缺少证据失败**，
  所以默认跳过，`--online` 才跑。工作流里它是 `continue-on-error: true` 的**只报告**步骤——网络抖动、
  限流、5xx 都会读成 `unknown`，这一档的"绿"本身有歧义。
- **没有 frontmatter 的课程**，provenance 门禁看不到（`scan()` 直接跳过，exit 0）。那不是它的活：
  那一类由 lesson-gate 以"missing required field"拦下。跨门禁的空白记在这里，谁要补都得先补测试。
- workflow 驱动的突变执行的是 **step body，不是 GitHub Actions 运行时**：step 的 `if:`、job 级
  `continue-on-error`、规则集成员资格都不在覆盖内——它们由 `tests/test_ci_runs_what_it_claims.py`、
  `tests/test_workflow_pins.py` 与 weekly ratchet（`scripts/check_documented_gates.py`）负责。
- `audit` 的 **verdict block 本身不执行**（那串 `exit 1` 和报告生成交织在一起）：我们证明的是
  喂给它的判据；"红的判据会传到 job verdict"由 `tests/test_ci_runs_what_it_claims.py` 钉住。
- 它**不检查外部动作是否被 pin、不检查 workflow 是否真被调用**——那些是
  `tests/test_workflow_pins.py`、`tests/test_workflow_inventory.py` 的地盘。

## 怎么加一个门禁（或一个变异）

1. 选一个**廉价、离线、可判定**的目标，有两种形态：
   - **独立脚本**门禁：读一个文件、退出码有意义（0 通过 / 非零失败）；
   - **判据在 workflow 里**：用 `_workflow_step_body(workflow, job, step_name)` 把那个 step 的
     `run:` body 取出来，能在一个临时目录里把它跑出 0/1。

   跨平台矩阵那种"要跑 8 条腿才有结论"的整体不适合；但**required leg 的判据 step** 可以——
   `pytest-leg` 只跑一次 pytest，不是跑 8 条腿。
2. 写 `_mutate_xxx(路径) -> None` 改坏样本。**改不到就抛 `MutationError`**——静默没生效的变异会被
   报成"门禁不能失败"，那是冤枉。需要整块重写 frontmatter 时（例如 JSON 风格那个变异）直接
   读/写文件，别让正则凑合。
3. 在 `GATES` 里加一条 `Gate(...)`：
   - `check=` 填 `docs/ci-gates.md` 硬门表里的 context 原文；**非硬门填 `None` 并写 `why=`**，
     说清为什么仍值得证明；
   - `prepare` 决定拿什么**有效样本**（默认是
     `BASELINE_LESSON = lessons/contrib/docker-build-exit-137-multistage-oom.md`，它必须通过严格档）；
   - 独立脚本用 `command(路径, online)`；workflow 驱动用 `_workflow_gate_command("新名字")`，
     并在 `_DRIVERS` 里注册对应的 `_drive_xxx`。
4. 别把门禁的**判据**和它的**落点**分开：`_drive_*` 里用 `_require_text(...)` 钉住"谁的 false
   会让它变红"（例如 pr-checks 的 `dco-passed == 'false'`）。判据搬家时它会红，而不是悄悄证明
   一条已经不再阻塞合并的规则。
5. 在 `tests/test_gate_mutation_audit.py` 里确认它真的红（`test_audit_passes_for_the_current_gates`
   会遍历 `GATES`，所以加完自动进网）。
6. 本地验收：

   ```bash
   python3 scripts/gate_mutation_audit.py --gate <新门禁名> -v
   python3 scripts/gate_mutation_audit.py --list-gates
   python3 -m pytest tests/test_gate_mutation_audit.py -q -p no:randomly
   ```

7. **加 workflow 文件的门禁还要补 `docs/CI.md` 的索引表行**（只改触发/新增行，别顺手改别人的行），
   否则 `tests/test_workflow_inventory.py::test_the_ci_inventory_equals_the_workflow_directory` 会红。

选择样本课程（`BASELINE_LESSON`）时的坑：它必须通过严格档。仓库形状也有用——
`lessons/<子目录>/<名>.md` 这个形状会让 lesson-gate 只对"课程树里的文件"套用严格档，
而且同 stem 的文件被当作翻译镜像，所以复制一份不会撞上重复标题检查（否则误报）。

## 多久跑一次 · 谁负责

| 项 | 值 |
|---|---|
| 频率 | **每个 PR** + **每周一 06:43 UTC**（`cron: '43 6 * * 1'`，与 `provenance-gate.yml` 的 06:17、ratchet 的 07:11 错开）+ `workflow_dispatch` |
| **为什么现在在 PR 上跑** | 能让门禁失去牙齿的改动**本身就是 PR**（#3837）。只跑周审计时，这种改动最多要等一周才被发现，这中间所有合并都在一个不会说"不"的门禁后面跑。跑在 PR 上，作者和 reviewer 在合并前就看到红 |
| 成本 / 权限 | 单 job、无矩阵、约 1–2 分钟；`concurrency` 取消被覆盖的 push；`permissions: contents: read`、无 secret，fork PR 也安全。它**不在规则集里**，所以红了是提示、不是阻塞——阻断合并靠 required 的那几项 |
| 手动 | `workflow_dispatch`（改完门禁、加完变异当场验一次） |
| 责任人 | **维护者**（当前只有 @Ikalus1988；本仓 bus factor = 1，见 `docs/maintainer/backlog-and-growth-2026-09-20.md`） |
| 通知 | 定时任务失败时 GitHub 会通知仓库维护者。**但通知不是责任人**：这条写在这里，就是为了在通知静音的情况下仍有一个人负责 |

**红了怎么处置**（按顺序，别跳过第 3 条）：

1. 看日志点名的是哪个门禁、哪个变异——`cannot fail` 那一行就是结论。如果失败信息是
   **hard gate(s) … with no mutation**，那是有人在 `docs/ci-gates.md` 加了硬门却没加变异。
2. 门禁确实写错了 → 修门禁（这才是设计意图：让"不能失败的门禁"在变成事故之前被抓住）。
3. 门禁**已经没意义了**（守护的对象消失、规则被别的门禁覆盖）→ **删掉它**，连同它的变异一起删。
   一个没人信的门禁会教大家忽略门禁。
4. 是**变异失效**了（样本课程被改/被删、标题改名、step 改名）→ 更新变异或 `BASELINE_LESSON`，
   不要放宽断言。判据找不到时脚本报的是 `criterion could not be evaluated`，不是红。
5. **不要靠重跑让它变绿**。连续 2 次（PR 或周审计）红了却没人处置，就把被点名的门禁当作
   **不存在**：在合并判断里不再引用它的 ✅，并开一条 issue 记这个决定。

## 复现（2026-10-25 实测）

```bash
python3 scripts/gate_mutation_audit.py
# hard gates: 4/4 covered — the list is parsed from docs/ci-gates.md, not repeated here
# mutation audit: 7 gate(s), 16 mutation(s) — 15 red (as required), 1 skipped (network), 0 that did not prove the gate can fail
# mutation audit: OK — every covered gate still goes red when the thing it guards is broken   → exit 0

python3 scripts/gate_mutation_audit.py --list-gates
# 7 条门禁 → 各自的 context（4/4 covered）；provenance-gate 标 "not a hard gate"；exit 0

python3 scripts/gate_mutation_audit.py --gate provenance-gate --online
# 4 red (as required)  → dead-source 也确认红了（HTTP 404）

python3 -m pytest tests/test_gate_mutation_audit.py -q -p no:randomly   # 20 passed
```

## 已知接续事项（2026-10-25）

- `docs/CI.md` 的索引行要跟着触发变化走（`gate-mutation-audit.yml` 的触发列现在是
  `PR, 定时, 手动`）。新增 workflow 文件时这一步**不是可选项**，否则
  `tests/test_workflow_inventory.py::test_the_ci_inventory_equals_the_workflow_directory` 会红。
- **硬门已全部覆盖**（4/4）：抽查范围是 **7 个门禁 / 16 个变异**，其中 1 个需网络。
  剩余候选都是**非硬门**：工具计数（`scripts/sync_lesson_count.py --check`，对应 #1822 ——
  它是"自指徽章"那类缺陷的现场）与 `scripts/injection_scan.py`；两者都廉价离线，加进来的成本
  就是上面那几步。
- 判据级 stub 只剩**覆盖率门槛**一处：装了 `pytest-cov` 的 CI 上它是真变异，本机没有插件时才是
  建模比较。要消灭最后一个 stub，得让 `pytest-cov` 成为本机也默认安装的测试依赖。
