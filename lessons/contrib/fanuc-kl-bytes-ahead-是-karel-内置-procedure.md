---
{"title": "FANUC KL: BYTES_AHEAD 是 Karel 内置 Procedure", "domain": "fanuc", "source": "bootstrap", "status": "draft", "tags": [], "created": "2026-05-03", "updated": "2026-05-03", "subdomain": "kl-syntax", "confidence": 0.7}
---


## FANUC KL: BYTES_AHEAD 是 Karel 内置 Procedure

### 问题描述
KL 编译报错时，误认为 BYTES_AHEAD 是禁用标识符或非法调用，将其从 MM_RCV_NTFY.kl 中删除。

### 根因
BYTES_AHEAD 是 Karel 语言的内置系统调用（Built-in Procedure），用法完全正确。KL 语言保留字（禁用标识符）有特定列表，BYTES_AHEAD 不在其中。

### 修复方法
恢复 MM_RCV_NTFY.kl 中所有 BYTES_AHEAD 调用，不应删除。禁用标识符列表：SECONDS、ENDDO、ELSEIF 等（详见 fanuc-kl-compile SKILL.md）。

### 验证方式
KTRANS 编译 MM_RCV_NTFY.kl，无 BYTES_AHEAD 相关报错。
