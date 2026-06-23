---
domain: "contrib"
title: "fanuc kl mm module h no routine"
verification: "metadata-normalized"
{"title": "FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明", "domain": "fanuc", "subdomain": "kl-modules", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明

### 问题描述
mm_module_h.kl（头文件）末尾有 `ROUTINE Check_Status(params) FROM MM_MODULE`（带参数版），导致 MM_MODULE.kl 中同名 routine 报"already defined"。

### 根因
KTRANS 将头文件中的 ROUTINE 声明（含参数）当作**完整定义**，而非引用声明。ROUTINE 声明只应出现在主程序中，头文件仅含 TYPE/VAR/CONST。

### 修复方法
- 头文件 mm_module_h.kl：只保留 TYPE/VAR/CONST，不得有 ROUTINE 声明
- 头文件新变量声明格式：`IN CMOS FROM MM_MODULE_H`
- ROUTINE 定义（含实现）保留在主程序 MM_MODULE.kl 中

### 验证方式
KTRANS 编译整个项目无"already defined"报错。
