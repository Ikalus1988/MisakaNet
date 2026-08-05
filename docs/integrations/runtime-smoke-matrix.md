# Runtime Failure-Memory Smoke Test Matrix

Date: 2026-08-03
Version: v2.14.0
Related issue: #757

## Entry points

MisakaNet provides four runtime entry points for failure-memory suggestions:

| Entry point | File | Trigger |
|---|---|---|
| Cursor rule | `.cursor/rules/misakanet-failure-memory.mdc` | IDE auto-detects terminal failures |
| Claude Code playbook | `docs/integrations/claude-code-failure-memory.md` | Manual or prompted failure analysis |
| `misaka run` wrapper | `scripts/misaka_run.py` | CLI: wrap any command |
| Shell helper | `scripts/misaka-search.sh` | CLI: `misaka-search "query"` or `mk "query"` |

---

## 1. Cursor Rule

### Setup

1. Confirm `.cursor/rules/misakanet-failure-memory.mdc` exists in your project root (already present in this repo).
2. Open the project in Cursor IDE.
3. The rule activates automatically — no manual config needed.

### Trigger

Run a failing command in Cursor's integrated terminal:

```bash
npm run nonexistent-script
# or
python -c "import nonexistent_module"
```

### Expected behavior

Cursor should detect the non-zero exit and surface the failure-memory rule. The rule instructs Cursor to search MisakaNet for matching failure-recovery lessons.

### Limitations

- Cursor IDE only (not VS Code, not JetBrains).
- Rule must be in `.cursor/rules/` — not `.cursorrules` (deprecated format).
- Depends on Cursor's rule execution model, which may change.
- First-time failures with no matching lessons will return empty.

---

## 2. Claude Code Playbook

### Setup

1. Review `docs/integrations/claude-code-failure-memory.md`.
2. The playbook is a prompt/workflow document — it tells Claude Code how to invoke MisakaNet MCP tools on failure.

### Trigger

After a failure in Claude Code's terminal, ask:

```
Check MisakaNet for this error.
```

Claude Code should call `misakanet_search` via MCP.

### Expected behavior

Claude Code calls `misakanet_search` with the error text and returns matching lessons with titles, scores, and paths.

### Limitations

- Requires Claude Code with MCP support configured.
- MCP server must be running (`python scripts/mcp_server.py`).
- Depends on Claude Code's willingness to call MCP tools.
- Not fully automatic — user or playbook must trigger the search.

---

## 3. `misaka run` Wrapper

### Setup

```bash
# No install needed — run directly from repo
python scripts/misaka_run.py --help
```

### Trigger

```bash
python scripts/misaka_run.py npm test
python scripts/misaka_run.py python failing_script.py
python scripts/misaka_run.py --capture cargo build  # auto-submit intake on failure
```

### Expected behavior

On non-zero exit:
1. Captures stdout/stderr from the failed command.
2. Searches MisakaNet lessons for matching failure patterns.
3. Displays top matches with title, score, and path.

Options:
- `--capture` — auto-submit redacted failure report as intake (opt-in).
- `--top N` — number of lessons to show (default: 3).

### Limitations

- Adds overhead (subprocess + search).
- Interactive commands may behave differently when wrapped.
- Search quality depends on error message clarity.
- `--capture` sends data to `/api/intake` — only use if you understand the privacy model.

---

## 4. Shell Helper (`misaka-search.sh`)

### Setup

```bash
source scripts/misaka-search.sh
```

This defines two functions: `misaka-search` and `mk`.

### Trigger

```bash
misaka-search "database locked"
mk "pip install timeout"
```

### Expected behavior

Calls `search_knowledge.py` with the query and displays matching lessons.

### Limitations

- Bash/Zsh only.
- Must be sourced (not executed) — `bash misaka-search.sh` won't work.
- Calls Python internally, so Python must be in PATH.
- No color output on Windows CMD.

---

## Smoke test checklist

Run each entry point and verify:

| # | Entry point | Command | Pass criteria |
|---|---|---|---|
| 1 | Cursor rule | Open project in Cursor, run `python -c "import nonexistent"` | Rule triggers, Cursor shows suggestion or search prompt |
| 2 | Claude Code | After a failure, ask "check MisakaNet" | MCP `misakanet_search` returns results |
| 3 | `misaka run` | `python scripts/misaka_run.py false` | Shows "Command failed" + lesson matches |
| 4 | Shell helper | `source scripts/misaka-search.sh && misaka-search "database locked"` | Returns lesson results |

## Related docs

- Cursor integration: `docs/integrations/cursor-failure-memory.md`
- Claude Code integration: `docs/integrations/claude-code-failure-memory.md`
- MCP smoke report: `docs/integrations/mcp-smoke-report.md`
- Glama analytics: `docs/integrations/glama-analytics.md`
