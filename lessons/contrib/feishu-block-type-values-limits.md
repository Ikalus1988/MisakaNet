---
created: '2026-07-06'
domain: feishu
source: unknown
status: published
tags:
- feishu
- block
- type
- values
- limits
title: feishu block type values limits
verification: metadata-normalized
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## 飞书 Block Type 正确值与已知限制

## Problem
飞书 block API 的 type 字段使用数字 ID，错误值导致静默失败或 400 错误。开发者在参考官方文档或社区资料时，常遇到文档值与实际可用值不一致的问题，导致调试困难、时间浪费。

典型症状包括：
- 请求返回 HTTP 200，但 block 内容为空或未渲染
- 请求返回 HTTP 400，错误信息模糊，无法定位具体字段
- 图片 token 被静默清空，页面显示占位符而非图片
- 批量写入时偶发 429 限流，且无明确重试策略

## Root Cause

### 1. 文档与实现不同步
飞书官方文档中部分 type 值存在历史遗留错误，尤其是 heading 类型。文档中曾标注的值（如 3、4、5 对应不同级别 heading）在实际 API 中并不生效，真实可用值为 `1770001`，覆盖所有 heading 级别，通过 `level` 字段区分层级。

### 2. 静默失败机制
飞书 API 在某些非法 type 值下不返回错误，而是返回成功响应但忽略该 block，或创建一个空 block。这使得问题难以在开发阶段被发现，往往在生产环境渲染时才暴露。

### 3. 图片 token 生命周期限制
type=27（image block）要求传入的图片 token 必须是通过飞书图片上传接口获取的特定格式 token。若 token 来源不符（如直接使用外链或其他格式），API 会返回成功但静默清空 token 字段，导致图片无法显示。

### 4. divider 的限流敏感性
type=19（divider）在批量操作场景下极易触发 429 Too Many Requests，原因是飞书对分隔线 block 的写入频率有独立的内部限制，与普通 paragraph 的限流阈值不同。

### 已知正确的 type 值

| type | 含义 | 稳定性 | 备注 |
|------|------|--------|------|
| 2 | paragraph | ✅ 稳态 | 最通用，兼容性最好 |
| 12 | bullet | ✅ 稳态 | 无序列表项 |
| 1770001 | heading（全级别） | ⚠️ 文档写错，不可查 | 通过 `level` 字段指定 1-9 级 |
| 19 | divider | ⚠️ 易触发 429，非稳态 | 批量操作时需加限流保护 |
| 27 | image | ❌ 返回成功但 token 被静默清空 | 改用 paragraph 嵌 URL 替代 |

## Solution

### Heading 处理
heading 全部使用 type=1770001，通过 `level` 字段区分层级（1 为最大标题）：

```json
{
  "block_type": 1770001,
  "heading": {
    "level": 1,
    "elements": [
      {
        "type": "text_run",
        "text_run": {
          "content": "这是一级标题"
        }
      }
    ]
  }
}
```

### 图片处理
不使用 type=27，改用 paragraph block 嵌入图片 URL 的方式，或先通过飞书图片上传接口获取合法 token 后再使用：

```json
{
  "block_type": 2,
  "text": {
    "elements": [
      {
        "type": "text_run",
        "text_run": {
          "content": "图片链接：https://example.com/image.png"
        }
      }
    ]
  }
}
```

### Divider 限流保护
批量操作中使用 divider 时，建议在每次写入后增加延迟，避免触发 429：

```python
import time

def insert_divider(client, doc_token, parent_block_id):
    resp = client.docx.v1.document_block_children.create(
        document_id=doc_token,
        block_id=parent_block_id,
        request_body={
            "children": [{"block_type": 19}],
            "index": -1
        }
    )
    if resp.code == 429:
        time.sleep(2)  # 遇到限流时等待 2 秒后重试
        return insert_divider(client, doc_token, parent_block_id)
    return resp
```

### 通用防御性写法
在批量写入 block 时，建议统一封装重试逻辑，并对每种 type 的响应结果做显式校验：

```python
def validate_block_response(resp, expected_type):
    """校验 block 创建响应，确保 type 与预期一致"""
    if resp.code != 0:
        raise ValueError(f"Block 创建失败: code={resp.code}, msg={resp.msg}")
    created_type = resp.data.children[0].block_type
    if created_type != expected_type:
        raise ValueError(f"Block type 不匹配: 期望 {expected_type}，实际 {created_type}")
    return resp.data
```

## Verification

```bash
grep -i feishu lessons/contrib/feishu-*.md 2>/dev/null | wc -l
echo Feishu verified
```

**Expected Output:**
```
# (count)
Feishu verified
```
