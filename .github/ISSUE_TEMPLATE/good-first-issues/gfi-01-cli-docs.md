---
name: "docs: Write complete CLI usage guide"
about: Good first issue — documentation task
labels: ["good first issue", "documentation", "Ring-4"]
assignees: ''
---

## Task

Write a comprehensive CLI usage guide for `search_knowledge.py` that covers all available flags and modes.

## Context

The CLI reference at `docs/cli-reference.md` exists but is incomplete. New users and AI agents need a clear, example-driven guide to use the tool effectively.

## Acceptance Criteria

1. Create or update `docs/cli-guide.md` with:
   - Quick start (first search in 30 seconds)
   - All flags documented with examples: `--lessons`, `--ref`, `--top=N`, `--titles`, `--broad`, `--suggest`, `--semantic`, `--score`, `--explain`, `--env`, `--domain`, `--lang`, `--heal`, `--harvest`
   - Common workflows: "I got an error, find a lesson", "Search by domain", "Find high-quality lessons only"
   - Troubleshooting section (no results found, import errors, etc.)

2. Update `docs/cli-reference.md` if any flags are missing

3. Add a "Quick Start" section to `README.md` that links to the new guide

## Skills Required

- Technical writing (English)
- Familiarity with CLI tools
- No code changes needed — pure documentation

## Estimated Time

2-4 hours

## How to Claim

Comment `/claim` on this issue. You have 8 hours to open a WIP PR.
