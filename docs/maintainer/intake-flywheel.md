# Intake 飞轮：现状、瓶颈与最优配置

> 2026-11-02 实测。回答两个问题：**现在能不能自动跑**，以及**要让它自动跑，最小改动是什么**。

## 1. 现状：进来的量远大于出去的量

| 量 | 数值 | 怎么量的 |
|---|---|---|
| 累计 intake（`mcp-intake`，500 条上限） | 500 | `gh issue list --state all --label mcp-intake` |
| 最近五周每周新增 | 97 / 44 / 82 / 114 / 150 | 按 `createdAt` 的 ISO 周聚合 |
| 当前 open | 172 | `--state open` |
| 其中 `## Problem` / `## Root Cause` / `## Fix` | 128 / 37 / 110 | `intake_lesson_to_file.section()` |
| **三个都齐（转换器唯一需要的形状）** | **0** | 同上 |
| 转换器现在能直接转的 | **1 / 172** | `convert()` 干跑 |

**结论：不是队列没人管，是形状对不上。** 每周进 100+ 条，能自动转的 0 条——队列只会更长。

> **2026-11-16 更新：形状这一关已经过去了。** 同一份干跑对当时的 183 条 open intake 给出
> **convertible 73**（40%），跳过 110 条里 97 条正是缺 Problem/Root Cause/Fix。所以 §2 的 ①
> 仍然是瓶颈，但不再"一条都转不了"——现在的瓶颈换成了**每周一次 + 每批一刀人工**（见 §4 L2）。
> 来源：`python3 scripts/convert_intake_batch.py --limit 300`。

## 2. 瓶颈在哪一段

一条 intake 走到"成为课程 + 回执 + 关单"，有四段：

| 段 | 现状 | 成本 |
|---|---|---|
| ① 形状（提交时） | **全部**缺 `## Root Cause` | 改提示词，0 |
| ② 转换（issue → 文件） | 工具齐了，但只能吃 ① 的产物 | 0（确定性） |
| ③ 门禁 + 合入 | 已有 `lesson_gate` + `Auto-Merge Lessons` | 0 |
| ④ 回执 + 关单 | 2026-11-02 起自动（`emit_intake_receipt.py --close`） | 0 |

②③④ 都是零成本、已有或今天刚接通的。**唯一的瓶颈是 ①，而且它不在代码里**。

## 3. 为什么 ① 是瓶颈：表单没要那一节

`misakanet_submit_intake` 的产物（`workers/register-proxy-sw.js:5099-5108`）：

```
**Kind:** missing_lesson
## Problem        ← 一段自由文本
## Error          ← 可选
## What was tried ← 可选
## Fix (if known) ← 可选
## Verification   ← 可选
```

没有 `## Root Cause`，而 `intake_lesson_to_file.convert()` 要求 Problem/Root Cause/Fix 三节齐全。
今天给转换器加了 `split_intake_problem()`：按提交者自己写的标记（`根因`/`修复`）把那段话**原句切分**
到三节——164 条里只有 16 条达到标准。**能切分的是措辞，切不出来的是提交者压根没写的原因。**

## 4. 最优配置（按杠杆排序）

### L0 · 先别让"不是报告的东西"进来（2026-11-16 已做）

一个扫描器把 16 条 payload 当 lesson submission 提了进来（`' OR 1=1--`、`../../../../etc/passwd`、
`Scanner Payload`、`security_test_123`…，两批：#4703–#4714、#4819–#4827）。它们**什么都没破坏**——
值是文本，从没拼进 SQL、路径或响应——但全部落在 `pending-review`，那个队列于是从 3 条真实项变成 19 条。

现在 `intake_auto_review.detect_payload_submission()` 给这类提交一个独立决定 `payload`：
`intake-auto-review.yml` 发一条说明（值被当文本存了、没坏、要 reopen 就补上观测/根因/验证）、
打 `not-a-lesson`、**关闭**。不进 `auto-rejected`，因为每日 salvage digest 会把那个标签捞回
`needs-human-review`——同一个回环，`placeholder` 分支当初就是为这个才单独存在的。

判据是两个信号同时成立：**攻击语法或自我声明**（标题/`Domain:`/`Title:` 字段里的 `' OR 1=1`、`../../`、
`<script>`、`Source: generated-payload`…）**且**没有任何报告证据（代码块、traceback、版本号、堆栈、错误码）。
实测：真实 payload 19 条抓 16 条，377 条 open intake 里**误判 0 条**——刻意放过的那 3 条没有攻击语句
（`SSRF to Internal Metadata`、`Access to <PATH>`、`System unexpectedly allows unauthorized access`），
宁可漏也不肯把真报告关掉。

### L1 · 改表单，让 ① 产出可转换的形状（0 成本，收益最大）

在 `submit_intake` 的 `problem` 说明里加一句结构约定：

> 如果已知根因/修复，请在 `problem` 里用 `## Root Cause` / `## Fix` 分节写出来；不知道就只写现象，
> 我们会把它当作"待补根因"排在队列里，而不是硬转。

预期：**110 条有 Fix、37 条有 Root Cause** 的 intake 会变成三节齐全 → 可转换比例从 ~1% 升到 50-60%。
这是唯一能让队列下降的改动。

### L2 · 批量转换做成定时任务（1 个 workflow）

`intake-batch-convert.yml`，每日一次：

1. `gh issue list --label mcp-intake --state open` → JSON；
2. `scripts/convert_intake_batch.py`（本文件配套）——推断 domain、`convert()`、去重、写文件，
   打印 `converted=N skipped=M by reason`；
3. 有产物就开分支 + PR，打 `auto-merge-lesson` 标签；
4. `Auto-Merge Lessons` 在机械条件满足时合并（已有）；
5. `update-lessons.yml` 当日/次日发回执并关单（今天已接上）。

**只有当 L1 落地后才值得开**：形状不改，每天开的都是空 PR。

### L3 · 剩下的交给模型（可选的兜底）

L1 之后仍有一批"没写根因"的。两条路：

| 选项 | 成本 | 说明 |
|---|---|---|
| Workers AI（脚本默认 provider） | **0**（含在 Workers Paid） | 需 `CLOUDFLARE_API_TOKEN` 带 AI 权限 |
| 外部 API（deepseek-chat 价） | **约 $0.23**（679k in + 103k out） | 需自备 key |

**不要把模型放在 L1 前面**：模型能补的是"写法"，补不了"这个人当时看到了什么"。先让提交者把话说全，
剩下的才轮到生成。

## 5. 这套配置的失败模式（写下来免得下次再踩）

| 失败模式 | 症状 | 判据 |
|---|---|---|
| 转换器吃不到某节 | 队列只涨不消 | `convert()` 的 skip 直方图 |
| 回执字段对不上 | 发了回执没人收到 | `emit_intake_receipt.py` 的 scan 数（2026-11-02 前一直是 0：找 `contrib_id`，而 330 篇课写的是 `provenance.issue`） |
| 关单没接上 | 回执发了 issue 还开着 | issue 的 `state`（今天之前全靠人工） |
| 空 PR 天天开 | Actions 列表噪声 | PR 里 `lessons/` 文件数 = 0 就该不建 PR |

### 裸提三次以上的散文词：**故意**不自动放行（2026-11-21 决定）

批次现在能转的比例从 11% 提到 25%（`#5505`），剩下的 75 条里 **20 条**卡在同一处：门禁把
"**裸提三次以上**的词"当命令名（`command_surface_identifiers()` 的 `count >= 3` 那条）。被拦的词分两类：

- 普通英文词在散文里重复：`arrival`、`vacancy`、`wlan`、`checked-in`；
- 标识符形状：`skillspector`、`select_source`、`ship_weight`、`krlerr5`——**这一类拦得对**。

试过、但**决定不做**的两条路：

| 想过 | 为什么不做 |
|---|---|
| 把词表从"代码段词"扩到"散文词" | 那条"裸提三次"规则存在的理由就是 `mico issue rerun` 这种没有 flag 的内部命令名；散文词全放行等于把它拆了 |
| 自动给这些课加 `public_analogue` | 那个字段的含义是"内部名的公开等价物"，拿来写"这只是散文"会把它变成 "ignore the gate" 的后门 |

所以这 20 条留在 `needs-human-review`，人写课时顺手把句子改成不像命令（或确认它是公开工具、进 allowlist）。
判据：一个词如果**读者会去搜它**，它就是名字；`visit` 不会，`skillspector` 会。

#### 2026-11-22 复测：这条决定现在缺一个执行者，而且拦错的比例可测

同一条判据、同一段代码，隔一天再跑一遍（`convert_intake_batch` 的 dry run + 门禁逐条）：

| 量 | 2026-11-21 | 2026-11-22 | 怎么量的 |
|---|---|---|---|
| open intake 扫描数 | 77 | 77 | 批次的 `scanned` 行 |
| 公共面被拦 | 20 | **24** | `would fail the lesson gate (public surface)` |
| 被拦的**词** | 27 | **34** | 逐条 `unknown_surface_names()` |

一天之内多出四条，而批次的 `convertible` 一直是 1 —— 因为这条决定依赖的那件事（**一个人去把它们转成课、
顺手把句子改掉**）没有队列、没有标签、没有归属。它们和别的 intake 一样挂着 `needs-human-review`，
于是没有任何东西记得：这是机器**故意**不碰的那一堆。

而被拦的词大部分**不是**这条规则当初针对的情况。把 34 个词按“它是什么”分类（逐个看 24 条报告，
这是我的判断，不是机器判的）：

| 形状 | 数量 | 例子 | 该不该拦 |
|---|---|---|---|
| 真标识符 | 9 | `model_provider`、`remote_control`、`requires_openai_auth`、`ship_weight`、`krlerr5` | **对** |
| 公开可搜的工具名 | 4 | `ss-server`、`select_source`、`bru`、`bruno` | 拦得对，但该进 allowlist |
| 普通英文 / 散文复合词 | **21** | `arrival`、`lights`、`wlan`、`vacancy`、`exhaust`、`scalar`、`checked-in`、`scientific-notation` | **拦错了** |

也就是说 34 个词里 **21 个（62%）**是散文，不是名字。`arrival` 在一条课里出现 3 次是因为那是个业务字段，
不是一条命令。这个比例是**判据层面的证据**，不是又一条“更省事的路”：它说明“散文词不进词表”与“裸提三次算命令”
这两条规则叠在一起时，命中率主要落在散文上；要改的是**计数那一步**（例如裸提只在标识符形状上计数，
或要求该词至少有一次出现在命令位：`$` 提示符、带 fence 语言标签的块、或跟 flag），而不是把词表扩到散文。

两条补充读数，放在这里免得下次重新测：

- **`## 背景` 形状是历史遗留。** 最近 60 条 intake（11-20 起）里 0 条用旧客户端的 `## Problem` + `## 背景`
  嵌套写法；那 10 条是 10 月底之前进来的，不要为它们加转换器别名。
- **L1 那段提示词是有效的。** 11-02 测的 `## Root Cause` 覆盖是 37/172（21.5%）；11-22 最近 60 条是
  **23/60（38%）**。今天一次批次能转 1 条，不是因为人不写原因了，而是因为剩下的这批人写了原因、
  却被公共面那条门禁挡住。

## 6. 今天已经落地的部分

- ④ 回执 + 关单自动化（`#4333`）；
- ② 转换器修了 `## Fix (if known)`、围栏、页脚、slug 字节上限（`#4322`/`#4330`）；
- L3 的确定性替代：`backfill_structured_fields.py --provider derived` 给 348 篇补了结构化字段（0 成本，`#4344`）。

**下一步就是 L1 那一段提示词。** 它改完，L2 的 workflow 才有意义。
