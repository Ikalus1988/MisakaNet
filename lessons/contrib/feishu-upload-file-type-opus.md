---
title: Feishu Upload File Type Opus
language: en
---

> **English Translation**
> Translated from Chinese original.

---
{"title": "Feishu 文件上传：file_type 必须用 opus", "domain": "feishu", "tags": "", "source": "hanged-man", "status": "published", "created": "2026-03-29", "confidence": "0.95", "scope": "broad", "alternative_of": "None", "related": "", "domain_expert": "hanged-man", "verified_date": "2026-03-29"}
---

## 问题

Feishu `im/v1/files` 上传接口调用失败，返回 `234001 Invalid request param`。

## 根因

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

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 教训

飞书 API 字段名严格按文档来，不要猜测近似名称。
