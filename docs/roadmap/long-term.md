# MisakaNet Long-Term Roadmap (Architecture)

> These are long-term architectural goals tracked for reference.
> They are NOT open bounty issues. Work on them requires maintainer coordination.

## Status: Planning / Future

### Federation & Trust
- **#320** Hub federation mode — cross-repo lesson sync
- **#321** Distributed trust system with verification tiers
- **#322** Reputation system with reuse signals
- **#324** Governance config — misaka-protocol.json

### Multi-Agent
- **#325** Real-time collaboration protocol for multi-agent editing
- **#326** Multi-agent conflict resolution for lesson merges
- **#329** Decentralized Autonomous Learning Network (DALN) spec

### Quality & Versioning
- **#327** Semantic versioning for lessons and protocol
- **#328** Anti-gaming safeguards for reputation system

### Infrastructure
- **#323** Asset isolation — frontend to sidecar repository

## When to activate

These become active when:
1. Core platform (search, MCP, intake) is stable
2. There are enough real contributors to benefit from federation/trust
3. A specific use case drives the need (e.g., cross-org lesson sharing)

## How to contribute

If you want to work on any of these:
1. Open a new issue with a specific, phased proposal
2. Start with Phase 1 (read-only / prototype)
3. Get maintainer approval before building

---

*Also tracked:*
- REST API for lesson search (#307) — closed 3 times, needs integrated design
- Query expansion with synonyms (#313) — needs integration with existing search engine
- Quality scoring CI pipeline (#305) — Phase 1 done via #501, Phase 2 pending
