---{"title": "飞书 Block Type 正确Value与已知Limit", "domain": "feishu", "subdomain": "block-api", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03"}---

## 飞书 Block Type 正确Value与已知限制

### Problem描述
飞书 block API 的 type 字段Use数字 ID，ErrorValue导致静默失败或 400。

### 根因
文档中 heading type Value不正确，实际可用Value与社区文档有出入。

### 已知正确的 type Value
| type | 含义 | 稳定性 |
|------|------|--------|
| 2 | paragraph | ✅ 稳态 |
| 12 | bullet | ✅ 稳态 |
| 1770001 | heading（全级别） | ⚠️ 文档写错，不可查 |
| 19 | divider | ⚠️ 易触发 429，非稳态 |
| 27 | image | ❌ 返回成功但 token 被静默清空 |

### Fix方法
- heading 全用 1770001（不可查但实测可用）
- 图片不传 type=27，改用 paragraph 嵌 URL 替代
- divider（type=19）慎用，批量操作时加限流保护

### 验证方式
单Interface测试各 type，验证响应中返回的 block 结构与预期一致。
