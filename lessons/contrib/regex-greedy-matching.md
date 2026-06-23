---
{"title": "正则表达式 debugging — 贪婪匹配造成的意外结果", "domain": "development", "tags": ["regex", "debug", "greedy", "pattern"], "domain_expert": "unknown"}
---

## Background

正则匹配返回了预期之外的大量文本。`<div>.*</div>` 匹配到了文档末尾而不是最近的闭合标签。

## 根因

Default `.*` 和 `.+` 是贪婪模式，匹配尽可能多的字符。

## Fix

```python
import re

text = "<div>内容1</div><div>内容2</div>"

# 正则表达式 debugging — 贪婪匹配造成的意外结果
re.findall(r"<div>(.*)</div>", text)
# ['内容1</div><div>内容2']

# ✅ 非贪婪：匹配到最近的 </div>
re.findall(r"<div>(.*?)</div>", text)
# ['内容1', '内容2']

# ✅ Use更精确的排除匹配
re.findall(r"<div>([^<]*)</div>", text)
# ['内容1', '内容2']
```

## 速查

| 模式 | 含义 | 改为非贪婪 |
|------|------|-----------|
| `.*` | 任意字符0次+ | `.*?` |
| `.+` | 任意字符1次+ | `.+?` |
| `\d+` | 数字1次+ | `\d+?` |

## 验证

```bash
# Verify期望的匹配范围
python3 -c "import re; print(re.findall(r'YOUR_PATTERN', 'YOUR_TEXT'))"
```
