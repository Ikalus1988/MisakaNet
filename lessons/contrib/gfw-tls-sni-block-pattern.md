---
title: GFW TLS SNI Block Pattern — Why Tool-Layer Solutions Fail
domain: ops
subdomain: network
tags: ["gfw", "tls", "sni", "scraping", "proxy", "curl", "playwright"]
source: practical-experience
status: published
confidence: 0.95
created: 2026-07-01
verified_date: 
domain_expert: 
---


## Problem

Web scraping tools (curl, Playwright, scrapling, Safari MCP) all fail to connect to certain domains (e.g., reddit.com, stackoverflow.com) from networks behind the GFW, even though DNS resolves correctly.

## Root Cause

GFW performs TLS SNI (Server Name Indication) sniffing:

1. DNS resolves normally → CDN IP
2. TCP three-way handshake succeeds
3. TLS Client Hello is sent with SNI field (e.g., `reddit.com`)
4. GFW identifies the SNI and drops the Server Hello
5. Connection hangs for 10-30s then times out

**Key insight**: All tool-layer solutions (curl, Playwright, scrapling, Safari MCP, Agent-Reach) use the same TCP+TLS path. No tool can bypass a network-layer block.

## Diagnosis

```bash
# Check if a domain is SNI-blocked
curl -v --max-time 5 "https://target.com/" 2>&1 | grep -E "Connected|TLS|timeout"

# Expected pattern for SNI block:
#   Connected to target.com (x.x.x.x) port 443
#   TLS handshake, Client hello:
#   (hangs here...)
#   Connection timed out
```

## ⚠️ Whitelist: Sites Accessible from China (Do NOT Misdiagnose)

The following sites are **directly accessible** from mainland China. Agents must NOT report "GFW blocked" for these domains — scrape them directly.

| Site | Access | Method |
|------|--------|--------|
| robot-forum.com | ✅ Direct | Playwright (WoltLab) |
| bbs.gongkong.com | ✅ Direct | Playwright |
| GitHub | ✅ Direct | gh CLI / REST API |
| Dev.to | ✅ Direct | REST API |
| Juejin 掘金 | ✅ Direct | Playwright |
| SegmentFault | ✅ Direct | Playwright |

**Check flow (two-layer validation)**:

```
receive URL
  → Layer 1: Network reachability (whitelist / curl TLS test)
  → Layer 2: Environment readiness (tool dependencies satisfied?)
  → Both pass → scrape directly
  → Network OK but env missing → use fallback ladder
  → Network blocked → proxy or skip
```

### Layer 2: Environment Prerequisites

Whitelist means "network accessible", NOT "can scrape on this machine". Playwright needs system libraries:

```bash
# Check headless Chrome availability
npx playwright install --dry-run 2>&1 | grep -i "missing\|error"
# Or direct test
node -e "const {chromium}=require('playwright');chromium.launch().then(b=>b.close()).catch(e=>console.error(e.message))"
# Common missing: libnspr4, libnss3, libnssutil3 (Linux apt)
```

### Fallback Ladder (When Environment Not Ready)

| Priority | Method | Prerequisite | Best For |
|----------|--------|-------------|----------|
| 1 | Site REST API | None | HN/Dev.to/GitHub |
| 2 | curl + CSS selectors | None | Static pages |
| 3 | r.jina.ai mirror | None | General, but thread pages often fail |
| 4 | Safari MCP | macOS | Has browser env |
| 5 | Remote Chrome CDP | Chrome --remote-debugging-port | Has desktop Chrome |
| 6 | Browser Use API | API key | Paid solution |
| 7 | Fix local env | sudo | Most thorough |

## Solution

### Tool-Layer (Won't Work)

| Tool | Why It Fails |
|------|-------------|
| curl | Same TCP+TLS path |
| Playwright | Chromium uses same network stack |
| scrapling | curl_cffi underneath, same TLS path |
| Safari MCP | Safari uses same network path |
| Agent-Reach | Routes to upstream tools, same path |
| Reddit JSON API | curl underneath |
| Reddit RSS | curl underneath |

### Network-Layer (Required)

| Solution | Pros | Cons |
|----------|------|------|
| HTTP/HTTPS proxy | Works for all tools | Needs proxy server |
| VPN | Transparent to all tools | May affect all traffic |
| SOCKS5 proxy | Flexible | Tool-specific config |

### Configuration

```bash
# Environment variable (works for most tools)
export HTTPS_PROXY=http://proxy:port
export HTTP_PROXY=http://proxy:port

# curl specific
curl -x http://proxy:port https://target.com/

# Playwright
const browser = await chromium.launch({
  proxy: { server: 'http://proxy:port' }
});

# Agent-Reach
agent-reach install --channels reddit --proxy http://proxy:port
```

## Verification

1. `curl -v --max-time 5 "https://reddit.com/"` shows TLS handshake hanging
2. `curl -v --max-time 5 -x http://proxy:port "https://reddit.com/"` succeeds
3. Playwright with proxy option loads the page

## Notes

- This pattern applies to any GFW-blocked domain, not just Reddit
- Some networks have transparent proxies at the gateway level — check with your network admin
- DNS-over-HTTPS does NOT help — the SNI field is still visible in the TLS Client Hello
- ESNI/ECH (Encrypted Client Hello) would help but adoption is limited
- Source: practical experience from scraping multiple forums
