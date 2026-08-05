# Microservice Decoupling Plan

> Status: Proposal | 2026-06-19
> Goal: Split monorepo into 3 sidecar repositories

## Current State

Everything lives in one repo: `Ikalus1988/MisakaNet`

```
MisakaNet/
├── hub/           # Hub server (API, federation, sync)
├── web/           # Dashboard UI (Node.js/Next.js)
├── scripts/       # CLI tools (leaderboard, harvest, contribute)
├── misakanet/     # Python library (search engine, tools)
├── lessons/       # Knowledge base
└── docs/          # Documentation
```

## Target State

| Repo | Contents | Responsibility |
|------|----------|---------------|
| `Ikalus1988/MisakaNet` (shrunk) | `misakanet/`, `search_knowledge.py`, `lessons/`, `docs/`, `scripts/` | Core SKP engine + knowledge base |
| `Ikalus1988/MisakaNet-Hub` | `hub/`, `config.yaml` | Hub server, federation, arbitration |
| `Ikalus1988/MisakaNet-Web` | `web/` | Dashboard, node management |

## Migration Steps

### Phase 1: Code Audit (Week 1)

- [ ] Identify all cross-repo dependencies (`from hub import ...` in non-hub code)
- [ ] List shared utilities (logging, config, DB helpers)
- [ ] Decide on shared library approach (extract to `misakanet-core` or keep duplicated)

### Phase 2: Hub Extraction (Week 2-3)

- [ ] Create `Ikalus1988/MisakaNet-Hub` from `hub/` directory
- [ ] Set up CI/CD (copy relevant workflows)
- [ ] Create Python package with `pyproject.toml`
- [ ] Update `misaka_hub.py` entry point
- [ ] Add GitHub Actions for auto-deploy

### Phase 3: Web Extraction (Week 3-4)

- [ ] Create `Ikalus1988/MisakaNet-Web` from `web/` directory
- [ ] Set up Vercel/Cloudflare Pages deployment
- [ ] Update API endpoint references to point to Hub

### Phase 4: Cleanup (Week 4)

- [ ] Remove `hub/` and `web/` from main repo
- [ ] Update all documentation references
- [ ] Update AGENTS.md and CLAUDE.md
- [ ] Add cross-repo dependency notes

## Dependencies to Resolve

| Current Import | Target Repo | Resolution |
|---------------|-------------|------------|
| `hub.storage.vector_store` | MisakaNet-Hub | Extract to shared package (`misakanet-core`) |
| `hub.master.master_api` | MisakaNet-Hub | Extract client SDK to main repo |
| `hub/federation/` | MisakaNet-Hub | Full move |
| `web/` (Next.js) | MisakaNet-Web | Full move |

## Risks

| Risk | Mitigation |
|------|------------|
| Circular dependencies between Hub and Core | Extract shared types to `misakanet-core` first |
| CI/CD pipeline duplication | Use reusable workflows |
| Breaking changes for existing nodes | Semver bump + migration guide |
| Loss of cross-repo visibility | Monthly cross-repo sync meeting or README |

## References

- [ADR: Monorepo Decision](../docs/adr/)
- [CI Workflows](../.github/workflows/)
