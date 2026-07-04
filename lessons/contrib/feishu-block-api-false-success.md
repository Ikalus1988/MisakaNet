---
domain: "contrib"
title: "feishu block api false success"
verification: "metadata-normalized"
{"title": "飞书 Block API 假成功特征", "domain": "feishu", "subdomain": "block-api", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## 飞书 Block API 假成功特征

## Problem
调用飞书 block API 时，限流场景下返回 `code=0` 但 `blocks_created=0`，看似成功实际失败。

## Root Cause
飞书服务端在触发限流时不会返回非零错误码，而是静默截断，`code=0` 是"请求被接受"而非"执行成功"。

## Solution
脚本必须增加以下容错逻辑：
```python
if response['code'] == 0 and response.get('blocks_created', 1) == 0:
    raise RuntimeError('Block API 限流假成功，需重试')
```
仅检查 `code=0` 不够，必须同时验证 `blocks_created > 0`。

## Verification
用 100+ block 批量写入压测，每次确认 `blocks_created` 与实际写入数一致。
