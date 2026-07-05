---
domain: "contrib"
title: "feishu block batch limit"
verification: "metadata-normalized"
---
---{"title": "飞书 Block Batch写入上限", "domain": "feishu", "subdomain": "block-api", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03"}---

## 飞书 Block 批量写入上限

## Problem
批量创建 block 时，每次超过约 20 个触发限流或静默截断。

## Root Cause
服务端对单次 batch 请求有隐性上限，未在文档中说明。

## Solution
每批 ≤20 个 block；`parent_block_id` 使用 DOC_ID（不加 index）；超量时分批发送并加 500ms 间隔。

## Verification
连续写入 100 个 block，逐批确认 `blocks_created` 计数。
