---
{
  "title": "YAML 内联注释导致类型强制转换失败",
  "domain": "devops",
  "tags": [
    "yaml",
    "type-coercion",
    "parser",
    "comment"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "pr",
  "created": "2026-08-18",
  "updated": "",
  "verified_date": "",
  "domain_expert": "",
  "author": "Ikalus1988",
  "edited_at": "2026-08-18T12:51:50+08:00",
  "merged_by": "Ikalus1988",
  "pr": 1102
}
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

- YAML 解析后类型正确
- 无 TypeError
- 注释不影响解析

## Key Points

- YAML 内联注释可能导致类型强制转换问题
- 使用严格解析器或避免内联注释
- 在 CI 中添加 YAML lint 检查
