# DeepSeekHarness Integration Smoke Report

**Date:** 2026-08-15
**Issue:** #1042
**Git SHA:** 8697f66
**Environment:** Windows 11 Pro (10.0.26200), Python 3.11.9, MisakaNet v2.17.0

---

## CLI Checks

### doctor

```bash
python3 scripts/misakanet_cli.py doctor
```

**Exit code:** 0

```json
{
  "command": "doctor",
  "version": "2.17.0",
  "overall": "healthy",
  "checks": [
    {"name": "lessons.json", "status": "ok", "count": 289},
    {"name": "sag.db", "status": "ok"},
    {"name": "lessons/", "status": "ok", "count": 418},
    {"name": "search_engine", "status": "bm25"}
  ]
}
```

### smoke

```bash
python3 scripts/misakanet_cli.py smoke
```

**Exit code:** 0

```json
{
  "command": "smoke",
  "version": "2.17.0",
  "overall": "pass",
  "elapsed_ms": 128,
  "tests": {
    "search": {"status": "ok", "result_count": 3, "source": "sag-lite"},
    "get_lesson": {"status": "ok", "content_length": 3832, "path": "lessons/core/dco-auto-fix-workflow.md"}
  }
}
```

### validate

```bash
python3 scripts/misakanet_cli.py validate
```

**Exit code:** 0

```json
{
  "command": "validate",
  "version": "2.17.0",
  "overall": "pass",
  "checks": [
    {"name": "mcp_server", "status": "ok", "tool_count": 4, "tools": ["misakanet_search", "misakanet_get_lesson", "misakanet_submit_usage", "misakanet_usage_status"]},
    {"name": "deepseek_adapter", "status": "ok", "tool_count": 6, "tools": ["deepseek.recovery.search", "deepseek.recovery.get_lesson", "deepseek.recovery.submit_feedback", "deepseek.recovery.status", "deepseek.recovery.doctor", "deepseek.recovery.smoke"]},
    {"name": "SKILL.md", "status": "ok"},
    {"name": "pyproject.version", "status": "ok", "value": "2.17.0"}
  ]
}
```

---

## MCP Adapter Tools

**Tool count:** 6

| Tool | Description |
|------|-------------|
| `deepseek.recovery.search` | Search failure-recovery lessons |
| `deepseek.recovery.get_lesson` | Fetch a specific lesson |
| `deepseek.recovery.submit_feedback` | Record that a lesson helped |
| `deepseek.recovery.status` | Check plugin status |
| `deepseek.recovery.doctor` | Health check |
| `deepseek.recovery.smoke` | Minimal smoke test |

---

## Search Round-trip

```json
{
  "tool": "deepseek.recovery.search",
  "arguments": {"query": "DCO", "top": 3}
}
```

**Result:** 3 lessons returned

| Title | Path |
|-------|------|
| DCO Auto-Fix Workflow | lessons/core/dco-auto-fix-workflow.md |
| Agent Competition Issue Flywheel: DCO Guard | lessons/contrib/agent-competition-issue-flywheel-dco-guard.md |
| GitHub Actions CI for AI Agent PRs — DCO decoupling | lessons/contrib/ci-dco-decouple-pythonpath-fork-pr.md |

---

## Get Lesson Round-trip

```json
{
  "tool": "deepseek.recovery.get_lesson",
  "arguments": {"path": "lessons/core/dco-auto-fix-workflow.md"}
}
```

**Result:**
- Path: `lessons\core\dco-auto-fix-workflow.md`
- Content length: 3832 chars
- First 200 chars: `--- { "title": "DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation", "domain": "devops", "tags": ["github-actions", "dco", "signoff", "issue-comment", "auto-fi...`

---

## Summary

| Check | Status | Exit Code |
|-------|--------|-----------|
| doctor | ✅ healthy | 0 |
| smoke | ✅ pass | 0 |
| validate | ✅ pass | 0 |
| adapter tools | ✅ 6 tools | — |
| search round-trip | ✅ 3 results | — |
| get_lesson round-trip | ✅ 3832 chars | — |

**Overall:** ✅ All checks passed. DeepSeekHarness integration is functional.

---

## Fallback Behavior

- SAG-Lite FTS keyword conflicts (e.g. "off", "and") → graceful error with hint
- Search engine unavailable → falls back to BM25 or keyword match
- Lesson path not found → returns error with search suggestion
- Adapter errors → returns structured error JSON, no crash
