---
title: FANUC KL: 1086 是代码行号而非错误码
domain: fanuc
subdomain: debug-methodology
source: bootstrap
status: draft
confidence: 0.7
created: 2026-05-03
---

## FANUC KL: 1086 是代码行号而非错误码

### 问题描述
分析 FANUC 1086 报错时，误将 1086 当作某种错误码，一路追错方向。

### 根因
1086 是 MM_MODULE.kl 的代码**行号**（line number），不是错误码。KTRANS 输出报错时同时标注行号，但之前分析路径将其误认为错误编号。

### 修复方法
- 报错信息中的数字需区分：行号 vs 错误码
- ERR_ABORT=2 是真正导致"所有任务中止"的根因（而非 1086）
- IPC 通信超时导致 ERR_ABORT 触发 → 根因是 Mech-Vision 12:00 文件夹切换竞争

### 验证方式
复现 IPC 超时场景，确认 1086 出现在 KTRANS 编译输出中（而非运行时日志）。

### 关键区分
| 值 | 含义 | 示例 |
|----|------|------|
| 1086 | KL 代码行号（KTRANS 编译输出） | `ERROR AT LINE 1086` |
| ERR_ABORT=2 | 任务中止指令 | `POST_ERR(..., ERR_ABORT)` |
| ERR_PAUSE=1 | 仅暂停当前任务 | `POST_ERR(..., ERR_PAUSE)` |
