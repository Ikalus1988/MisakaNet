# SAG vs CLI Comparison Report — 2lll5

## Environment
- OS: Linux z-bot 6.8.0-117-generic x86_64 (Ubuntu kernel)
- Browser (for homepage): HeadlessChrome 148.0.0.0 via Puppeteer Core, visiting live `https://misakanet.org/` and typing into `#search-input`.
- Python version: Python 3.11.15

## Comparison

| Query | Homepage top result | CLI top result | Match? | Notes |
|-------|-------------------|---------------|--------|-------|
| pip timeout | `pip install HTTPS Timeout from WSL — Prepend HTTPS_PROXY=http://172.19.128.1:7890` | `pip install HTTPS Timeout from WSL — Prepend HTTPS_PROXY=http://172.19.128.1:7890` | Yes | Homepage and CLI agree on the top result. Homepage showed three tied SAG-Lite scores for pip/network timeout lessons; the first item matches CLI ordering. |
| database locked | `Hermes State Database Lock Issues - Cleanup Protocol` | `Hermes State Database Lock Issues - Cleanup Protocol` | Yes | Both rank the same duplicated title first (`hermes-state-database-lock-issues-cleanup-protocol.md`), followed by the `hx-...` duplicate. |
| fatal guard tombstone | `OPENCLAW_ERROR_HANDLER — Standard protocol for CLI fatal error external hooks` | `OPENCLAW_ERROR_HANDLER — Standard protocol for CLI fatal error external hooks` | Yes | Top result matches. Both methods also surface `MisakaNet --heal Engine Bootstrap Workflow` and `Swarm PR Battle Playbook` in the top group, though second/third ordering differs. |

## Issues found

- No significant top-result differences for the three requested queries.
- Minor observation: for `fatal guard tombstone`, the homepage SAG-Lite scoring and CLI search agree on the top result, but rank the second and third related lessons in a different order.
- Minor observation: `database locked` has two very similar top entries with the same title, so users may see duplicate-looking results even when both search paths agree.

## Suggestion

- Keep homepage SAG-Lite and CLI search as-is for these queries; no blocking mismatch was found.
- Consider adding a future deduplication pass for near-identical lesson titles such as the two `Hermes State Database Lock Issues - Cleanup Protocol` entries.

## Validation commands

```bash
PYTHONIOENCODING=utf-8 python3 search_knowledge.py "pip timeout" --top 3
PYTHONIOENCODING=utf-8 python3 search_knowledge.py "database locked" --top 3
PYTHONIOENCODING=utf-8 python3 search_knowledge.py "fatal guard tombstone" --top 3
```

Homepage results were checked by fetching the live homepage/data and applying the same `searchLessons()` scoring logic from `docs/index.html` to the live `/data/lessons.json` payload (199 lessons).
