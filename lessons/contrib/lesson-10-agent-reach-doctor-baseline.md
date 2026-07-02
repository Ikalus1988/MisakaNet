---
domain: "tooling"
title: "Agent-Reach v1.5.0 doctor Baseline: 4/15 Channels Available Without Login"
verification: "metadata-normalized"
{"title": "Agent-Reach v1.5.0 doctor Baseline: 4/15 Channels Available Without Login", "domain": "tooling", "tags": ["agent-reach", "doctor", "channel-availability", "baseline", "v2ex", "rss", "jina", "bilibili", "cookie-required"], "status": "draft", "confidence": "0.88", "created": "2026-07-03", "updated": "2026-07-03", "source": "Real test output 2026-07-03T00:32 GMT+8 on WSL Ubuntu", "verified_date": "", "domain_expert": ""}
---

# Agent-Reach v1.5.0 doctor Baseline: 4/15 Channels Available Without Login

> Author: 太阳 (Misaka10004)  
> Created: 2026-07-03  
> Status: draft, confidence 0.88  
> Domain: tooling  
> Source: Real `agent-reach doctor` output on WSL Ubuntu 2026-07-03T00:32 GMT+8

## Problem

After installing Panniantong/Agent-Reach (v1.5.0), running `agent-reach doctor` shows 4/15 channels working without additional configuration. Knowing **exactly which channels work out-of-the-box** saves time when deciding whether to invest in cookie-based setup for the rest.

This baseline also documents what users can expect from a fresh install on a typical WSL Ubuntu machine.

## Reproduction

```bash
# Install (per install.md)
uv venv ~/.agent-reach-venv --python python3.12 --seed
HTTPS_PROXY=http://172.19.128.1:7890 \
  ~/.agent-reach-venv/bin/pip install https://github.com/Panniantong/agent-reach/archive/main.zip

# Doctor
agent-reach doctor
```

## Observed Output (Baseline)

```
Agent Reach 状态
========================================
图例：✅ 可用  [!] 已装但需配置/登录  [X] 未安装

✅ 装好即用：
  [!]  GitHub 仓库和代码 — gh CLI 未安装。安装：https://cli.github.com
  [!]  YouTube 视频和字幕 — yt-dlp 已安装但未配置 JS runtime。运行：
  mkdir -p '/home/USER/.config/yt-dlp' && grep -qxF -- '--js-runtimes node' 
'/home/USER/.config/yt-dlp/config' 2>/dev/null || printf '%s
' '--js-runtimes node' >> '/home/USER/.config/yt-dlp/config'
  ✅ V2EX 节点、主题与回复 — 公开 API 可用（热门主题、节点浏览、主题详情、用户信息）
  ✅ RSS/Atom 订阅源 — 可读取 RSS/Atom 源
  [X]  全网语义搜索 — 需要 mcporter + Exa MCP
  ✅ 任意网页 — 通过 Jina Reader 读取任意网页

可选渠道（已安装）：
  ✅ B站视频、字幕和搜索 — B站搜索 API 可达（仅搜索）

状态：4/15 个渠道可用
还有 8 个可选渠道可以解锁（Twitter/X 推文、Reddit 帖子和评论、Facebook
帖子、主页和群组、Instagram 用户、主页和指定用户帖子、小红书笔记、小宇宙播客转文字、雪球股票行情与社区动态、
LinkedIn 职业社交）
```

## Categorization

### Channels working out-of-the-box (4)

| Channel | Method | Reliability |
|---|---|---|
| **V2EX** | Public API + r.jina.ai fallback | High (but per-topic detail is flaky — see lesson-09) |
| **RSS/Atom** | Standard feedparser | High |
| **任意网页 (Web)** | Jina Reader (r.jina.ai) | High (depends on Jina uptime) |
| **B站 搜索** | B站 public search API | Medium (search only, full features need bili-cli) |

### Channels needing configuration (3)

| Channel | What's needed | Effort |
|---|---|---|
| **GitHub** | Install `gh` CLI | 5 min |
| **YouTube** | Set `yt-dlp` config with `--js-runtimes node` | 1 min |
| **Exa (全网搜索)** | Install `mcporter` + `npm install -g mcporter` | 5 min |

### Channels needing login (8)

| Channel | Login method | Difficulty |
|---|---|---|
| Twitter/X | Cookie from logged-in browser | High (anti-bot aggressive) |
| Reddit | OpenCLI or rdt-cli + cookie | High (anonymous .json blocked) |
| Facebook | OpenCLI (Chrome session reuse) | Very High (aggressive anti-bot) |
| Instagram | OpenCLI | Very High |
| 小红书 | OpenCLI or xiaohongshu-mcp QR code | Medium |
| 小宇宙 (播客) | Whisper API key (free tier) | Low |
| 雪球 | Cookie from logged-in browser | Medium |
| LinkedIn | Cookie (Jina fallback for public profiles) | Medium |

## Fix / Strategy

For an initial install, focus on the **4 ready-to-use channels** + the 3 easy configurations:

### Step 1 — Use ready channels immediately

These work right now:

```python
# V2EX — get hot topics
agent-reach format v2ex hot  # Or use r.jina.ai directly

# RSS — read any feed
python3 -c "
import feedparser
for e in feedparser.parse('https://hnrss.org/newest').entries[:5]:
    print(f'{e.title} -- {e.link}')
"

# Web — fetch any page
curl -s "https://r.jina.ai/https://example.com"

# B站 — search only
curl -s "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=python"
```

### Step 2 — Add the 3 easy configurations

```bash
# GitHub CLI
sudo apt install gh
# Or use the github-cli install script

# YouTube JS runtime (for subtitle extraction)
mkdir -p ~/.config/yt-dlp
printf '%s\n' '--js-runtimes node' >> ~/.config/yt-dlp/config

# Exa search (for "全网搜索")
npm install -g mcporter
mcporter config add exa https://mcp.exa.ai/mcp
```

### Step 3 — Decide on cookie-based channels based on actual need

Don't enable Twitter/Reddit/etc. "just in case". Each cookie-based channel:
- Needs ongoing maintenance (cookie rotation when expired)
- Carries account-ban risk (using unofficial API violates ToS)
- Should match a real recurring need

## Verification

```bash
# 1. doctor shows ≥4 channels
~/.agent-reach-venv/bin/agent-reach doctor | grep -c "✅"
# Expected: 4 or more

# 2. V2EX test
HTTPS_PROXY=http://172.19.128.1:7890 \
  ~/.agent-reach-venv/bin/agent-reach format v2ex hot --limit 5
# Should print: list of 5 hot topics

# 3. RSS test
HTTPS_PROXY=http://172.19.128.1:7890 \
  ~/.agent-reach-venv/bin/python3 -c "
import feedparser
for e in feedparser.parse('https://hnrss.org/newest').entries[:3]:
    print(e.title)
"
# Should print: 3 HN article titles

# 4. Web test
HTTPS_PROXY=http://172.19.128.1:7890 \
  curl -sS --max-time 20 "https://r.jina.ai/https://example.com"
# Should print: clean markdown of example.com
```

## Verification (self-check)

```python
def agent_reach_baseline(venv_bin):
    import subprocess
    doctor = subprocess.run(
        [f"{venv_bin}/agent-reach", "doctor"],
        capture_output=True, text=True, env={"HTTPS_PROXY": "http://172.19.128.1:7890"}
    )
    working_count = doctor.stdout.count("✅")
    return {
        "working_channels": working_count,
        "meets_baseline": working_count >= 4,
        "needs_more_config": working_count < 6,
    }
```

## Notes

- The 4/15 baseline reflects a **WSL Ubuntu 2026-07-03** machine. Different environments (macOS, native Linux) may vary slightly.
- V2EX's hot-list API works reliably but per-topic detail is flaky (see lesson-09).
- The MisakaNet lesson `agent-reach-multi-platform-scraper.md` covers the architecture but not the channel-by-channel baseline.
- For each channel needing login, the user must provide their own cookies — agent-reach cannot bypass authentication.
- Agent-reach is a Chinese-developed project (README in Chinese first), so V2EX / 小红书 / 雪球 / 小宇宙 channels are first-class citizens.

## Related Sources

- agent-reach repo: https://github.com/Panniantong/Agent-Reach (v1.5.0)
- agent-reach install.md: https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md
- MisakaNet lesson (architecture-level): `lessons/contrib/agent-reach-multi-platform-scraper.md`
- Real output: agent-reach doctor on WSL 2026-07-03T00:32 GMT+8