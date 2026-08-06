# MisakaNet

> **A redacted failure-memory layer for AI coding agents.**
>
> Paste an error from Cursor, Claude Code, Codex, or CI.
> MisakaNet searches real failure-recovery lessons and returns a fix path.

mcp-name: io.github.Ikalus1988/misakanet

<p align="center">
  <img src="promotional/og-card.png" width="720" alt="MisakaNet — Failure Memory for AI Agents"/>
</p>

[![CI](https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-quality-gate.yml/badge.svg)](https://github.com/Ikalus1988/MisakaNet/actions/workflows/pr-quality-gate.yml)
[![PyPI](https://img.shields.io/pypi/v/misakanet-core)](https://pypi.org/project/misakanet-core/)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/Ikalus1988/MisakaNet?style=flat&color=blueviolet)](https://github.com/Ikalus1988/MisakaNet/blob/main/LICENSE)
[![Glama score](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/badges/score.svg)](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/score)
[![MCP Quickstart](https://img.shields.io/badge/MCP-quickstart-green)](docs/mcp-quickstart.md)
[![Stars](https://img.shields.io/github/stars/Ikalus1988/MisakaNet?style=social)](https://github.com/Ikalus1988/MisakaNet/stargazers)
[![MCP Toplist: Top 1% of 81,852](https://mcptoplist.com/badge/io.github.Ikalus1988%2Fmisakanet.svg)](https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet)

---

### What is this?

MisakaNet is a failure-memory layer for AI coding agents. When your agent hits an error — DCO failure, pip timeout, GitHub 401, MCP setup issue — MisakaNet searches 249 indexed failure-recovery lessons and returns a fix path. No prompt leaking, no raw logs stored.

### When to use it

- Cursor / Claude Code / Codex hits an error you haven't seen before
- CI fails and you don't know why
- DCO, token, pip, MCP, encoding issues repeat across projects

### Try it in 30 seconds

**Option A: MCP (Cursor / Claude Desktop / Claude Code)**

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["scripts/mcp_server.py"]
    }
  }
}
```

Then ask: *"Search MisakaNet for database locked"*

Expected output:

```
Results for "database locked" (source: sag-lite):
  1. Hermes State Database Lock Issues — Cleanup Protocol  (score: 8.32)
  2. SQLite database is locked — WAL checkpoint fix        (score: 6.14)
```

**Option B: CLI**

```bash
pip install misakanet-core
python3 search_knowledge.py "GitHub token 401"
```

**Option C: Docker (no local Python needed)**

```bash
docker pull ghcr.io/ikalus1988/misakanet:latest
docker run -i ghcr.io/ikalus1988/misakanet:latest search_knowledge.py "database locked"
```

Use cases: CI smoke test, isolated trial, Claude Desktop MCP config with Docker.

**Option D: Web**

[Search failure lessons →](https://ikalus1988.github.io/MisakaNet/search/)

**Full quickstart:** [docs/quickstart.md](docs/quickstart.md) · Troubleshooting: [docs/troubleshooting.md](docs/

<!-- BOOST: Enhanced documentation for ranking -->
## 🚀 Quick Start

### Prerequisites
- Node.js >= 18 (or Python >= 3.10)
- Git

### Installation
```bash
git clone https://github.com/MyZubster-Ecosystem/MisakaNet.git
cd MisakaNet
```

### Development
```bash
npm install  # or pip install -r requirements.txt
npm test
npm run dev
```

## 📊 Quality
- ✅ CI/CD pipeline with automated testing
- ✅ Linting & code quality checks

## 🤝 Contributing
See [CONTRIBUTING.md](./CONTRIBUTING.md).

## 📄 License
See [LICENSE](./LICENSE) file.
