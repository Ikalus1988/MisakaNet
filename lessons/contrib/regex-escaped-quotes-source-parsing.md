---
title: "正则陷阱 — 源码中转义引号导致非贪婪匹配提前终止"
domain: development
tags:
  - regex
  - python
  - source-parsing
  - escape-sequences
  - debug
status: published
source: practical-experience
confidence: 0.9
created: 2026-07-07
---

## Problem

用正则从 Python 源码中提取 `os.environ.get("KEY", "default_value")` 的默认值时，提取结果被截断：

```python
source = 'exclude = os.environ.get("EXCLUDE_CHARACTERS", "/@\\"'+:?&!=% ")'
# 实际默认值: /@"'+:?&!=%  (含转义引号 \")
# 正则提取到: /@\  (在 \" 处停止)
```

## Root Cause

标准非贪婪正则 `(["'])(.*?)\1` 在遇到 `\"` 时：

1. `(.*?)` 匹配到 `/@\`
2. 下一个字符是 `"`（被 `\` 转义的引号）
3. `\1` 回溯引用匹配到这个 `"`（因为它是 `"` 字符）
4. 正则在此处停止，忽略了后续的 `'+:?&!=% "`

正则不知道 `\"` 是转义序列，只看到一个 `"` 字符。

## Solution

用 `[^\\]|\\.` 替代 `.` 来跳过转义字符：

```python
# ❌ 错误：. 不能跳过转义引号
pattern = r'(["'])(.*?)\1'

# ✅ 正确：(?:[^\\]|\\.) 匹配非反斜杠字符或转义序列
pattern = r'(["\'])((?:[^\\]|\\.)*?)\1'
```

解释：
- `[^\\]` — 匹配任何非 `\` 的字符
- `\\.` — 匹配 `\` 后跟任意字符（即转义序列）
- `(?:...)*?` — 非贪婪重复，但在每个位置都能正确跳过 `\"`

完整用法：

```python
import re

def extract_env_default(source: str, key: str) -> str:
    pattern = rf'''os\.environ\.get\(\s*["']{key}["']\s*,\s*(["\'])((?:[^\\]|\\.)*?)\1'''
    match = re.search(pattern, source)
    assert match, f"Could not find {key} default in source"
    return match.group(2)
```

## Verification

```python
source = 'os.environ.get("KEY", "/@\\"\\'+:?&!=% ")'
result = extract_env_default(source, "KEY")
assert '"' in result   # 转义引号被正确保留
assert "'" in result   # 单引号被正确保留
assert "&" in result   # 后续字符未被截断
```

## Why it matters

从源码中提取字符串常量是自动化测试和代码分析的常见需求。当源码包含转义引号（`\"`、`\'`）时，标准非贪婪匹配会提前终止。这个问题在解析 JSON 字符串、SQL 查询、Shell 命令等嵌套引号场景中也会出现。
