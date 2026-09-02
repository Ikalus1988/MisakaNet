# MisakaNet Python Package

The `misakanet/` package is the importable core of MisakaNet — a git-backed
failure-memory network for AI agents. It provides search, evidence
grading, and the MCP server implementation.

> 2026-08-31: rewritten — the previous "Node/Hub/Knowledge Graph" protocol
> framing described a centralized federation design that was never deployed.
> The project is now positioned purely as a failure-lesson network: agents
> search shared, verified debugging lessons. No hub, no node federation, no
> graph.

## Modules

| Module | Purpose |
|--------|---------|
| `misakanet/search/engine.py` | BM25 search over `lessons/` (pure stdlib), L1/L2 cache, metadata scoring |
| `misakanet/search/embeddings.py` | Optional `--semantic` embeddings (sentence-transformers) |
| `misakanet/evidence.py` | Evidence levels E0–E4 normalization and trust scoring |
| `misakanet/freshness.py` | Lesson freshness decay / recency scoring |
| `misakanet/guard.py` | Secret redaction guard (redact before truncate) |
| `misakanet/profile.py` | Node profile (stage + referral), atomic writes |
| `misakanet/server/` | MCP server implementation (protocol, handlers, tools, resources, prompts) |
| `misakanet/tools/` | Integrations: dashboard, langchain tool, lesson scorer, telemetry |
| `misakanet/graphql/` | GraphQL schema over lesson search |
| `misakanet/scripts/` | Operational scripts (clean pipeline, inject helpers, draft reminders, hook stats) |

## Quick start

```python
from misakanet.search import search_lessons
results = search_lessons("pip install timeout")
for r in results:
    print(r["title"], r["score"])
```

## CLI

```bash
python3 -m misakanet           # usage overview
python3 -m misakanet.search    # (if exposed) search entry
```

## Testing

The package ships with a test suite under `tests/` covering search quality,
evidence grading, MCP protocol, and redaction. Run:

```bash
python3 -m pytest tests/ -q
```
