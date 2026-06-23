---
title: Feishu Block Type Values Limits
language: en
---

> **English Translation**
> Translated from Chinese original.

---{"title": "飞书 Block Type 正确值与已知Limit", "domain": "feishu", "subdomain": "block-api", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03"}---

## 飞书 Block Type 正确值与已知限制

### 问题描述
飞书 block API 的 type 字段使用数字 ID，错误值导致静默失败或 400。

### 根因
文档中 heading type 值不正确，实际可用值与社区文档有出入。

### 已知正确的 type 值
| type | 含义 | 稳定性 |
|------|------|--------|
| 2 | paragraph | ✅ 稳态 |
| 12 | bullet | ✅ 稳态 |
| 1770001 | heading（全级别） | ⚠️ 文档写错，不可查 |
| 19 | divider | ⚠️ 易触发 429，非稳态 |
| 27 | image | ❌ 返回成功但 token 被静默清空 |

### 修复方法
- heading 全用 1770001（不可查但实测可用）
- 图片不传 type=27，改用 paragraph 嵌 URL 替代
- divider（type=19）慎用，批量操作时加限流保护

### 验证方式
单接口测试各 type，验证响应中返回的 block 结构与预期一致。
