---
confidence: '0.85'
created: '2026-07-06'
domain: contrib
domain_expert: bootstrap
source: bootstrap
status: published
subdomain: network
tags:
- project:rag
- platform:wsl
- node:hermes_wsl
- scope:broad
title: firewall port open not public
verification: metadata-normalized
verified_date: '2026-05-03'
'{"title"': '防火墙端口开放不等于内网穿透", "domain": "devops", "subdomain": "network", "source":
  "bootstrap", "status": "published", "tags": ["project:rag", "platform:wsl", "node:hermes_wsl",
  "scope:broad"], "confidence": "0.85", "created": "2026-05-03", "domain_expert":
  "bootstrap", "verified_date": "2026-05-03"}'
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
title: firewall port open not public
verification: metadata-normalized
'{"title"': '防火墙端口开放不等于内网穿透", "domain": "devops", "subdomain": "network", "source":
  "bootstrap", "status": "published", "tags": ["project:rag", "platform:wsl", "node:hermes_wsl",
  "scope:broad"], "confidence": "0.85", "created": "2026-05-03", "domain_expert":
  "bootstrap", "verified_date": "2026-05-03"}'
---
## Problem

为 wcferry 开放 Windows 防火墙端口 10086 时，误以为这是"内网穿透"操作，担心安全性。

## Root Cause

netsh advfirewall firewall add rule 只是允许本机 WSL2 虚拟机访问 Windows 主机的端口。流量路径在**单台电脑内部**：

```
WSL2 (Linux 虚拟机) → 本机虚拟网卡 → Windows 主机 :10086
```

不涉及外网、不暴露端口到互联网。和 ngrok/frp/端口映射完全不是一回事。

## Solution

无修复必要——操作本身就是正确的。但需要理解：
- 防火墙规则 = 允许谁访问（本机 WSL2 → Windows）
- 内网穿透 = 允许外网访问你的内网机器（如 ngrok）
- **两者无关**

## Verification

```bash
echo "Lesson: firewall port open not public"
wc -l lessons/contrib/firewall-port-open-not-public.md
```

**Expected Output:**
```
Lesson: firewall port open not public
# (line count)
```

## Notes

WSL2 + Windows 混合开发，任何需要 WSL 访问 Windows 端口的情况（RAG API、微信机器人等）。
