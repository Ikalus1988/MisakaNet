---
title: 模型输出截断 / JSON 解析失败Handling
domain: contrib
tags:
- model
- output
status: published
created: '2026-07-06'
language: zh
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

模型返回的内容不完整（truncated），或者 JSON 解析失败（`json.decoder.JSONDecodeError`），导致后续处理流程中断。

## Root Cause

- 模型输出超过 max_tokens 限制，被截断
- 模型生成内容在传输过程中被截断（网络问题或网关限制）
- 输出格式不完整（如缺少闭合 `}` 或 `]`）
- 内容含有特殊字符导致解析器提前终止

## Solution

**JSON 截断修复：**
```python
import json, re

def safe_parse_json(raw: str) -> dict | None:
    """尝试修复截断的 JSON"""
    # 1. 去除控制字符
    raw = re.sub(r'[\x00-\x1f]', '', raw)
    # 2. 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 3. 尝试补全缺失的闭合括号
    for bracket in [('"', '"'), ("'", "'"), ("[", "]"), ("{", "}")]:
        open_count = raw.count(bracket[0]) - raw.count(bracket[1])
        if open_count > 0:
            raw += bracket[1] * open_count
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
```

**模型侧预防：**
```python
# 模型输出截断 / JSON 解析失败Handling
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,  # 加大
    # 或者在 prompt 里要求："输出完整的 JSON，不要省略任何字段"
)
```

**检测截断：**
```python
def is_truncated(response_text: str) -> bool:
    """检查是否被截断"""
    # 常见截断标记
    truncated_markers = [
        '...',           # 省略号结尾
        '..."',          # 字符串未闭合
        '{...}',         # 对象被省略
        '"',             # 字符串未闭合
    ]
    for marker in truncated_markers:
        if response_text.rstrip().endswith(marker):
            return True
    return False
```

## Verification

```bash
echo "Lesson: 模型输出截断 / JSON 解析失败Handling"
wc -l lessons/contrib/model-output-fix.md
```

**Expected Output:**
```
Lesson: 模型输出截断 / JSON 解析失败Handling
# (line count)
```

## Related

- 与 RAG 答案质量有关：truncated 的 JSON 会导致 rag_answer 解析失败
- 与 minimax 模型网关的 response 限制有关，mizu 通道可能有不同的截断行为