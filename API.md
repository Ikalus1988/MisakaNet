# MisakaNet API Reference

> **Version:** 2.17.0 | **Protocol:** `misaka-protocol.json`

MisakaNet exposes a multi-surface API: CLI search, MCP tools, GitHub-based contribution endpoints, and optional Hub federation. This document catalogues every supported interface.

---

## 1. CLI Search API (`search_knowledge.py`)

The primary entry point for knowledge retrieval.

### Usage

```bash
python3 search_knowledge.py "<query>" [flags]
```

### Flags

| Flag | Description |
|------|-------------|
| `--lessons` | Search only lesson files |
| `--ref` | Search only reference documents |
| `--titles` | Match against titles only |
| `--domain <name>` | Filter by domain (e.g., `python`, `docker`) |
| `--semantic` | Enable semantic search (requires `sentence-transformers`) |
| `--explain` | Show score breakdowns and match reasons |
| `--json` | Output results as JSON |
| `--top N` | Limit to top N results (default: 10) |
| `--verbose` | Show detailed scoring metadata |

### JSON Output Schema

```json
{
  "title": "Lesson title",
  "domain": "python",
  "tags": ["tag1", "tag2"],
  "score": 0.8765,
  "path": "lessons/domain/filename.md",
  "preview": "First 120 characters...",
  "match_reason": "title + body match",
  "preview_highlighted": "First 120 chars with <mark>...</mark>",
  "confidence": "high",
  "result_type": "lesson",
  "score_breakdown": {
    "bm25": 0.8234,
    "title_boost": 1.5,
    "tag_match": 1.2,
    "final": 0.8765
  }
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success — results returned |
| 1 | Search failed or no results found |

---

## 2. MCP Tools (Model Context Protocol)

Two transports are available: **stdio** (local) and **HTTP/SSE** (remote).

### 2.1 Stdio Transport (`scripts/mcp_server.py`)

```bash
python3 scripts/mcp_server.py
```

Exposes 4 tools via MCP stdio protocol:

| Tool | Parameters | Returns |
|------|-----------|---------|
| `misakanet.search` | `query` (str), `domain?` (str), `top?` (int=5) | Ranked lesson results |
| `misakanet.get_lesson` | `path_or_id` (str) | Full lesson markdown content |
| `misakanet.submit_usage` | `lesson_id` (str), `tool` (str), `outcome` (str) | Confirmation |
| `misakanet.usage_status` | `user?` (str) | Usage statistics |

#### Claude Code Configuration

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["C:/path/to/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

### 2.2 HTTP/SSE Transport (`scripts/mcp_http_server.py`)

```bash
python3 scripts/mcp_http_server.py [--port 8080]
```

Started on `http://localhost:8080/mcp` by default. Compatible with any MCP client supporting Streamable HTTP transport.

#### Cursor / Continue Configuration

```json
{
  "mcpServers": {
    "misakanet-http": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

### 2.3 MCP Protocol Metadata

Server identity advertised at connection:

```json
{
  "name": "misakanet",
  "version": "2.16.0",
  "description": "MisakaNet knowledge search and contribution"
}
```

---

## 3. Contribution API (`scripts/contribute.py`)

Submit lessons directly via GitHub API — no fork or `git push` required.

### Usage

```bash
# Submit a pre-written .md file
python3 scripts/contribute.py path/to/lesson.md

# Create a lesson inline
python3 scripts/contribute.py -t "Title" -d domain --tags "tag1,tag2" "Content body..."
```

### Requirements

- `GITHUB_TOKEN` environment variable (or `~/.git-credentials`)
- PR is created against `Ikalus1988/MisakaNet:main`
- Branch is auto-named `lesson/<slug>`

### API Flow

1. Get default branch SHA (`GET /repos/Ikalus1988/MisakaNet/git/ref/heads/main`)
2. Create blob (`POST /repos/Ikalus1988/MisakaNet/git/blobs`)
3. Create tree (`POST /repos/Ikalus1988/MisakaNet/git/trees`)
4. Create commit (`POST /repos/Ikalus1988/MisakaNet/git/commits`)
5. Create branch ref (`POST /repos/Ikalus1988/MisakaNet/git/refs`)
6. Create PR (`POST /repos/Ikalus1988/MisakaNet/pulls`)

### Queue Lesson API (`scripts/queue_lesson.py`)

```bash
python3 scripts/queue_lesson.py \
  -t "Title" -d domain \
  --tags "node:name,project:name" \
  "Problem\n\n## Root Cause\n...\n\n## Fix\n...\n\n## Verification\n..."
```

---

---

## 6. Verification Tools

### `scripts/misaka_verify.py`

```bash
python3 scripts/misaka_verify.py
```

Validates protocol configuration against `misaka-protocol.json`.

### `scripts/validate_lessons.py`

```bash
python3 scripts/validate_lessons.py [--strict]
```

Checks all lesson frontmatter for schema compliance.

### `scripts/site_health_check.py`

```bash
python3 scripts/site_health_check.py
```

End-to-end health check of deployed services.

---

## 7. Python SDK Imports

```python
# Core search engine
from misakanet.search.engine import MisakaNetSearchEngine, _search_cached, LESSONS

# Lesson scoring
from misakanet.tools.lesson_scorer import score_lessons, format_lesson_scores

# BM25 via ecosystem package
from misakanet_core import BM25, tokenize, rrf

# Node profile
from misakanet.profile import NodeProfile

# Evidence tracking
from misakanet.evidence import EvidenceTracker
```

---

## 8. Rate Limits & Error Handling

- **GitHub API**: Standard rate limits apply (5000 req/h authenticated)
- **MCP stdio**: Single-connection, no built-in rate limiting
- **MCP HTTP**: No built-in rate limiting — use a reverse proxy for production
- **Search**: L1/L2 caching built into `misakanet.search.engine`
- **Notifiers**: Exponential backoff on webhook failures (3 retries, 2s/4s/8s)
