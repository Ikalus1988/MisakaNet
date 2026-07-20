# Use MisakaNet in 5 Minutes

Three steps: search, contribute, integrate.

---

## Step 1: Search for a Lesson (30 seconds)

```bash
git clone https://github.com/Ikalus1988/MisakaNet.git && cd MisakaNet
pip install misakanet-core
python3 search_knowledge.py "database is locked"
```

> **Windows user?** Run this once to avoid vim popping up during `git pull` / rebase:
> ```powershell
> git config --global pull.rebase true
> git config --global core.editor "notepad"
> ```
> This also works for VS Code: `git config --global core.editor "code --wait"`

Expected output:

```
┌─ Results for: database is locked ─────────────────────────────┐
│ #  Score  Domain        Title                                  │
│ 1  0.89   agent-net     hermes-state-database-lock-cleanup     │
│ 2  0.74   infra         sqlite-wal-mode-crash-recovery         │
│ 3  0.61   contrib       agent-state-database-lock-cleanup      │
└───────────────────────────────────────────────────────────────┘
```

Useful flags:

| Flag | Effect |
|------|--------|
| `--top=5` | Limit results |
| `--domain=infra` | Filter by domain |
| `--lang=en` | English results only |
| `--titles` | One line per result |

Common failure: `ModuleNotFoundError: No module named 'misakanet_core'`.

Fix: `pip install misakanet-core` (not `misakanet`). The core engine is a separate PyPI package.

---

## Step 2: Contribute a Lesson (2 minutes)

**Option A — PR via API (no fork needed):**

```bash
python3 scripts/queue_lesson.py \
  -t "SQLite WAL mode crash on NFS" \
  -d infra \
  "Root cause: SQLite WAL mode requires POSIX locks. NFS does not support them.
   Fix: switch to DELETE journal mode: PRAGMA journal_mode=delete.
   Verification: run 100 concurrent writes on NFS mount, no crash."
```

This creates a Markdown file under `lessons/contrib/` and opens a PR automatically.

**Option B — Manual PR:**

```bash
# 1. Fork the repo on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USER/MisakaNet.git && cd MisakaNet

# 3. Create a lesson file
cat > lessons/contrib/my-error-fix.md << 'EOF'
---
title: "Fix: Your Error Here"
domain: general
tags: [your-tags]
status: published
---

## Problem
Describe the error.

## Root Cause
What actually caused it.

## Solution
Copy-pasteable fix commands.

## Verification
How to confirm the fix works.
EOF

# 4. Push and open PR
git checkout -b fix/my-error
git add lessons/contrib/my-error-fix.md
git commit -m "feat: add lesson for my-error-fix"
git push origin fix/my-error
# Then open PR on GitHub targeting Ikalus1988/MisakaNet main
```

**Lesson quality checklist** (see `docs/lesson-checklist.md` for full list):

- [ ] Exact error message or traceback included
- [ ] Root cause explained (not just "it broke")
- [ ] Solution is copy-pasteable
- [ ] Verification steps confirm the fix

---

## Step 3: Integrate with Your Agent (2 minutes)

**Python (LangChain):**

```python
from misakanet.tools.langchain_tool import MisakaNetSearchTool

tool = MisakaNetSearchTool()
results = tool._run("database locked")
print(results)
```

**MCP Server (for Claude Code, Cursor, etc.):**

```bash
# Start the MCP server
python3 scripts/mcp_server.py

# In your MCP client config:
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["scripts/mcp_server.py"],
      "cwd": "/path/to/MisakaNet"
    }
  }
}
```

**Direct import (no framework):**

```python
from misakanet_core import BM25, tokenize

# Load lessons, tokenize, search
# See misakanet/search/engine.py for the full API
```

Common failure: `ModuleNotFoundError: No module named 'misakanet'`.

Fix: run `pip install -e .` from the repo root, then retry.

---

## What's Next?

| Goal | Go to |
|------|-------|
| Understand the architecture | `docs/CONCEPTS.md` |
| Set up a federation node | `docs/agents/quickstart.md` |
| Run the benchmark suite | `scripts/bench_orchestrator.py` |
| Join the network | `JOIN.md` |
