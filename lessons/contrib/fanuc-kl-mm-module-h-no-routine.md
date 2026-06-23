---
{"title": "FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明", "domain": "fanuc", "subdomain": "kl-modules", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## FANUC KL: mm_module_h.kl 禁止 ROUTINE 声明

### Problem描述
mm_module_h.kl（头File）末尾有 `ROUTINE Check_Status(params) FROM MM_MODULE`（带Parameter版），导致 MM_MODULE.kl 中同名 routine 报"already defined"。

### 根因
KTRANS 将头File中的 ROUTINE 声明（含Parameter）当作**完整定义**，而非引用声明。ROUTINE 声明只应出现在主程序中，头File仅含 TYPE/VAR/CONST。

### Fix方法
- 头File mm_module_h.kl：只保留 TYPE/VAR/CONST，不得有 ROUTINE 声明
- 头File新Variable声明格式：`IN CMOS FROM MM_MODULE_H`
- ROUTINE 定义（含实现）保留在主程序 MM_MODULE.kl 中

### 验证方式
KTRANS 编译整个项目无"already defined"报错。
