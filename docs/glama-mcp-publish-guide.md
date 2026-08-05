# Glama MCP Server Registration & Publishing — Complete Guide

> Consolidated from our own experience and zsxh1990's PR #590 (deployment lessons).

## Overview

Glama indexes MCP servers from GitHub, builds them via Docker, runs MCP introspection, and assigns quality scores (TDQS). The process is mostly automated — you do one manual setup, then it rescan on every commit.

## Step 1: Prerequisites

Before submitting to Glama, make sure your MCP server has:

- [ ] `Dockerfile` in repo root (Glama builds from this)
- [ ] `.dockerignore` (keep image small)
- [ ] `glama.json` in repo root
- [ ] `server.json` for MCP Registry (optional but recommended)
- [ ] Tool descriptions with behavior/output/usage docs (for TDQS scoring)
- [ ] LICENSE file with SPDX identifier in `pyproject.toml`

### glama.json

```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["your-github-username"]
}
```

### pyproject.toml (Python)

```toml
[project]
name = "your-package"
license = "Apache-2.0"  # SPDX expression, NOT classifier
classifiers = [
    # Do NOT include "License :: OSI Approved :: ..." — conflicts with PEP 639
]
```

## Step 2: Dockerfile

### For Python MCP servers (stdio)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY your_module/ your_module/
COPY scripts/mcp_server.py scripts/mcp_server.py
COPY lessons/ lessons/        # if applicable

RUN pip install --no-cache-dir .

CMD ["python3", "scripts/mcp_server.py"]
```

### For Glama's auto-generated Dockerfile

Glama uses `debian:trixie-slim` + `uv` (not pip). If you configure via Glama's web UI:

| Field | Value |
|-------|-------|
| Base image | `debian:trixie-slim` |
| Python version | `3.12` (match what you test with) |
| Node.js version | `20` (required field, even if unused) |
| Build steps | `["uv venv && . .venv/bin/activate && uv pip install -e ."]` |
| CMD arguments | `["mcp-proxy", "--", ".venv/bin/python", "scripts/mcp_server.py"]` |
| Pinned commit SHA | Leave empty (use latest) |

**Critical:** You MUST use `uv venv` — Glama's Python is "externally managed" by uv.

## Step 3: Submit to Glama

1. Go to https://glama.ai/mcp/servers
2. Click **"Add Server"**
3. Enter your GitHub repo URL
4. Glama will:
   - Clone your repo
   - Build from Dockerfile
   - Run MCP introspection (`initialize`, `tools/list`, `resources/list`, `prompts/list`)
   - Score each tool (TDQS)
   - Assign overall quality grade (A/B/C/D/F)

## Step 4: Verify

After submission, check:

1. **Build status** — https://glama.ai/mcp/servers/YOUR_ORG/YOUR_REPO
2. **Score page** — https://glama.ai/mcp/servers/YOUR_ORG/YOUR_REPO/score
3. **Tool scores** — each tool gets individual TDQS score

## Step 5: Publish to MCP Registry

```bash
# Install mcp-publisher
# Windows:
Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_amd64.tar.gz" -OutFile "mcp-publisher.tar.gz"
tar xf mcp-publisher.tar.gz mcp-publisher.exe
rm mcp-publisher.tar.gz

# Login
.\mcp-publisher.exe login github

# Publish
.\mcp-publisher.exe publish
```

Requires `server.json` in repo root with correct `mcp-name` (case-sensitive: `io.github.YourName/your-server`).

## Step 6: Publish to PyPI (optional)

```bash
python -m build
python -m twine upload dist/*
```

PyPI package README must contain: `mcp-name: io.github.YourName/your-server`

## Common Failures & Fixes

| Failure | Error | Fix |
|---------|-------|-----|
| pip not found | `/bin/sh: 1: pip: not found` | Use `uv pip install` |
| No venv | `No virtual environment found` | Add `uv venv && . .venv/bin/activate` |
| PEP 668 | `externally managed` | Use venv, not `--system` |
| Package not installed | `No module named X.__main__` | Add `uv pip install -e .` |
| pyproject.toml not found | `neither pyproject.toml nor setup.py` | Check COPY path in Dockerfile |
| Docker Hub timeout | `context deadline exceeded` | Retry (transient) |
| Build cancelled | `did not start within 2 hours` | Retry during off-peak |
| License conflict | `License classifiers have been superseded` | Remove license classifier, keep SPDX expression |
| mcp-name casing | `ownership validation failed` | Match GitHub username casing exactly |
| Description too long | `expected length <= 100` | Shorten server.json description |
| glama.json ignored | `No glama.json` despite file existing | Keep glama.json minimal: only `$schema` + `maintainers`. Tool definitions come from MCP introspection, not glama.json |
| Tools not showing | Build succeeds but `tools: []` | Introspection is async — wait, then Sync Server / Rebuild to trigger fresh introspection |

## Auto-Rescan

Glama automatically rescans on:
- New commits to default branch
- Dockerfile changes
- Manual "Rebuild" button on Glama page

No manual re-scoring needed. Just push your changes and wait.

## TDQS Scoring (Tool Definition Quality Score)

Each tool is scored 1-5 on 6 dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| Purpose Clarity | Is the tool's purpose obvious from its name and description? |
| Usage Guidelines | Does the description explain when/how to use it? |
| Behavioral Transparency | Are side effects, auth, and error behavior documented? |
| Parameter Semantics | Are input parameters clearly described with types and examples? |
| Conciseness | Is the description focused and not redundant? |
| Contextual Completeness | Does the description explain the tool's relationship to other tools? |

**To improve scores:** Add behavior docs (read-only? side effects?), output format, error cases, and when to use vs other tools.

## Version Alignment

Keep versions consistent across channels:

| Channel | Source |
|---------|--------|
| PyPI | `pyproject.toml` version |
| MCP Registry | `server.json` version |
| Glama | Latest commit on default branch |
| GitHub Release | Git tag |

If Glama shows a different version than PyPI, it's normal — Glama tracks the latest commit, not the PyPI version.

## Checklist

- [ ] `Dockerfile` builds locally
- [ ] `glama.json` in repo root
- [ ] Tool descriptions have behavior/output/usage docs
- [ ] LICENSE file exists with SPDX identifier
- [ ] No deprecated license classifiers in `pyproject.toml`
- [ ] `server.json` has correct `mcp-name` casing
- [ ] Submitted to Glama via "Add Server"
- [ ] Build passes on Glama
- [ ] Score page shows tool scores
- [ ] Published to MCP Registry
- [ ] README has Glama badge

## References

- Glama methodology: https://glama.ai/mcp/methodology
- MCP Registry quickstart: https://modelcontextprotocol.io/registry/quickstart
- zsxh1990's deployment lesson: `lessons/contrib/glama-mcp-server-deploy-lessons.md`
