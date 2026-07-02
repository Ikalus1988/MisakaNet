{"title": "Agent-Reach — Multi-Platform Internet Access for AI Agents", "domain": "agent", "subdomain": "tooling", "tags": ["agent-reach", "scraping", "reddit", "twitter", "bilibili", "mcp"], "source": "github.com/Panniantong/Agent-Reach", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}

{"title": "Agent-Reach — Multi-Platform Internet Access for AI Agents", "domain": "agent", "subdomain": "tooling", "tags": ["agent-reach", "scraping", "reddit", "twitter", "bilibili", "mcp"], "source": "github.com/Panniantong/Agent-Reach", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

AI agents need to read/search across multiple internet platforms (Twitter, Reddit, YouTube, Bilibili, etc.) but each has its own authentication, anti-bot, and API requirements.

## Root Cause

Each platform has different access methods:
- Some need API keys (Twitter, Reddit official API)
- Some need browser cookies (Reddit via rdt-cli)
- Some have public APIs (Bilibili search)
- Some are behind geo-blocks (Reddit in China)

## Solution

### Agent-Reach Architecture

Agent-Reach is an installer + router, NOT a wrapper. After install, agents call upstream tools directly.

```
agent-reach install --channels reddit,twitter
  ↓
Installs: rdt-cli, twitter-cli, etc.
  ↓
Agent calls: rdt search "query", twitter-cli timeline
```

### Installation

```bash
# Create venv
python3 -m venv ~/.agent-reach-venv
source ~/.agent-reach-venv/bin/activate

# Install
pip install https://github.com/Panniantong/agent-reach/archive/main.zip

# Auto-configure
agent-reach install --env=auto

# With proxy (for blocked sites)
agent-reach install --channels reddit --proxy http://proxy:port

# Check status
agent-reach doctor --json
```

### Supported Platforms (15)

| Platform | Zero-Config | Needs Config |
|----------|-------------|--------------|
| GitHub | ✅ | Private repos |
| YouTube | ✅ (yt-dlp) | JS runtime |
| RSS | ✅ | — |
| Web (Jina Reader) | ✅ | — |
| Bilibili | ✅ (search) | Full features |
| Reddit | ❌ | Login + proxy |
| Twitter | ❌ | Login |
| XiaoHongShu | ❌ | Login |

### Key Tools Installed

| Tool | Purpose |
|------|---------|
| rdt-cli | Reddit CLI (reverse-engineered API) |
| twitter-cli | Twitter CLI |
| bili-cli | Bilibili CLI |
| yt-dlp | YouTube downloader |
| Jina Reader | Universal web reader |

## Verification

1. `agent-reach doctor --json` shows platform statuses
2. `agent-reach install --channels reddit` installs rdt-cli
3. `rdt status` shows authentication state
4. `rdt search "query"` returns results (if authenticated)

## Notes

- Agent-Reach is a Chinese project (README in Chinese)
- Reddit has NO zero-config path — anonymous .json is blocked, official API closed self-registration
- For China-based users: Reddit/Twitter/Instagram need proxy
- Source: github.com/Panniantong/Agent-Reach (v1.5.0)
