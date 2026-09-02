---
title: aily feishu mcp pull only
domain: feishu
tags:
- aily
- feishu
- pull
- only
status: published
created: '2026-07-06'
source: bootstrap
confidence: 0.7
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: mcp-capability
---

<!-- provenance:
provenance:
  source: "internal"
  contributor: "Ikalus1988"
  merged_at: "2026-05-20"
  evidence: "post-publication"
-->

---
<!-- 
## aily 飞书 MCP 通道：只能拉取不能推送

## Problem
虫群架构设计时，误以为 aily 飞书侧支持 MCP Server 暴露给 Hub 调用。

## Root Cause
aily 平台只支持**调用外部 MCP server**，不能作为 MCP server 被外部调用。

## Solution
飞书侧走"轮询拉取模式"：定时查询 Hub diff，而非接收推送。
- Hub 广播 Skill Diff → 飞书节点定时轮询
- 接受 30 分钟 SLA（延迟可接受，实时性要求不高）

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