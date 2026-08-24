---
issue_number: 1166
title: "[Intake] Memory dump watcher: auto-extract lessons from agent logs"
score: 32.4
decision: reject
created_at: "2026-08-24T10:22:53.364398Z"
---

# [Intake] Memory dump watcher: auto-extract lessons from agent logs

## Problem

MisakaNet's intake pipeline requires explicit submission (curl/MCP/API). But the richest failure signals are buried in **agent conversation logs, Claude memory dumps, and debugging transcripts** — nobody goes back to manually extract lessons from these.

TeamMemory's Obsidian Watcher monitors a vault directory for file changes → auto-creates drafts → RefinementWorker extracts structured fields → auto-publishes. We need a similar mechanism for agent memory dumps.

## Proposed Design

### Watcher Modes

| Mode | Input | Trigger |
|---|---|---|
| **File watcher** | Directory of `.md`/`.json`/`.jsonl` files | File created/modified |
| **CLI pipe** | stdin stream | `cat agent.log \| misakanet extract` |
| **MCP callback** | Agent pushes conversation end | `misakanet_submit_usage` with `extract=true` |

### Extraction Pipeline

```
Raw memory dump
    ↓
[Content filter] — skip if too short, too noisy, or already indexed
    ↓
[Failure detector] — LLM classifies: is this a failure scenario? (yes/no/maybe)
    ↓
[Structure extractor] — LLM extracts: problem, root_cause, fix, domain, tags
    ↓
[Dedup check] — fuzzy match against existing lessons
    ↓
[Draft creator] — saves as draft with status=pending_review
    ↓
[Notify maintainer] — optional webhook/email/notification
```

### Configuration

```yaml
# .misakanet/watcher.yaml
watch:
  directories:
    - path: ~/.claude/projects/*/memory/
      pattern: "*.md"
      auto_extract: true
    - path: ./agent-logs/
      pattern: "*.jsonl"
      auto_extract: false  # manual trigger only

extraction:
  min_length: 200           # skip very short files
  failure_threshold: 0.7    # confidence for failure detection
  dedup_threshold: 0.85     # similarity threshold for dedup
  auto_publish: false       # always create draft first
  notify: true              # notify maintainer on new draft
```

### CLI Interface

```bash
# Watch mode
misakanet watch ~/.claude/projects/*/memory/ --extract

# One-shot extraction
misakanet extract --file agent-conversation.md --output draft.md

# Pipe mode
cat debug-session.log | misakanet extract --stdin

# Batch mode
misakanet extract --dir ./agent-logs/ --pattern "*.jsonl" --batch
```

### Integration Points

- New module: `misakanet/watcher.py` — file system monitoring
- New module: `misakanet/extractor.py` — LLM-based failure extraction
- New CLI command: `misakanet watch` and `misakanet extract`
- Intake pipeline: drafts flow into existing review queue
- Dedup: reuse existing lesson similarity checking

## Acceptance Criteria

- [ ] `misakanet watch <dir>` monitors directory for new/modified files
- [ ] Files pass through content filter (min length, noise detection)
- [ ] LLM classifies whether file contains a failure scenario
- [ ] Structured extraction: problem, root_cause, fix, domain, tags
- [ ] Dedup check against existing lessons (fuzzy match)
- [ ] Creates draft with `status=pending_review` (never auto-publishes)
- [ ] `misakanet extract --file` works for one-shot extraction
- [ ] `cat file | misakanet extract --stdin` works for pipe mode
- [ ] Configuration via `.misakanet/watcher.yaml`
- [ ] Unit tests cover: content filter, failure detection, extraction, dedup
- [ ] Documentation in `docs/watcher.md`

## References

- TeamMemory: Obsidian Watcher + RefinementWorker (GLM-5-Turbo, 30s scan, auto-publish)
- MisakaNet existing: intake pipeline, `POST /api/intake`, classifier, demand board
- Related: #1071 (MCP intake strategy), #1150 (faithfulness)

## Scope

- **In scope**: File watcher, CLI extraction, LLM-based failure detection, dedup, draft creation
- **Out of scope**: Real-time streaming extraction, auto-publishing, Obsidian plugin, VS Code extension integration
<br/>
<hr/>

<details><summary>This repo is using Opire - what does it mean? 👇</summary><br/>💵 Everyone can add rewards for this issue commenting <code>/reward 100</code> (replace <code>100</code> with the amount).<br/>🕵️‍♂️ If someone starts working on this issue to earn the rewards, they can comment <code>/try</code> to let everyone know!<br/>🙌 And when they open the PR, they can comment <code>/claim #1166</code> either in the PR description or in a PR's comment.<br/><br/>🪙 Also, everyone can tip any user commenting <code>/tip 20 @Ikalus1988</code> (replace <code>20</code> with the amount, and <code>@Ikalus1988</code> with the user to tip).<br/><br/>📖 If you want to learn more, check out our <a href="https://docs.opire.dev">documentation</a>.</details>

