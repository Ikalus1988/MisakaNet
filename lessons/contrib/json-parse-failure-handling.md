---
{"title": "JSON 解析失败处理 — 截断 / 格式错误", "domain": "devops", "tags": ["json", "parse", "truncated", "llm", "output"]}
---

## 背景

从 LLM 输出或 API 返回中解析 JSON 时报 `json.decoder.JSONDecodeError`。常见于模型输出被截断、前后有多余字符。

## 根因

1. 模型输出在 JSON 完成前被截断（token 限制）
2. 模型在 JSON 前后加了 markdown 代码块标记 ```json ... ```
3. JSON 内容含未转义的特殊字符

## 修复

```python
import json
import re

def safe_json_parse(text: str) -> dict | None:
    """尝试多种策略解析 JSON"""
    
    # 策略 1：直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 策略 2：提取代码块中的 JSON
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    
    # 策略 3：提取第一个 { } 间的完整内容
    m = re.search(r'(\{.*\})', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    
    # 策略 4：使用 strict=False（允许控制字符）
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    
    return None

# 使用
result = safe_json_parse(model_output)
if result is None:
    print("JSON 解析失败，尝试重新生成")
```
