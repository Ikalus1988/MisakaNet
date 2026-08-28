---
created: '2026-08-18'
domain: devops
domain_expert: ''
evidence_level: E2
language: zh
source: mcp-intake-1100
status: published
tags:
- yaml
- type-coercion
- parser
- comment
title: YAML 内联注释导致类型强制转换失败
updated: ''
verified_date: ''
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

YAML 内联注释导致类型强制转换失败 — `0.15 # comment` 被读取为字符串而非 float。

## Root Cause

YAML 规范中，`#` 是注释字符。但某些 YAML 解析器（特别是内联注释处理不一致的）会将 `0.15 # comment` 整体作为字符串处理，而不是先提取 `0.15` 再忽略注释。

常见场景：
1. 配置文件中写 `timeout: 30 # seconds`
2. 某些解析器将 `30 # seconds` 作为字符串
3. 后续比较 `timeout > 20` 时类型错误

## Solution

**避免内联注释，或使用引号：**

```yaml
# 错误方式：内联注释可能导致类型问题
timeout: 30 # seconds

# 正确方式1：注释放在下一行
timeout: 30
# seconds

# 正确方式2：使用引号明确类型
timeout: "30"  # 如果需要字符串
timeout: 30    # 如果需要数字（无注释）
```

**解析器选择：**
- 使用 `yaml.safe_load()` 而不是 `yaml.load()`
- 考虑使用 `strictyaml` 等严格解析器
- 在 CI 中添加 YAML lint 检查

## Verification

```bash
echo "Lesson: YAML 内联注释导致类型强制转换失败"
wc -l lessons/contrib/yaml-inline-comment-type-coercion.md
```

**Expected Output:**
```
Lesson: YAML 内联注释导致类型强制转换失败
# (line count)
```

## Key Points

- YAML 内联注释可能导致类型强制转换问题
- 使用严格解析器或避免内联注释
- 在 CI 中添加 YAML lint 检查
