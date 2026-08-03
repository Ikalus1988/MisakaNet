# MisakaNet Runtime Smoke Matrix

Document runtime failure-memory entry points with smoke test procedures.

**Test date:** 2026-08-03
**Version:** v2.14.0
**Related issue:** #757

## Entry Points Covered

| # | Entry Point | File | Type |
|---|-------------|------|------|
| 1 | Cursor rule | `.cursor/rules/misakanet-failure-memory.mdc` | Cursor rules |
| 2 | Claude Code playbook | `docs/integrations/claude-code-failure-memory.md` | CLAUDE.md snippet |
| 3 | `misaka run` wrapper | `scripts/misaka_run.py` | CLI wrapper |
| 4 | `misaka-search.sh` helper | `scripts/misaka-search.sh` | Shell script |

---

## Entry Point 1: Cursor Rule

**File:** `.cursor/rules/misakanet-failure-memory.mdc`

### Install

```bash
# Copy the rule to your project
cp .cursor/rules/misakanet-failure-memory.mdc your-project/.cursor/rules/
```

Or via MCP (recommended):

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

### How to trigger

1. Make any build/test command fail in Cursor (e.g. `python -m pytest` with a failing test)
2. Cursor reads the `.mdc` rule and triggers a MisakaNet search automatically

Or manually:

```bash
python3 search_knowledge.py "database locked"
```

### Expected output

```
┌─ Results for: database locked ─────────────────────────────┐
│ #  Score  Domain        Title                              │
│ 1  0.89   agent-net     hermes-state-database-lock-cleanup │
│ 2  0.74   infra         sqlite-wal-mode-crash-recovery   │
└───────────────────────────────────────────────────────────┘
```

### Known limitations

- Requires `MISAKANET_REPO` or `misakanet.repoPath` to point to the lesson directory
- Raw logs are never uploaded; only redacted error keywords are searched
- MCP mode requires Claude Desktop or Cursor (not plain `claude` CLI)

---

## Entry Point 2: Claude Code Playbook

**File:** `docs/integrations/claude-code-failure-memory.md`

### Install

Add the following to your project's `CLAUDE.md`:

```markdown
## Failure Memory (MisakaNet)

After two failed attempts at fixing the same error, search MisakaNet before trying a third fix.

### When to search
- Command exits non-zero twice
- Same test fails twice
- DCO sign-off, GitHub token, pip, MCP errors

### How to search
python3 search_knowledge.py "<error keywords>"
```

### How to trigger

Run any failing command in Claude Code twice — after the second failure, run:

```bash
python3 search_knowledge.py "<your error>"
```

### Expected output

List of matching lessons with title, score, and fix path.

### Known limitations

- Requires local MisakaNet checkout or `pip install misakanet-core`
- Claude Code must be invoked from the MisakaNet repo root (or `$MISAKANET_REPO` set)

---

## Entry Point 3: `misaka run` Wrapper

**File:** `scripts/misaka_run.py`

### Install

```bash
# From MisakaNet repo
pip install -e .

# Or run directly
python3 scripts/misaka_run.py --help
```

### How to trigger

Prefix any command with `misaka run`:

```bash
python3 scripts/misaka_run.py -- python -m pytest
python3 scripts/misaka_run.py -- git commit -m "fix"
python3 scripts/misaka_run.py -- npm test
```

On non-zero exit, it automatically:
1. Captures stderr tail
2. Redacts secrets
3. Searches MisakaNet for matching lessons
4. Prints top 3 lessons

### Expected output

```
[misaka] Command failed (exit 1). Searching MisakaNet...
┌─ Results ─────────────────────────┐
│ #1  0.87  infra  sqlite-wal-fix  │
│ #2  0.72  agent  db-lock-cleanup │
└───────────────────────────────────┘
```

### Known limitations

- Does NOT auto-retry the command
- Does NOT upload logs or secrets
- Only searches, never modifies

---

## Entry Point 4: `misaka-search.sh`

**File:** `scripts/misaka-search.sh`

### Install

```bash
# Make executable and add to PATH
chmod +x scripts/misaka-search.sh
cp scripts/misaka-search.sh /usr/local/bin/misaka-search

# Or run from repo
./scripts/misaka-search.sh "database locked"
```

### How to trigger

```bash
misaka-search "database locked"
misaka-search "DCO sign-off"
misaka-search "pip timeout"
```

### Expected output

Same table format as `search_knowledge.py` (BM25 scored results with title and domain).

### Known limitations

- Requires `search_knowledge.py` in the same directory or in `$PATH`
- Shell-only (no Windows CMD/PowerShell equivalent without WSL)

---

## Smoke Test Checklist

| Entry Point | Install | Trigger | Output | Limitation Check |
|-------------|---------|---------|--------|-----------------|
| Cursor rule | ✅ | ✅ | ✅ | ✅ |
| Claude Code playbook | ✅ | ✅ | ✅ | ✅ |
| `misaka run` | ✅ | ✅ | ✅ | ✅ |
| `misaka-search.sh` | ✅ | ✅ | ✅ | ✅ |

All 4 entry points verified working as of 2026-08-03 (v2.14.0).

---

## Related

- [Cursor Failure Memory](cursor-failure-memory.md)
- [Claude Code Failure Memory](claude-code-failure-memory.md)
- [MCP Smoke Report](mcp-smoke-report.md)
- [MCP Quickstart](../mcp-quickstart.md)
