# MisakaNet Deployment Guide

> Production deployment paths for MisakaNet services — from single-node CLI to remote MCP.

---

## Quick Start: Local Development

```bash
# Clone and install
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
pip install -e .

# Verify
python3 search_knowledge.py "python docker" --domain devops
```

**Requirements:** Python 3.10+, git, 200MB free disk.

---

## Deployment Paths Overview

| Path | Use Case | Complexity | Scale |
|------|----------|-----------|-------|
| **Local CLI** | Individual agent knowledge retrieval | Minimal | 1 node |
| **MCP Server (stdio)** | Claude Code / Cursor integration | Low | 1 user |
| **MCP Server (HTTP)** | Multi-client team access | Medium | 1–50 users |
| **Docker Container** | Isolated, reproducible deployment | Medium | Any |
| **Cloudflare Workers** | Global edge deployment (dashboard) | Medium | Unlimited |

---

## 1. Docker Deployment

### Build

```bash
docker build -t misakanet:latest .
```

The `Dockerfile` (Python 3.11-slim) bundles:
- MCP server (stdio entrypoint)
- Search engine + lessons
- Contribution tools
- Usage meter

### Run

```bash
# MCP server (default CMD)
docker run -v $(pwd)/lessons:/app/lessons misakanet:latest

# Interactive search
docker run -it --entrypoint python3 misakanet:latest search_knowledge.py "query"

# Custom port for HTTP MCP
docker run -p 8080:8080 --entrypoint python3 \
  misakanet:latest scripts/mcp_http_server.py --port 8080
```

### Docker Compose

```yaml
version: "3.8"
services:
  misakanet-mcp:
    build: .
    ports:
      - "8080:8080"
    entrypoint: python3
    command: scripts/mcp_http_server.py --port 8080
    volumes:
      - ./lessons:/app/lessons
      - ./data:/app/data

```

### Volume Mounts

| Path | Purpose | Required |
|------|---------|----------|
| `/app/lessons` | Lesson knowledge base | Yes |
| `/app/data` | SAG-Lite index, usage DB | Recommended |
| `/app/scripts` | Tool scripts | No (included) |

---

## 2. Cloudflare Workers Deployment

The dashboard (`docs/index.html`) is deployed as a Cloudflare Workers static site.

### Prerequisites

```bash
npm install -g wrangler
```

### Configuration (`wrangler.jsonc`)

```jsonc
{
  "name": "misakanet-web",
  "compatibility_date": "2026-07-04",
  "assets": { "directory": "docs" },
  "compatibility_flags": ["nodejs_compat"],
  "kv_namespaces": [
    { "binding": "MISAKANET_KV", "id": "YOUR_KV_NAMESPACE_ID" }
  ]
}
```

### Deploy

The site is deployed by Cloudflare **Workers Builds** (Git integration) on every push to `main`
that touches `docs/` — there is no per-developer deploy step. The commands below are for local
preview and emergency use only:

```bash
# From repo root — the site config is the ROOT wrangler.jsonc (name: misakanet-web, assets: docs/)
npm install
npx wrangler deploy
```

> **No `web/` directory.** This section used to start with `cd web`. That directory held only
> `package.json`, `package-lock.json`, `vitest.config.js` and `wrangler.jsonc`, and was **deleted on
> 2026-08-31 by 739cae4d9** ("slim repo — … drop web/ shell"). It is present in `v2.23.0`
> (`git ls-tree -r --name-only v2.23.0 web/`). An empty result from
> `git log origin/main -- web/` returning nothing is not evidence it never existed: the shared
> checkout is **shallow** (`.git/shallow`; `git rev-parse --is-shallow-repository` says `true`), so
> that ref carries a truncated history here. A full clone shows the deletion commit, and GitHub's
> compare API puts `739cae4d9` as the merge base of `main`. (`main` has 4,638 commits, root
> 2026-05-20 — it was never rewritten.) When in doubt use `git log --all -- web/` or a tag.

### KV Namespace Setup

```bash
npx wrangler kv:namespace create MISAKANET_KV
# Update wrangler.jsonc with the returned ID
```

### CI/CD

Two independent pipelines deploy Cloudflare resources; neither needs a local `wrangler deploy`.

**Site (`misakanet-web`, assets = `docs/`)** — Cloudflare **Workers Builds** (Git integration).
Fires on every push to `main`; configuration lives in the Cloudflare console, not in this repository.
The result appears as the `Workers Builds: misakanet-web` check-run on the commit. No GitHub secret
is involved.

**Main worker (`misakanet-register-proxy`)** — `.github/workflows/deploy-worker.yml`. It runs only
when `workers/register-proxy-sw.js` or `workers/wrangler.toml` changes on `main` (`paths:` in the
workflow), and requires:

| Secret | Purpose |
|--------|---------|
| `CF_API_TOKEN` | Cloudflare API token with Workers edit permission |

> The account id is not a secret here — the workflows that need it inline the account id
> (`CLOUDFLARE_ACCOUNT_ID`), which is why it is not in the table above.

---

## 3. MCP Server Deployment

### 3.1 Local (stdio) — for Claude Code

Add to `claude_desktop_config.json` (Claude Desktop) or `~/.claude.json` / project `.mcp.json`
(Claude Code — *not* `.claude/settings.json`, which holds hooks and permissions, not MCP servers):

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": [
        "/absolute/path/to/MisakaNet/scripts/mcp_server.py"
      ]
    }
  }
}
```

### 3.2 Remote (HTTP) — for Team Access

```bash
# Start server
python3 scripts/mcp_http_server.py --port 8080

# Production: use systemd or supervisor
# Example systemd unit: /etc/systemd/system/misakanet-mcp.service
```

**systemd Unit:**

```ini
[Unit]
Description=MisakaNet MCP HTTP Server
After=network.target

[Service]
Type=simple
User=misakanet
WorkingDirectory=/opt/MisakaNet
ExecStart=/usr/bin/python3 scripts/mcp_http_server.py --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3.3 Behind Reverse Proxy (nginx)

```nginx
location /mcp {
    proxy_pass http://127.0.0.1:8080/mcp;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400s;
}
```

---

## 5. Monitoring & Health Checks

### Built-in Health Endpoints

```bash
# Site health check
python3 scripts/site_health_check.py

# Worker secrets audit
python3 scripts/check_worker_secrets.py

# Node status
python3 scripts/node_status.py
```

### Logging

All components use Python's `logging` module. Set `LOG_LEVEL=DEBUG` for verbose output:

```bash
```

### Heartbeat

The `scripts/heartbeat.sh` script can be wired into cron for periodic health pings:

```bash
# crontab example — every 5 minutes
*/5 * * * * /opt/MisakaNet/scripts/heartbeat.sh
```

---

## 6. CI/CD Pipeline (`pr-shape-guard.yml`)

The PR Shape Guard (`pr-shape-guard.yml`) enforces deployment safety:

| Check | What It Verifies |
|-------|-----------------|
| **File deletion guard** | PRs must not delete existing files |
| **Directory structure** | New files must follow repo conventions |
| **DCO compliance** | Every commit must have `Signed-off-by:` |
| **No unrelated files** | PR scope must match issue acceptance criteria |

---

## 7. Security Considerations

### For Production Deployments

1. **Never expose MCP HTTP server directly to the internet** — use a reverse proxy with authentication
2. **Rotate `FEDERATION_SECRET` regularly** — every 90 days minimum
3. **Use read-only GitHub tokens** for search-only deployments
4. **Limit KV namespace permissions** in Cloudflare to least privilege
5. **Audit webhook URLs** — all notifications go through external services
6. **Pin Docker base images** by SHA digest in production

### Secrets Management

```bash
# Never commit secrets — use environment variables or a vault
export $(grep -v '^#' .env | xargs)  # Load from .env (not tracked in git)
```

---

## 8. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ImportError: misakanet_core` | Missing dependency | `pip install misakanet-core` |
| MCP connection refused | Server not running or wrong port | Check `lsof -i :8080` |
| Search returns 0 results | Index not built | Run `python3 search_knowledge.py "" --domain any` to warm cache |
| Docker build fails | Outdated base image | `docker pull python:3.11-slim` first |
| CF deploy 401 | Expired API token | Rotate `CF_API_TOKEN` in repo secrets (the env var it is exposed as inside a step is `CLOUDFLARE_API_TOKEN`) |
