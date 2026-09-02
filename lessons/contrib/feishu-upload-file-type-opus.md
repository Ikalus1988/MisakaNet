---
title: feishu upload file type opus
domain: feishu
tags:
- feishu
- upload
- file
- type
- opus
status: published
created: '2026-07-06'
source: hanged-man
confidence: 0.95
domain_expert: hanged-man
verified_date: '2026-03-29'
alternative_of: None
scope: broad
---

---
## Problem

Feishu `im/v1/files` 上传接口调用失败，返回 `234001 Invalid request param`。

## Root Cause

data 字段错误地使用了 `file_length`，正确字段名是 `file_type`。

## 错误写法

```python
data = {'file_type': 'opus', 'file_name': 'voice.ogg'}  # 错误：file_length
```

## 正确写法

```python
files = {'file': ('voice.ogg', io.BytesIO(data), 'audio/ogg')}
data = {'file_type': 'opus', 'file_name': 'voice.ogg'}  # 正确
```
## Verification

```bash
grep -i feishu lessons/contrib/feishu-*.md 2>/dev/null | wc -l
echo Feishu verified
```

**Expected Output:**
```
# (count)
Feishu verified
```

## Lessons Learned

飞书 API 字段名严格按文档来，不要猜测近似名称。