┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌─────────────────────────┐     ┌─────────┐
│  Node    │     │  Local       │     │  Git        │     │  CI Auditing Pipeline   │     │  Main   │
│  catches │────▶│  validates   │────▶│  commits    │────▶│  DCO → Quality Score    │────▶│  Branch │
│  a bug   │     │  & formats   │     │  & pushes   │     │  Deps → Tests → Audit   │     │  Merged │
└──────────┘     └──────────────┘     └─────────────┘     │  Auto-Merge (if all ✅)  │     └─────────┘
                                                             └─────────────────────────┘
       │                                                             │
       ▼                                                             ▼
┌──────────────────┐                                       ┌──────────────────┐
│  Another Node    │                                       │  Lessons indexed │
│  searches via    │◀──────────────────────────────────────│  & published to  │
│  BM25 + RRF      │                                       │  GitHub Pages    │
└──────────────────┘                                       └──────────────────┘