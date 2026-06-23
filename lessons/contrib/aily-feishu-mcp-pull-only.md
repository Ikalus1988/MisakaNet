---
{"title": "aily 飞书 MCP 通道：只能拉取不能推送", "domain": "feishu", "subdomain": "mcp-capability", "source": "bootstrap", "status": "draft", "confidence": "0.7", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---


## aily 飞书 MCP 通道：只能拉取不能推送

### Problem描述
虫群架构设计时，误以为 aily 飞书侧Support MCP Server 暴露给 Hub 调用。

### 根因
aily 平台只Support**调用外部 MCP server**，不能作为 MCP server 被外部调用。

### Fix方法
飞书侧走"轮询拉取模式"：定时查询 Hub diff，而非接收推送。
- Hub 广播 Skill Diff → 飞书节点定时轮询
- 接受 30 分钟 SLA（延迟可接受，实时性要求不高）

### 验证方式
Hub 推送广播后，Check飞书侧日志是否在 SLA 内拉取到Update。
