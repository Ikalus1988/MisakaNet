---
title: External PR Strategy via pr-genius
domain: contrib
tags: [github-pr, external-pr, pr-genius, federation]
status: published
source: pr-genius
created: 2026-07-06
updated: 2026-07-06
---

# External PR Strategy via pr-genius

For repository-specific PR profiles, maintainer response patterns, and PR round evidence, query the pr-genius federation peer.

## Canonical peer

https://github.com/zsxh1990/pr-genius

## What pr-genius contains

- **Repo profiles**: AI-friendliness, merge rates, maintainer response times, failure patterns per repo
- **PR case studies**: Full review rounds with maintainer comments, CI feedback, and outcome evidence
- **Cross-repo patterns**: Common PR pitfalls across high-star projects (star >= 1k)
- **OKF-compliant bundles**: Portable, cross-linked markdown knowledge packs

## What MisakaNet keeps

MisakaNet keeps only **generalized** contribution lessons here — patterns that apply across all repos, not repo-specific intelligence.

## How to use

```bash
# Search for PR strategy patterns
python3 search_knowledge.py "pr-genius federation"
python3 search_knowledge.py "external PR strategy"

# Query pr-genius directly
# Clone: git clone https://github.com/zsxh1990/pr-genius
# Search: python3 search_knowledge.py "astral-sh/uv" (in pr-genius repo)
```

## Federation rules

- Query-only: pr-genius content is not auto-synced into MisakaNet
- Imported lessons must preserve upstream provenance, commit SHA, license, and evidence URLs
- See `docs/federation/pr-genius.md` for full peer declaration
