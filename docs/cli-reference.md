# CLI Reference — MisakaNet

## `search_knowledge.py` — Core Search Tool

```bash
python3 search_knowledge.py <query> [options]
```

| Argument | Target | Description | Example |
|----------|--------|-------------|---------|
| `query` | (positional) | Search keywords | `python3 search_knowledge.py "pip install timeout"` |
| `--lessons` | Mode | Switch to lesson search mode (not a path/id filter) | `--lessons` |
| `--ref` | Mode | Switch to reference search mode (not a path/id filter) | `--ref` |
| `--top=<N>` | Pagination | Show top N results (default: 10) | `--top=3` |
| `--titles` | Display | Show titles only | `--titles` |
| `--json` | Display | Emit a JSON array with `title`, `domain`, `tags`, `score`, `path`, and `preview`; each result also carries `freshness` (`{score, tier, badge}`) when the freshness computation succeeds; errors are JSON objects | `"pip timeout" --json \| jq '.[0]'` |
| `--broad` | Matching | Broader keyword matching | `--broad` |
| `--suggest` | Mode | List matching titles (≥2 chars) | `--suggest` |
| `--semantic` | Mode | Use sentence-transformers _(optional dep)_ | `--semantic` |
| `--score` | Mode | Lesson quality scoring from telemetry | `--score --top=5` |
| `--telemetry=<path>` | Scoring | Custom telemetry DB path | `--telemetry=/tmp/t.db --score` |
| `--explain` | Search | Show BM25/Meta/Base score breakdown | `--explain` |
| `--verbose` | Search | Alias for `--explain`; JSON output includes `score_breakdown` | `--verbose --json` |
| `--env=<env>` | Filter | Filter by environment tag (wsl2, docker, ...) | `--env=wsl2` |
| `--domain=<d>` | Filter | Filter by domain (devops, rag, ...) | `--domain=devops` |
| `--lang=<lang>` | Filter | Filter by language | `--lang=zh` |
| `--heal` | Mode | Diagnose error logs from file/stdin | `--heal error.log` |
| `--harvest --from-file=<f>` | Mode | Parse log for errors → draft lesson | `--harvest --from-file=crash.log` |

**Exit codes:** `0` = results found, `1` = no results or error.

### `freshness` is not the same measure in both tools

Two surfaces in this repository publish a field called `freshness`, and they do not mean the same
thing — one is a **score** and one is an **age**:

| surface | shape | how it is computed | values |
|---|---|---|---|
| this CLI (`--json`) | `{"score": 0-100, "tier": "fresh", "badge": "🟢"}` | `misakanet/freshness.py` — a score that decays daily, with boosts for usage, votes, edits and pins | `fresh` / `stable` / `aging` / `stale` / `outdated` |
| the MCP tool (`misakanet_search`) | `"fresh"` — a plain string | `misakanet/server/handlers/search.py::_freshness` — days since the lesson was updated | `fresh` (<30d) / `recent` (<180d) / `aging` (<365d) / `stale` / `unknown` |

Three of the names are shared and **their boundaries are not**: a lesson updated ten days ago can
be `fresh` by age and `stable` by score. They are two independent implementations of one idea, so
do not compare the two values — and note that the MCP one is a string while this one is an object.
(Hand-off §124.9: unifying them is a product decision, not a documentation fix.)

`--json` keeps standard output machine-readable, so it can be piped directly to
tools such as `jq`:

```bash
python3 search_knowledge.py "database locked" --json --top=3 | jq '.[].path'
```

## Other CLI Tools

| Command | Description |
|---------|-------------|
| `python3 scripts/new_lesson.py` | Interactive lesson generator |
| `python3 scripts/queue_lesson.py` | Queue a lesson via CLI args |
| `python3 scripts/tombstone_to_draft.py --from-file <f>` | fatal-guard tombstone → draft lesson |
| `python3 scripts/bench_orchestrator.py [--include-drafts]` | Agent benchmark runner (Phase B/C) |
| `python3 scripts/contribute.py --wizard` | 7-step interactive lesson creation wizard |
| `python3 scripts/check_worker_secrets.py` | Scan workers/ for hardcoded secrets |
| `python3 scripts/site_health_check.py [--write] [--strict]` | Public site + Worker health snapshot (read-only probes) |
| `python3 search_knowledge.py --score` | Telemetry-based lesson ranking |
| `python3 -m misakanet.tools.dashboard` | Launch telemetry dashboard (stdlib HTTP server) |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `MISAKANET_HOME` | `~/.misakanet` | Data directory (cache, telemetry DB) |
| `MISAKANET_TELEMETRY` | `$MISAKANET_HOME/langchain_telemetry.db` | Telemetry database path |

