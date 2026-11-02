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

## 6. 今天已经落地的部分

- ④ 回执 + 关单自动化（`#4333`）；
- ② 转换器修了 `## Fix (if known)`、围栏、页脚、slug 字节上限（`#4322`/`#4330`）；
- L3 的确定性替代：`backfill_structured_fields.py --provider derived` 给 348 篇补了结构化字段（0 成本，`#4344`）。

**下一步就是 L1 那一段提示词。** 它改完，L2 的 workflow 才有意义。
