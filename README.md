┌──────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐     ┌─────────┐
│  Node    │     │  Local       │     │  Git        │     │  CI      │     │  Main   │
│  catches │────▶│  validates   │────▶│  commits    │────▶│  DCO +   │────▶│  Branch │
│  a bug   │     │  & formats   │     │  & pushes   │     │  Lint +  │     │  Merged │
└──────────┘     └──────────────┘     └─────────────┘     │  pytest  │     └─────────┘
                                                            └─────────┘
       │                                                          │
       ▼                                                          ▼
┌──────────────────┐                         

Produce the fix now.