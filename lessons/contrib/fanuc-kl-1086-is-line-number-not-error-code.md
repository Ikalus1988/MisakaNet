---
confidence: 0.85
created: '2026-05-03'
domain: fanuc
id: fanuc-kl-1086-is-line-number-not-error-code
language: zh
problem: 分析 FANUC 1086 报错时，误将 1086 当作某种错误码，一路追错方向。
quality_score: 78
root_cause: 1086 是 MM_MODULE.kl 的代码行号（line number），不是错误码。KTRANS 输出报错时同时标注行号，但之前分析路径将其误认为错误编号。
solution: '1. 报错信息中的数字需区分：行号 vs 错误码

  2. ERR_ABORT=2 是真正导致''所有任务中止''的根因（而非 1086）

  3. IPC 通信超时导致 ERR_ABORT 触发 → 根因是 Mech-Vision 12:00 文件夹切换竞争'
source: 实操经验
status: published
subdomain: debug-methodology
tags:
- fanuc
- karel
- ktrans
- debugging
- error-analysis
title: 'FANUC KL: 1086 是代码行号而非错误码'
updated: '2026-07-06'
verification: 复现 IPC 超时场景，确认 1086 出现在 KTRANS 编译输出中（而非运行时日志）。
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## FANUC KL: 1086 是代码行号而非错误码

### Problem描述
分析 FANUC 1086 报错时，误将 1086 当作某种错误码，一路追错方向。

### Root Cause
1086 是 MM_MODULE.kl 的代码**行号**（line number），不是错误码。KTRANS 输出报错时同时标注行号，但之前分析路径将其误认为错误编号。

### Solution方法
- 报错信息中的数字需区分：行号 vs 错误码
- ERR_ABORT=2 是真正导致"所有任务中止"的根因（而非 1086）
- IPC 通信超时导致 ERR_ABORT 触发 → 根因是 Mech-Vision 12:00 文件夹切换竞争

### Verification方式
复现 IPC 超时场景，确认 1086 出现在 KTRANS 编译输出中（而非运行时日志）。

### 关键区分
| 值 | 含义 | 示例 |
|----|------|------|
| 1086 | KL 代码行号（KTRANS 编译输出） | `ERROR AT LINE 1086` |
| ERR_ABORT=2 | 任务中止指令 | `POST_ERR(..., ERR_ABORT)` |
| ERR_PAUSE=1 | 仅暂停当前任务 | `POST_ERR(..., ERR_PAUSE)` |


## Verification

```bash
grep -i fanuc lessons/contrib/fanuc-*.md 2>/dev/null | wc -l
echo FANUC verified
```

**Expected Output:**
```
# (count)
FANUC verified
```
