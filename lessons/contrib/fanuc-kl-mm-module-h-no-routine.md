---
title: 'FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明'
domain: fanuc
tags:
- fanuc
- module
- routine
status: published
created: 2026-05-03
language: zh
source: bootstrap
confidence: 0.7
domain_expert: bootstrap
verified_date: 2026-05-03
subdomain: kl-modules
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明

### Problem描述

`mm_module_h.kl`（头文件）末尾存在如下声明：

```kl
ROUTINE Check_Status(params : INTEGER) : BOOLEAN FROM MM_MODULE
```

该声明带有完整参数列表，导致 `MM_MODULE.kl` 中同名 routine 在 KTRANS 编译阶段报错：

```
Error: ROUTINE 'CHECK_STATUS' already defined in program 'MM_MODULE'
```

此错误会阻止整个项目的编译，所有依赖该头文件的程序均无法生成 `.pc` 文件。

---

### Root Cause

KTRANS 编译器对 ROUTINE 声明的处理方式与 C 语言头文件中的函数原型（prototype）**完全不同**：

1. **KTRANS 不区分"声明"与"定义"**：只要头文件中出现 `ROUTINE foo(...) FROM PROG`，KTRANS 就将其视为一次完整的 routine 绑定登记。当主程序 `MM_MODULE.kl` 再次定义同名 routine 时，编译器认为该符号已被占用，触发 `already defined` 错误。

2. **`FROM` 子句的误导性**：开发者常误以为 `ROUTINE foo FROM MM_MODULE` 仅是一个"外部引用声明"（类似 `extern`），实际上 KTRANS 会将其与 `MM_MODULE` 的符号表合并，造成冲突。

3. **头文件的正确职责**：FANUC KL 头文件（`_h.kl`）的唯一职责是共享 `TYPE`、`VAR`、`CONST` 定义，不应承载任何可执行逻辑或 routine 签名。

---

### Solution方法

**错误写法（mm_module_h.kl 中）：**

```kl
-- ❌ 错误：头文件中不得出现 ROUTINE 声明
ROUTINE Check_Status(status_code : INTEGER) : BOOLEAN FROM MM_MODULE
ROUTINE Reset_Module FROM MM_MODULE
```

**正确写法（mm_module_h.kl 中）：**

```kl
-- ✅ 正确：头文件只保留 TYPE / VAR / CONST
TYPE
  MM_STATUS_T = STRUCTURE
    code    : INTEGER
    message : STRING[64]
    active  : BOOLEAN
  ENDSTRUCTURE

VAR
  mm_status   IN CMOS FROM MM_MODULE_H : MM_STATUS_T
  mm_err_cnt  IN CMOS FROM MM_MODULE_H : INTEGER

CONST
  MM_MAX_RETRY = 3
  MM_TIMEOUT   = 5000
```

**正确写法（MM_MODULE.kl 中保留完整实现）：**

```kl
PROGRAM MM_MODULE
%INCLUDE mm_module_h

-- ✅ ROUTINE 定义（含实现）只在主程序中出现
ROUTINE Check_Status(status_code : INTEGER) : BOOLEAN
BEGIN
  IF status_code = 0 THEN
    RETURN(TRUE)
  ELSE
    RETURN(FALSE)
  ENDIF
END Check_Status

ROUTINE Reset_Module
BEGIN
  mm_status.code   = 0
  mm_status.active = FALSE
  mm_err_cnt       = 0
END Reset_Module

BEGIN
  -- 主程序入口
END MM_MODULE
```

**关键规则总结：**

| 内容类型 | 头文件 `_h.kl` | 主程序 `.kl` |
|---|---|---|
| `TYPE` 定义 | ✅ 允许 | ✅ 允许 |
| `VAR` 声明 | ✅ 允许 | ✅ 允许 |
| `CONST` 定义 | ✅ 允许 | ✅ 允许 |
| `ROUTINE` 声明/定义 | ❌ 禁止 | ✅ 必须在此 |

---

### Verification方式

**步骤 1：检查头文件中是否残留 ROUTINE 声明**

```bash
# 扫描所有 _h.kl 头文件，确认不含 ROUTINE 关键字
grep -in "^ROUTINE" src/*_h.kl 2>/dev/null && echo "❌ 发现违规 ROUTINE 声明" || echo "✅ 头文件无 ROUTINE 声明"
```

**步骤 2：KTRANS 编译验证**

```bash
# 使用 KTRANS 编译主程序，确认无 already defined 报错
ktrans MM_MODULE.kl 2>&1 | grep -i "already defined" && echo "❌ 存在重复定义错误" || echo "✅ 编译通过"
```

**步骤 3：验证课程文件覆盖率**

```bash
# Verify: FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明
grep -r "fanuc" lessons/contrib/fanuc-*.md 2>/dev/null | wc -l
```

**Expected Output:**
```
# (FANUC lesson count)
```

**步骤 4：人工审查检查清单**

- [ ] `mm_module_h.kl` 中无任何 `ROUTINE` 关键字
- [ ] 所有 `VAR` 声明使用 `IN CMOS FROM MM_MODULE_H` 格式
- [ ] `MM_MODULE.kl` 中 `Check_Status` 等 routine 定义完整且无重复
- [ ] KTRANS 编译输出无 `already defined` 或 `duplicate symbol` 错误
- [ ] 依赖该头文件的其他程序（如 `MM_CALLER.kl`）编译正常