---
confidence: '0.95'
created: '2026-07-06'
domain: feishu
domain_expert: hanged-man
scope: broad
source: hanged-man
status: published
tags:
- feishu
- return
title: feishu doc url use api return
verification: metadata-normalized
verified_date: '2026-03-29'
'{"title"': 'Feishu 文档 URL：必须用 API 返回值，不要拼接", "domain": "feishu", "tags": "", "source":
  "hanged-man", "status": "published", "created": "2026-03-29", "confidence": "0.95",
  "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-03-29"}'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
created: '2026-07-06'
domain: contrib
source: unknown
status: published
title: feishu doc url use api return
verification: metadata-normalized
'{"title"': 'Feishu 文档 URL：必须用 API 返回值，不要拼接", "domain": "feishu", "tags": "", "source":
  "hanged-man", "status": "published", "created": "2026-03-29", "confidence": "0.95",
  "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-03-29"}'
---
## Problem

创建 Feishu 云文档后，猜测 URL 格式为 `https://feishu.cn/document/...`，用户连续3次无法打开文档。

## Root Cause

对飞书文档 URL 格式不熟悉，没有验证就自己拼接。

## 正确做法

API 返回的 `url` 字段直接使用，不要自己构造。正确格式：`https://{租户域名}.feishu.cn/docx/{document_id}`
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

## Lessons Learned

厂商 API 返回的字段就是真实值，信任文档，不要猜测格式。
