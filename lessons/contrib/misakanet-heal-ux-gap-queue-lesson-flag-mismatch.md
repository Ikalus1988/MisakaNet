---
{
  "domain": "contrib",
  "title": "MisakaNet --heal UX Gap — Suggested queue_lesson.py Command Uses Wrong Flag",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "MisakaNet --heal UX Gap — Suggested queue_lesson.py Command Uses Wrong Flag (--file not -f)", "domain": "development", "scope": "broad", "tags": ["misakanet", "heal", "ux", "queue-lesson", "cli", "argparse", "fixture", "openclaw", "flag-mismatch"], "status": "published", "confidence": "0.9", "source": "Misaka10004", "created": "2026-06-23", "updated": "2026-06-23"}---

# MisakaNet --heal UX Gap — Suggested queue_lesson.py Command Uses Wrong Flag

## Problem

`search_knowledge.py --heal` (line 188-194) prints suggested `queue_lesson.py` commands to help agents submit a lesson for an unmatched signature. The suggested command has **three CLI flag mismatches** with the actual `scripts/queue_lesson.py` argparse definition, causing copy-paste submission to silently fail or produce wrong-domain lessons:

| Position | What `--heal` suggests | What `queue_lesson.py` actually accepts | Consequence |
|----------|------------------------|----------------------------------------|-------------|
| 1 | `-f <fixture>` | `--file <fixture>` (no `-f` short form) | `unrecognized arguments: -f tests/fixtures/openclaw/unmatched_*.log` |
| 2 | `-d openclaw` | `-d`/`--domain` accepts freeform string, **but** `openclaw` is **not in `lessons/index.md`** domain list | Lesson gets published with a domain no other lesson uses, breaks BM25 corpus stats |
| 3 | `<domain>` placeholder literally | Same `-d` flag, but the suggested command has `<domain>` only in the "all matched" path (line 194), not the unmatched path (line 190) | When user has matched signatures too, the suggestion mixes placeholders with real values |

A user copy-pasting either of the two suggested commands (line 190 or line 194 of `search_knowledge.py`) will get an argparse error or a lesson in a non-canonical domain — both of which require a manual fixup before the lesson can be merged.

## Root Cause

`search_knowledge.py` (commit f4bce62 in June 2026) added `--heal` and the suggested commands, but the suggested text **was never synchronized** with `scripts/queue_lesson.py`'s argparse definition:

- `search_knowledge.py:190` and `:194` were written assuming a future `queue_lesson.py` API with short flags and stricter domain validation
- `scripts/queue_lesson.py:294-301` has `argparse` with `--title/-t`, `--domain/-d`, `--tags`, `--file` (long form only), and `content` positional — **no `-f` short flag, no domain choices list**
- The two files have no shared constant or schema; each evolves independently

This is a **UX gap, not a bug** — the scripts work, but the help text lies. Agents (or human contributors) following the help text waste 5-10 minutes debugging argparse errors that wouldn't exist if the help text were accurate.

## Solution

Until the maintainer (zeroknowledge0x) synchronizes the suggested commands with the actual argparse, **always verify the suggested command against the script's `--help` before running**. Three rules:

### Rule 1: Use `--file` (long form), not `-f`

```bash
# ✅ Correct — long form, matches queue_lesson.py:300
python3 scripts/queue_lesson.py \
  --file tests/fixtures/openclaw/unmatched_a1b2c3d4.log

# ❌ Wrong — -f is not a defined short flag in queue_lesson.py
python3 scripts/queue_lesson.py \
  -f tests/fixtures/openclaw/unmatched_a1b2c3d4.log
# argparse error: unrecognized arguments: -f tests/...
```

### Rule 2: Pick a domain from the canonical 11, not a freeform tag

Canonical domains (as of v2.7.0, 2026-06-23, listed in `lessons/index.md`):

- `agent-network`
- `audio`
- `claude`
- `devops`
- `fanuc`
- `feishu`
- `marketing`
- `mcp`
- `rag`
- `tts`
- `uncategorized`

`openclaw` is **not** a canonical domain — it's a **tag**. Use `development` (the domain for code/runtime lessons) or `devops` (for environment/tooling lessons) as the domain, then add `openclaw` to the `tags` array for BM25 recall.

```bash
# ✅ Correct — domain=development, tag=openclaw
python3 scripts/queue_lesson.py \
  -t "My OpenClaw-related error" \
  -d development \
  --tags "openclaw,wsl2,fixture"

# ❌ Wrong — openclaw is a tag, not a domain (lesson ends up in the "uncategorized" bucket by BM25 stats)
python3 scripts/queue_lesson.py \
  -t "My OpenClaw-related error" \
  -d openclaw
```

After import, the lesson's frontmatter will have `domain: development` and BM25 will treat `openclaw` as a token from the `tags` array.

### Rule 3: For the "all matched" suggestion, replace the `<domain>` placeholder

`search_knowledge.py:194` prints:

```
💡 Contribute back if you applied a new fix:
   python3 scripts/queue_lesson.py -t 'your title' -d <domain> 'content...'
```

**Replace `<domain>` literally** with one of the canonical 11 above, then write `content...` as actual lesson content (the suggested `content...` is a placeholder, not a literal string to paste):

```bash
# ✅ Correct — domain filled, content written
python3 scripts/queue_lesson.py \
  -t "RAG retrieval returns stale results after index update" \
  -d rag \
  "Symptom: search returns pre-update chunks. Root cause: BM25 cache invalidation. Fix: bump index version + clear cache."
```

## Verification

Tested end-to-end on 2026-06-23 with a real unmatched signature from a Playwright WSL2 crash:

```bash
$ python3 search_knowledge.py --heal /tmp/playwright-crash.log
[MisakaNet] 🔍 Extracted 1 error signature(s)
  ❌ unmatched: 'libnss3.so not found' (no lesson found)
  📊 Coverage: 0/1 signatures matched (0.0%)
  📝 1 unmatched signature(s) — auto-generated fixtures in tests/fixtures/openclaw/
     Submit a lesson to improve coverage:
     python3 scripts/queue_lesson.py -t 'your title' -d openclaw -f tests/fixtures/openclaw/unmatched_a1b2c3d4.log
```

Following the suggested command **literally**:

```bash
$ python3 scripts/queue_lesson.py \
    -t 'libnss3 fix' \
    -d openclaw \
    -f tests/fixtures/openclaw/unmatched_a1b2c3d4.log
usage: queue_lesson.py [-h] [-t TITLE] [-d DOMAIN] [--tags TAGS]
                       [--status {published,draft,deprecated}]
                       [--file FILE]
                       [content]
queue_lesson.py: error: unrecognized arguments: -f tests/fixtures/openclaw/unmatched_a1b2c3d4.log
# Exit code 2, no lesson written, fixture orphaned
```

**Fixed command**:

```bash
$ python3 scripts/queue_lesson.py \
    --file tests/fixtures/openclaw/unmatched_a1b2c3d4.log
# Lesson drafted, then manual edit + commit, then re-run --heal → 100% coverage
```

## Notes

- **This is a documentation drift, not a parser bug** — both files work as designed; the issue is that `--heal`'s help text was written against a different mental model of `queue_lesson.py`. Fixing it requires a 4-line patch to `search_knowledge.py:190` and `:194` (or, more robustly, dynamically generating the suggestion from `queue_lesson.py`'s parser via `argparse.ArgumentParser.format_help()`).
- **Suggested PR** (for maintainer consideration): a follow-up PR could either (a) patch the two print statements to use `--file` + a canonical domain, or (b) refactor to call `queue_lesson.py` programmatically via `subprocess.run([...])` so the suggested command is always in sync.
- **Domain list source of truth**: `lessons/index.md` "Domain" column. If a new domain is added, both `search_knowledge.py` and `queue_lesson.py` should be updated. A unit test parsing `lessons/index.md` and asserting `queue_lesson.py --help` mentions each domain would catch drift.
- **Related lessons**:
  - `misakanet-heal-engine-bootstrap-workflow` — the broader 5-step workflow this UX gap sits inside
  - `openclaw-fatal-error-hook-protocol` — how errors reach `--heal` in the first place
  - `openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium` — the lesson that *successfully* used the corrected command
