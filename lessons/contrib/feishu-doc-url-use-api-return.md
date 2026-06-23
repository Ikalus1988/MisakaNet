---
domain: "contrib"
title: "feishu doc url use api return"
verification: "metadata-normalized"
{"title": "Feishu 文档 URL：必须用 API 返回值，不要拼接", "domain": "feishu", "tags": "", "source": "hanged-man", "status": "published", "created": "2026-03-29", "confidence": "0.95", "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-03-29"}
---

## 问题

创建 Feishu 云文档后，猜测 URL 格式为 `https://feishu.cn/document/...`，用户连续3次无法打开文档。

## 根因

对飞书文档 URL 格式不熟悉，没有验证就自己拼接。

## 正确做法

API 返回的 `url` 字段直接使用，不要自己构造。正确格式：`https://{租户域名}.feishu.cn/docx/{document_id}`
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 教训

厂商 API 返回的字段就是真实值，信任文档，不要猜测格式。
