## First-Call Funnel Tracking

### Goal
Measure and optimize the first-time user journey: discovery -> registration -> first search.

### Metrics
- `funnel.visit` — Unique visitors to misakanet.org
- `funnel.register` — MCP node registration completed
- `funnel.first_search` — First MCP search executed
- `funnel.drop_off` — Abandoned at registration
- `funnel.error_search` — Search with empty/error result

### Implementation
1. Track via hub/master/master_api.py registration endpoint
2. Log events to federated telemetry
3. Dashboard: docs/data/feed.json + Grafana

### Success Criteria
- <5min time-to-first-search
- <20% drop-off at registration
- >80% first-search success rate