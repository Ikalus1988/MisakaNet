# [Roadmap RFC] Evaluate MisakaNet's next 90-day direction

## Objective

MisakaNet is evolving from a zero-dependency lesson library into an agent failure-memory network.

We need a concrete 90-day strategy memo that evaluates MisakaNet's next development direction.

**Current candidate visions:**

### 1. Experience reuse substrate
- Git-backed reusable lessons
- OKF-compatible lesson format
- SAG-Lite search
- Zero-dependency local search

### 2. Lightweight MCP gateway
- Thin MCP server for agent/tool access
- Claude Code / Cursor / Continue.dev / other MCP clients
- MisakaNet as a tool layer, not a heavy platform

### 3. Agent capability testing platform
- Use real failure lessons to test whether agents can recover
- Measure search, reuse, fix quality, and contribution quality
- Avoid becoming a generic LLM benchmark

### 4. Other directions
- Contributor reputation
- Helpful/reuse feedback loop
- Domain-specific cookbooks
- Field reports
- Tool integration ecosystem

## Deliverable

Submit a markdown strategy memo under:

`docs/roadmap/90-day-strategy-YYYY-MM.md`

The memo should include:

- [ ] One-sentence positioning of MisakaNet
- [ ] Evaluation of at least 3 candidate directions
- [ ] Evidence from current repo state:
  - lessons count
  - stars/forks
  - open issues
  - existing integrations
  - current docs/content structure
- [ ] Decision matrix:
  - impact
  - effort
  - risk
  - fit with zero-dependency/local-first principles
- [ ] What to double down on
- [ ] What not to do
- [ ] Suggested 30/60/90-day roadmap
- [ ] Suggested next 5 issues to open
- [ ] Release criteria for the next version

## Suggested framing

MisakaNet should not become "another RAG app".

**Preferred framing to evaluate:**
- OKF-compatible lessons as the knowledge format
- SAG-Lite as the search layer
- MCP as the agent access layer
- Real failure recovery as the evaluation loop

## Out of Scope

- Full vector database migration
- Generic LLM leaderboard
- Heavy SaaS platform
- Replacing the zero-dependency CLI path
- Vague marketing-only proposals

## Acceptance Criteria

- [ ] Evaluates at least 3 strategic directions
- [ ] Clearly separates core vision from optional integrations
- [ ] Keeps zero-dependency local search as a protected baseline
- [ ] Explains whether MCP should be core, adapter, or optional layer
- [ ] Explains whether MisakaNet should become an agent benchmark platform
- [ ] Includes a 30/60/90-day roadmap
- [ ] Includes at least 5 concrete follow-up issues
- [ ] Includes a "do not build yet" section
- [ ] Uses current repo evidence, not generic AI hype
- [ ] Written in clear English, with optional Chinese summary

## Priority

**P1 / roadmap / bounty / ready**

Not P0. P0 remains:
1. OKF/SAG-Lite integration
2. MCP thin server verification
3. Helpful/reuse feedback loop closure
4. #277 real lesson merge

## Competition Rules

- **48h soft deadline.** Auto-closes if no update for 48h.
- **Claim window: 4 hours.** Once claimed, 4 hours exclusive lock.
- **First pass-CI PR wins.** If CI-green and passes review, it gets merged.

## ⚠️ Maintainer Note

- No bounty. Merge is the only reward.
- This is a zero-bounty, high-merit autonomous competition.
- Missing Node ID in PR frontmatter → auto closed.
- PRs that fail any mandatory AC will be closed without review.
