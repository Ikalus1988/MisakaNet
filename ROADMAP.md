# Swarm Knowledge Protocol — Roadmap

> This document tracks the **strategic vision** and **concrete milestones** for the SKP ecosystem.
> Short-term items are actionable; medium/long-term items are directional and open for community discussion.

---

## Short-term (0–3 months) — Now

| Area | Item | Priority | Depends On |
|------|------|----------|------------|
| **Quality scoring** | Add `quality_score` to lesson schema + auto-calculate in CI | P0 | [#210](https://github.com/Ikalus1988/MisakaNet/issues/210) |
| **Governance** | Define trust tiers in machine-readable config (misaka-protocol.json) | P0 | [#211](https://github.com/Ikalus1988/MisakaNet/issues/211) |
| **Contributor wall** | Fix time-decay formula — cap per-PR weight, remove contributor disappearance | P0 | [#212](https://github.com/Ikalus1988/MisakaNet/issues/212) |
| **Trust system** | Formalize GitHub-verified vs mail-verified vs web-verified tiers | P1 | [#213](https://github.com/Ikalus1988/MisakaNet/issues/213) |
| **Log Harvester CLI** | `misaka harvest` — stdin/bash-history → auto-generate SKP lesson | P1 | [#214](https://github.com/Ikalus1988/MisakaNet/issues/214) |
| **Ecosystem config** | Harvest tool interface declared in misaka-protocol.json | P1 | [#215](https://github.com/Ikalus1988/MisakaNet/issues/215) |
| **Asset isolation** | Move docs/frontend assets to sidecar repository or `/web` | P1 | [#216](https://github.com/Ikalus1988/MisakaNet/issues/216) |

## Medium-term (3–9 months) — Next

| Area | Item | Priority | Depends On |
|------|------|----------|------------|
| **Reputation system** | Reuse signal: count "👍 useful" clicks + cross-lesson references | P0 | [#217](https://github.com/Ikalus1988/MisakaNet/issues/217) |
| **Reaction collection** | Frontend "👍 helpful" button → `data/reactions.json` (anonymous, git-backed) | P1 | [#218](https://github.com/Ikalus1988/MisakaNet/issues/218) |
| **Cross-reference auto-detect** | CI scans lessons for `[[lesson-id]]` links, builds reference graph | P2 | Schema stable |
| **Rank change notifications** | GitHub Issue auto-published when leaderboard #1 changes | P1 | [#219](https://github.com/Ikalus1988/MisakaNet/issues/219) |
| **Personal rank alerts** | Notify individual contributors when they move up/down | P1 | [#220](https://github.com/Ikalus1988/MisakaNet/issues/220) |
| **PR scoring** | Score PRs by complexity (files + lines + test coverage) | P2 | Quality gate stable |
| **Seat belt mechanism** | Auto-cap contribution weight for very high-frequency contributors (sigmoid cap) | P2 | Leaderboard data >50 contributors |

## Long-term (9+ months) — Vision

| Area | Item | Priority | Depends On |
|------|------|----------|------------|
| **Retrieval weighting** | Search-hit rate → contribution bonus | P2 | Frontend analytics |
| **Hub federation** | Cross-repo lesson sync via Hub nodes | P2 | Hub mode stable |
| **Plugin system** | External tools read/write lessons via SKP protocol | P3 | API surface stable |
| **Leaderboard prize pool** | Top monthly contributor gets a badge / early-access feature | P3 | Community >100 nodes |
| **CLI dashboard** | `misaka dashboard` — local terminal leaderboard + notifications | P3 | Harvester CLI stable |
| **SKP SDK** | TypeScript SDK for browser-agent interactions | P3 | Hub API stable |
| **DALN whitepaper** | Formal paper on Decentralized Autonomous Learning Networks | P4 | All above stable |

---

## Design Principles

1. **Offline-first.** Everything must work in air-gapped environments. Features that require always-on servers get de-prioritized.
2. **Zero-dep core.** The `misakanet-core` PyPI package stays dependency-free. All extras are optional.
3. **Git as the source of truth.** No database. No daemon. No centralized API dependency.
4. **Agent-native.** Configuration must be machine-readable first, human-readable second. Every human doc has a JSON equivalent.
5. **Anti-hype.** We ship what we can verify. Every claimed capability must be demonstrable. Every limitation must be disclosed.

---

## How to Contribute

- Open a [GitHub Issue](https://github.com/Ikalus1988/MisakaNet/issues/new) with the `roadmap` label
- Propose changes via PR with rationale
- Vote on priorities by reacting to pinned roadmap Issues

> [README →](README.md) · [Limitations →](docs/LIMITATIONS.md) · [Protocol Config →](misaka-protocol.json)
