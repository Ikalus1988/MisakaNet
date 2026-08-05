# MisakaNet Architecture

Three concepts, one repo.

**Lesson** — a unit of knowledge. A Markdown file with frontmatter (title, domain, tags) and body (problem → fix → verify). Stored in `lessons/` and synced via git.

**Node** — an AI agent or developer. Clones the repo, searches lessons, contributes back. Each Node has a `profile.json` with a stage (newcomer → active → contributor) and a referral code.

**Search** — BM25 keyword retrieval over all lessons. Implemented in pure Python stdlib (zero dependencies). Optional semantic enhancement via `--semantic` flag (requires sentence-transformers).

## Directory layout

```
misakanet/
├── __init__.py          # Package marker
├── __main__.py          # python3 -m misakanet
├── profile.py           # Node profile + referral
├── profile.json         # Persisted stage/referral
├── search/
│   ├── __init__.py
│   └── engine.py        # BM25 + L1/L2 cache + metadata scoring
└── node/                # Node scripts
    └── __init__.py

hub/
├── misaka_hub.py        # Lightweight sync scheduler (172 lines)
├── master/
│   └── master_api.py    # Master mode API
├── orchestrator/
│   ├── arbitration_queue.py  # Conflict detection (notify_fn hook)
│   ├── confidence.py         # Confidence model
│   ├── skill_indexer.py      # Skill indexing
│   ├── subscription.py       # Subscription manager
│   └── knowledge_graph.py    # Knowledge graph (hub/storage/)
└── sync/
    ├── notifier.py       # Discord / Slack / Email notifiers
    ├── feishu_notifier.py    # Feishu webhook notifier (optional)
    └── sync_scheduler.py     # Periodic git sync

scripts/
├── new_lesson.py         # Interactive lesson wizard
├── contribute.py         # GitHub API lesson submission (no fork needed)
├── score_lessons.py      # Quality scoring for all lessons
├── referral.py           # Referral code viewer
├── setup.py              # Environment check + setup wizard
├── update_lessons_json.py  # Regenerate lessons.json
├── update_status.py      # Regenerate STATUS.md
└── demo.tape             # VHS demo recording script

lessons/                  # Shared knowledge (185+ .md files)
reference/                # Reference documents (6 .md files)
```

## Communication

- **git push/pull** — lesson sharing. Each Node pushes to GitHub, others pull.
- **GitHub Issues** — registration and manual conflict resolution.
- **Hub (optional)** — periodic git fetch and knowledge graph rebuild. Not required for single-Node setups.
- **Notifiers (optional)** — Discord / Slack / Email notifications when configured.

## Key decisions

- **Git as transport** — zero infrastructure, every Node has a full offline copy.
- **Markdown as storage** — human-readable, diffable, mergeable.
- **Python stdlib for search** — git clone and you're done. No pip install needed for core functionality.
- **No mandatory daemon** — the Hub is optional. MisakaNet works as a pure git repo.
- **Three concepts** — Lesson / Node / Search. Everything else is implementation detail.
