# 门禁变异抽查 —— 这些门禁还**能红**吗？（#2045）

> 脚本：`scripts/gate_mutation_audit.py` · 测试：`tests/test_gate_mutation_audit.py`
> 接线：`.github/workflows/gate-mutation-audit.yml`（**每周定时 + 手动**，刻意不挂在 PR 上）
> 落地日期：2026-09-22

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

| 门禁 | 脚本 | 变异（故意改坏的东西） | 期望 |
|---|---|---|---|
| `lesson-gate` | `scripts/lesson_gate.py` | 删掉 frontmatter 的 `title:` 行 | 非零退出 |
| | | 把 `domain:` 改成不在 `data/domains.json` 里的值 | 非零退出 |
| | | 把 `## Root Cause` 标题改名（缺必需章节） | 非零退出 |
| `provenance-gate` | `scripts/check_provenance.py` | 引用伪造来源（`https://github.com/<owner>/<repo>/issues/1`） | 非零退出 |
| | | 把同一条伪造来源藏进 **JSON 风格 frontmatter**（2026-09-16 红队盲区） | 非零退出 |
| | | 引用 2026-09-16 事故里那个 404 仓库（**需要网络**） | 非零退出 |

判读方式只有两种结果：

* **红** = 门禁仍能失败，符合预期（这才是"通过"）；
* **绿** = 门禁无法失败 → 脚本打印 `cannot fail` 并**非零退出**，点名是哪个门禁。

同一个退出码也覆盖另外三种"证明不了"的情况：变异**没生效**（正则没匹配上 / 文件字节未变）、
基线样本**本来就是红的**（那红/绿都说明不了什么）、门禁**卡死**。

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
- 它**不检查外部动作是否被 pin、不检查 workflow 是否真被调用**——那些是
  `tests/test_workflow_pins.py`、`tests/test_workflow_inventory.py` 的地盘。

## 怎么加一个门禁（或一个变异）

1. 选一个**廉价、离线、可判定**的目标：门禁读一个文件、退出码有意义（0 通过 / 非零失败）。
   跨平台矩阵那种"要跑 8 条腿才有结论"的不适合放进每周审计。
2. 在 `scripts/gate_mutation_audit.py` 里写两个小函数：
   * `_mutate_xxx(lesson: Path) -> None`：用 `_sub(...)` 改坏样本。**改不到就让 `_sub` 抛
     `MutationError`**——静默没生效的变异会被报成"门禁不能失败"，那是冤枉。
   * 需要整块重写 frontmatter 时（例如 JSON 风格那个变异）直接读/写文件，别让正则凑合。
3. 在 `GATES` 里加一条 `Gate(...)`：`prepare` 决定拿什么**有效样本**（默认是
   `BASELINE_LESSON = lessons/contrib/docker-build-exit-137-multistage-oom.md`，它必须通过严格档），
   `command(lesson, online)` 决定怎么调用门禁。需要网络的变异写 `network=True`。
4. 在 `tests/test_gate_mutation_audit.py` 里确认它真的红（`test_audit_passes_for_the_current_gates`
   会遍历 `GATES`，所以加完自动进网）。
5. 本地验收：

   ```bash
   python3 scripts/gate_mutation_audit.py --gate <新门禁名> -v
   python3 -m pytest tests/test_gate_mutation_audit.py -q -p no:randomly
   ```

6. **加 workflow 文件的门禁还要补 `docs/CI.md` 的索引表行**，否则
   `tests/test_workflow_inventory.py::test_the_ci_inventory_equals_the_workflow_directory` 会红。

选择样本课程（`BASELINE_LESSON`）时的坑：它必须通过严格档。仓库形状也有用——
`lessons/<子目录>/<名>.md` 这个形状会让 lesson-gate 只对"课程树里的文件"套用严格档，
而且同 stem 的文件被当作翻译镜像，所以复制一份不会撞上重复标题检查（否则误报）。

## 多久跑一次 · 谁负责

| 项 | 值 |
|---|---|
| 频率 | **每周一 06:43 UTC**（`cron: '43 6 * * 1'`，与 `provenance-gate.yml` 的 06:17 错开） |
| 手动 | `workflow_dispatch`（改完门禁、加完变异当场验一次） |
| **不在 PR 上跑** | 变异很慢且没有 PR 相关性：它回答的是"这个门禁还有能力失败吗"，变化尺度是**月**不是提交。放进每个 PR 只会花掉几分钟去重答上一个 PR 已经答过的问题，而**慢的 advisory 检查等于会被跳过的检查**（issue 原话：变异很慢，属于周期性审计） |
| 责任人 | **维护者**（当前只有 @Ikalus1988；本仓 bus factor = 1，见 `docs/maintainer/backlog-and-growth-2026-09-20.md`） |
| 通知 | 定时任务失败时 GitHub 会通知仓库维护者。**但通知不是责任人**：这条写在这里，就是为了在通知静音的情况下仍有一个人负责 |

**红了怎么处置**（按顺序，别跳过第 3 条）：

1. 看日志点名的是哪个门禁、哪个变异——`cannot fail` 那一行就是结论。
2. 门禁确实写错了 → 修门禁（这才是设计意图：让"不能失败的门禁"在变成事故之前被抓住）。
3. 门禁**已经没意义了**（守护的对象消失、规则被别的门禁覆盖）→ **删掉它**，连同它的变异一起删。
   一个没人信的门禁会教大家忽略门禁。
4. 是**变异失效**了（样本课程被改/被删、标题改名）→ 更新变异或 `BASELINE_LESSON`，不要放宽断言。
5. **不要靠重跑让它变绿**。周审计连续 2 周红了却没人处置，就把被点名的门禁当作**不存在**：
   在合并判断里不再引用它的 ✅，并开一条 issue 记这个决定。

## 复现（2026-09-22 实测）

```bash
python3 scripts/gate_mutation_audit.py
# mutation audit: 2 gate(s), 6 mutation(s) — 5 red (as required), 1 skipped (network), 0 that did not prove the gate can fail
# mutation audit: OK — every covered gate still goes red when the thing it guards is broken   → exit 0

python3 scripts/gate_mutation_audit.py --gate provenance-gate --online
# 3 red (as required)  → dead-source 也确认红了（HTTP 404）

python3 -m pytest tests/test_gate_mutation_audit.py -q -p no:randomly   # 11 passed
```

## 已知接续事项（2026-09-22）

- `docs/CI.md` 的索引行已补上（格式：`文件名 | 名称 | 触发 | cron`）。这一步**不是可选项**：
  新增任何 workflow 文件都要同时补这一行，否则
  `tests/test_workflow_inventory.py::test_the_ci_inventory_equals_the_workflow_directory` 会红。
- 抽查范围目前是 **2 个门禁 / 6 个变异**（issue 要求 3–5 个门禁）。下一个候选是工具计数
  （`scripts/sync_lesson_count.py --check`，对应 #1822：它是"自指徽章"那类缺陷的现场）与
  `scripts/injection_scan.py`；两者都廉价离线，加进来的成本就是上面那 5 步。
