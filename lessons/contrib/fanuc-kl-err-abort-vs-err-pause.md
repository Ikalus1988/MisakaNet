---
{"title": "FANUC KL: ERR_ABORT vs ERR_PAUSE 行为差异", "domain": "fanuc", "subdomain": "error-handling", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## FANUC KL: ERR_ABORT vs ERR_PAUSE 行为差异

### Problem描述
IPC 通信Error时未区分 ERR_ABORT 和 ERR_PAUSE，导致程序号丢失。

### 根因
- ERR_ABORT=2：所有任务中止（导致丢程序号）
- ERR_PAUSE=1：仅暂停Current任务，不影响Other任务

### Fix方法
IPC 超时类Error应Use ERR_PAUSE 而非 ERR_ABORT，避免级联中止。

### 验证方式
模拟 IPC 超时，Verify程序号在 ERR_PAUSE 场景下保留。
