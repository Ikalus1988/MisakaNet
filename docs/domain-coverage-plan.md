# Domain Coverage Expansion Plan

> Status: Roadmap | 2026-06-19 | Q3 2026 Target

## Current Coverage

| Domain | Current Lessons | Q3 Target | Gap |
|--------|:---------------:|:---------:|:---:|
| RAG | 24 | 35+ | +11 |
| DevOps/Infrastructure | 18 | 30+ | +12 |
| Multi-Agent Coordination | 8 | 20+ | +12 |
| LLM Fine-tuning | 3 | 15+ | +12 |
| Database & Query | 5 | 12+ | +7 |
| **Total** | **58** | **112+** | **+54** |

## Priority Topics by Domain

### RAG (+11)
- [ ] Chunking strategies for Chinese text (vs English)
- [ ] Hybrid search tuning (BM25 + vector weight calibration)
- [ ] Weaviate/LanceDB migration pitfalls
- [ ] Cross-encoder reranker memory management
- [ ] Query expansion failure modes
- [ ] Embedding cache invalidation
- [ ] SQLite vs PostgreSQL for metadata filtering
- [ ] Streaming RAG with async generators
- [ ] Guardrail design for RAG answers
- [ ] Evaluation dataset creation
- [ ] A/B testing retrieval strategies

### DevOps & Infrastructure (+12)
- [ ] Docker Compose network race conditions
- [ ] K8s liveness probe misconfiguration
- [ ] Terraform state locking issues
- [ ] GitHub Actions matrix strategy edge cases
- [ ] Self-hosted runner security hardening
- [ ] Nginx reverse proxy WebSocket timeout
- [ ] PostgreSQL connection pooling exhaustion
- [ ] Redis memory policy eviction
- [ ] Prometheus recording rules cardinality explosion
- [ ] Docker build cache invalidation debugging
- [ ] SSH key management automation
- [ ] CI/CD pipeline secret rotation

### Multi-Agent Coordination (+12)
- [ ] Agent state synchronization conflicts
- [ ] Context window overflow handling
- [ ] Agent-to-agent deadlock detection
- [ ] Shared tool invocation race conditions
- [ ] Message queue backpressure
- [ ] Agent heartbeat/timeout recovery
- [ ] Parallel tool execution ordering
- [ ] Agent memory consolidation strategies
- [ ] Inter-agent dependency resolution
- [ ] Leader election for task assignment
- [ ] Rate limiting across multiple agents
- [ ] Agent task queue prioritization

### LLM Fine-tuning (+12)
- [ ] LoRA rank selection guidelines
- [ ] Dataset format conversion pitfalls
- [ ] VRAM estimation for fine-tuning
- [ ] QLoRA vs LoRA tradeoffs
- [ ] Overfitting detection during training
- [ ] Evaluation set contamination
- [ ] Multi-GPU training data parallelism issues
- [ ] Gradient checkpointing OOM
- [ ] Mixed precision training instability
- [ ] Fine-tuning for code generation
- [ ] Instruction dataset curation best practices
- [ ] Model merging conflicts

### Database & Query (+7)
- [ ] SQL JOIN vs subquery performance traps
- [ ] Index design for time-series data
- [ ] Connection leak detection
- [ ] Deadlock diagnosis in PostgreSQL
- [ ] Query plan analysis for slow queries
- [ ] Pagination offset performance degradation
- [ ] JSONB vs relational schema tradeoffs

## Execution Strategy

| Phase | Focus | Method |
|-------|-------|--------|
| Phase 1 (Jul) | RAG + DevOps (23 lessons) | Batch create via harvester + contribute |
| Phase 2 (Aug) | Multi-Agent + Database (19 lessons) | Ring-4 bounty + community contributions |
| Phase 3 (Sep) | LLM Fine-tuning (12 lessons) | Expert contributions + LLM-assisted generation |

## Automation

Use Log Harvester CLI to accelerate creation:
```bash
# Harvest from error logs
python3 search_knowledge.py --harvest --from-file <error-log>

# Or contribute via wizard
python3 scripts/contribute.py --wizard
```

## Related

- [Ring-4 Newcomer Track](ring4-newcomer-track.md) — Translate/verify/tag tasks
- [Lesson Checklist](lesson-checklist.md) — Quality standards
