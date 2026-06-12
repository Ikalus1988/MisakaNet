---
{"title": "Feishu 文件上传：file_type 必须用 opus", "domain": "feishu", "source": "hanged-man", "status": "published", "tags": [], "created": "2026-03-29", "updated": "2026-03-29", "confidence": 0.95, "scope": "broad", "alternative_of": "None", "related": ""}
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

## 教训

飞书 API 字段名严格按文档来，不要猜测近似名称。
