# MHS Watch — Anthropic Model Hardware Standard ecosystem monitor

GitHub scanner that alerts when launch partners of Anthropic's
[Model Hardware Standard](https://www.anthropic.com/news/model-hardware-standard-research-preview)
(MHS, announced 2026-08-27) ship their first MHS-specific commits, pull
requests, or issues. Built for the Medici Collective's research-preview
preparation workflow.

## What it watches

Default tracked repos (in `scripts/mhs_watch_config.json`):

| Repo | Why |
|---|---|
| `anthropics/anthropic-sdk-python` | First place an MHS Python client would land |
| `huggingface/lerobot` | Confirmed MHS adopter (Anthropic announcement) |
| `strands-agents/strands-agents` | AWS Strands Robots, private MHS preview |
| `mbfbioscience/scanimage` | MBF Bioscience building MHS driver for microscopy |
| `UniversalRobots/Universal_Robots_ROS2_Driver` | Universal Robots, early MHS access |
| `raspberrypi/picamera2` | Raspberry Pi enabling MHS across products |
| `doosan-robotics/doosan-robotics` | Doosan Robotics, robotic arm testing |
| `Qiagen/QIAconnect` | QIAGEN, nucleic acid platform |
| `tecanteam/tecan` | Tecan, Fluent liquid handlers |
| `modelcontextprotocol/*` | MCP is the MHS transport — watch for MHS-aware SDK changes |

Plus vendor-specific keywords (`QuEra MHS`, `Tetsuwan MHS`, `Alek Kemeny`,
`Arco Bast`, `mhs-governance`, etc.) so early chatter at launch-partner
repos also fires.

## Install / run

No external dependencies — stdlib Python 3 only.

```bash
# one-shot scan, prints hits to stdout, appends to .cache/mhs-watch/hits.jsonl
python3 scripts/mhs_watch.py once

# daemon mode, scan every hour
python3 scripts/mhs_watch.py daemon --interval 3600

# inspect last scan
python3 scripts/mhs_watch.py status

# tail recent hits (formatted)
python3 scripts/mhs_watch.py tail -n 20
```

For crash-safe daemon (per `AGENTS.md`):

```bash
npx @misaka-net/fatal-guard -- python3 scripts/mhs_watch.py daemon --interval 3600
```

## Environment variables

| var | default | effect |
|---|---|---|
| `MHS_WATCH_HOME` | `<repo>/.cache/mhs-watch` | state + log directory |
| `MHS_WATCH_GITHUB_TOKEN` | (none) | bumps GitHub rate limit 60/hr → 5000/hr |
| `MHS_WATCH_WEBHOOK_URL` | (none) | POST scan results to this URL on each hit |
| `MHS_WATCH_CONFIG` | `scripts/mhs_watch_config.json` | config path |
| `MHS_WATCH_VERBOSE` | (unset) | log INFO-level events to stderr |

## Configuration

`scripts/mhs_watch_config.json` controls:

- `repos` — list of `owner/name` strings (any GitHub repo)
- `keywords` — list of substrings; case-insensitive; matched against
  title + body / commit message; first match wins
- `kinds` — which event types to scan (`commits`, `pulls`, `issues`,
  `discussions` — last one is not yet implemented)
- `lookback_days` — API `since` cutoff; defaults to 14
- `min_confidence` — minimum distinct-keyword hits to fire (default 1)
- `seen_cap` — max ids retained per (repo, kind) for dedup (default 2000)

Edit the JSON to add new repos or tighten keywords as the ecosystem
evolves. The config is committed to the repo (in-repo knowledge), but
state lives in `.cache/` (gitignored).

## Output schema

Each hit is one JSON line in `.cache/mhs-watch/hits.jsonl`:

```json
{
  "ts": "2026-09-03T00:36:00Z",
  "scan_id": "0b13eeb01d5a",
  "repo": "huggingface/lerobot",
  "kind": "pull_request",
  "id": "12345678",
  "number": 1325,
  "title": "feat: add MHS driver for SO-100 arm",
  "url": "https://github.com/huggingface/lerobot/pull/1325",
  "author": "remicadene",
  "created_at": "2026-09-02T...",
  "matched_keywords": ["MHS"],
  "confidence": 1,
  "snippet": "..."
}
```

Sort by `ts` to see newest first; filter by `kind` to separate
PR-only alerts from commit / issue chatter.

## Rate limits & noise

- **Unauthenticated**: 60 GitHub API requests/hour. With 17 default
  repos × 3 endpoints ≈ 51 calls/scan, leave at least 1 hour between
  scans if you don't set `MHS_WATCH_GITHUB_TOKEN`.
- **Authenticated** (set `MHS_WATCH_GITHUB_TOKEN`): 5000/hr, scan as
  often as every 5 minutes if needed.
- **False positives**: substring matching will fire on tangential uses
  (e.g. a commit message mentioning "anthropic" for unrelated reasons).
  Tighten `keywords` (drop short generics) or raise `min_confidence`
  to suppress. The keywords already favor multi-word or hyphenated
  phrases over single words where possible.

## Failure modes

- **Network drop**: scanner retries once with backoff, then logs and
  skips the repo. State is preserved.
- **Repo deleted / private**: 404 is logged and skipped.
- **Rate limited**: scanner logs `X-RateLimit-Remaining` and skips
  remaining repos; next scan recovers automatically after reset.
- **Crash mid-scan**: `fatal-guard` (recommended) catches the traceback
  and persists a tombstone. State up to the last completed repo is
  saved before crash.

## Workflow with the rest of MisakaNet

- Each hit goes to `.cache/mhs-watch/hits.jsonl`.
- A weekly cron (`scripts/mhs_watch.py daemon --interval 3600` + log
  rotation) feeds the Medici Collective's RFC research.
- A future bench task could auto-extract hits.jsonl into a MisakaNet
  lesson via `queue_lesson.py` (TODO: link when written).