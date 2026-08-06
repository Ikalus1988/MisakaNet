# pr-genius Federation Peer

pr-genius is a query-only federation peer of MisakaNet.

## Role

| Peer | Role |
|------|------|
| **pr-genius** | Evidence-backed external PR intelligence and PR rounds archive. |
| **MisakaNet** | Generalized agent failure/recovery lessons and swarm knowledge network. |

## Rules

- No automatic content sync.
- No automatic GitHub actions across repositories.
- No shared credentials or authority.
- Imported lessons must preserve upstream provenance, commit SHA, license, and evidence URLs.

## What pr-genius provides

- Repository-specific PR profiles (maintainer response patterns, merge rates, AI-friendliness)
- PR case studies with full review round evidence
- Cross-repo PR strategy patterns
- OKF-compliant knowledge bundles

## What MisakaNet provides

- Generalized debugging lessons (not repo-specific)
- BM25 + RRF search across all lessons
- SKP (Swarm Knowledge Protocol) for agent experience sharing
- Quality scoring and lesson lifecycle management

## How to query pr-genius from MisakaNet

```bash
# Search for PR strategy lessons
python3 search_knowledge.py "pr-genius federation"
python3 search_knowledge.py "external PR strategy"

# The pr-genius repo itself
# https://github.com/zsxh1990/pr-genius
```

## Machine-readable peer declaration

See `misaka-protocol.json` → `ecosystem.federation.peers.pr-genius`.
