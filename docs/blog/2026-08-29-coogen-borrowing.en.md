# Coogen Research and What MisakaNet Should Borrow

> Research date: 2026-08-29
> Subject: <https://www.coogen.ai> (including `/llms.txt`, `/skill.md`, `/install`, `/solve`, `/start`, `/dashboard`, `/rankings`, `/challenges`, `/agents`)
> Scope: Coogen's public frontend and machine-readable entry points; secondary channels (HN / GitHub / Twitter / review sites) returned **zero hits** — Coogen is in cold start · pre-public-launch, **closed-source + private traffic**, with no public discussion to reference.
> Artifacts (cleaned up): local `/tmp/cg_*` files containing Coogen's full i18n messages, the complete 380-line `skill.md` v10.13.0, and the full `llms.txt`.

---

## 1. What Coogen does (in one sentence)

**Coogen is a "working-method knowledge network" for AI agents**, with the slogan *"Verify. Adopt. Optimize."* — a three-party relationship:

```
Supply side sharer (owner + Agent)   →   platform L3 private collection + sandbox verification
                                             ↓  only public promote enters solve candidates
                                              capability profile E3 evidence
                                                  ↓
Consumption side any agent (any runtime)  ←  POST /solve + GET /cases/:id + receipt
```

The core narrative is **"the agent is not just a tool — it is a verified, adopted, measurable companion"** — which is exactly complementary to MisakaNet's view of the agent as a *consumer* of knowledge.

## 2. Coogen's key mechanisms (by importance)

| # | Mechanism | Implementation details |
|---|---|---|
| 1 | **L3 zero-upload promise** | Local hooks collect only *execution metadata* (tool names / call ordering / success or failure / duration / content hash fingerprints); raw content never leaves the machine; an outbound pass re-scans for raw-content leakage; method content is never public unless the owner explicitly Promotes it. |
| 2 | **Evidence levels E0 / E3 / E4** | E0 self-reported → E3 verified by the platform sandbox (with a signed execution receipt) → E4 reused by another agent (reuse receipt). Coogen has no E1/E2 — they are merged tiers. |
| 3 | **Cost-per-success prior** | `accuracy × sample size` + USD per success; hard constraints (permissions / budget / side effects) are *excluded outright* rather than down-weighted; no match returns a structured `unsolved`. |
| 4 | **Solve / Inspect three-step consumer surface** | `POST /agents/register` for an idempotency key → `POST /solve` with evidence level and ranking explanation → `GET /cases/:id` dereference → receipt after use. **Runtime-neutral**, not tied to OpenClaw. |
| 5 | **MCP Streamable HTTP channel** | `https://gmmeavrhzh…/mcp`, with `coogen_solve` / `coogen_inspect` / `coogen_search` / `coogen_events` / `coogen_demand_map` — 10 tools total; any MCP client (Claude Code / Hermes / generic JSON) can connect. |
| 6 | **Machine-readable entry points** | `/llms.txt` follows the llms.txt standard with three-intent navigation; `/skill.md` is the v10.13.0 agent-readable protocol manual (boot sequence / first-call flow / endpoints / safety / growth reporting / milestone / claim nudge). |
| 7 | **Three-intent facade** | `/install?intent=verify` · `/solve?intent=solve` · `/evaluate?intent=evaluate`; `/agents/register` and `/solve` accept the same `intent` field (id-only instrumentation, opt-in, invalid values silently dropped). |
| 8 | **Exactly one human-facing door** | `/start`: "You only do two things — authorize and see results." Copy a command → a pairing code is generated on the same page → jump to `/dashboard` to see the four evidence tiles. |
| 9 | **Pairing code + Claim bound to owner email** | Agents auto-register and get a `coogen_`-prefixed API key; after claiming, reputation is bound to the human's email and survives reinstalls / agent swaps. |
| 10 | **Closed feedback loop** | Event stream `GET /agents/me/events`: `verification_completed` (A4) · `method_adopted` (A6) · `promote_confirmed` (A5); cursor pagination; id-only. |
| 11 | **Demand map** | Unsolved problems are fed in by task_family × day × machine-enumerated reason; tells the supply side "what to contribute". id-only discipline. |
| 12 | **No more composite scores** | v10.12.0 T6-4: `credibility_composite` removed; the dashboard shows raw verifiable counts independently in four tiles. |
| 13 | **Emotional error copy** | "Your companion took its first step · helped its first partner" — metrics are translated into a "companion" narrative; never asks "was this helpful?". |

## 3. Borrowing traces already landed in this repo

Literal Coogen hits in the working tree number only **3** (plus 1 in a code comment):

| Borrowed point | File / evidence | Corresponding Coogen mechanism |
|---|---|---|
| **One-time pairing-code onboarding** | `workers/register-proxy-sw.js:2191` comment "(Coogen-inspired)"; `docs/release/v2.16.0-release-notes.md:13`; `/connect` page | Coogen `/start`'s "pairing code generated and shown on this page" |
| **One-line human positioning** | `JOIN.md:136`: "learn Coogen's 'agents connect first, users claim later, contribution behavior loops closed'; keep MisakaNet's 'Git-auditable, dry-run, redacted, PR-merged'" | Coogen `agents/register` + `claim_url` |
| **Homepage complexity comparison** | `docs/field-reports/release-readiness-2026-07-12.md:43`: "Homepage heavier than Coogen (nav drawer mitigates)" | Minimal homepage comparison |

Plus what is **already landed at the feature layer** (present in the repo but without literal "Coogen" mentions):

| Landed feature | File / evidence | Corresponding Coogen mechanism |
|---|---|---|
| **Evidence levels E0–E4** | `docs/trust-semantics.md` (full 5-level definition), `docs/search/index.html` EVIDENCE_LABELS, `schemas/lesson.json` enum, `misakanet/evidence.py:normalize_evidence_level()`, "Default is E0" | Coogen E0/E3/E4; E1/E2 are MisakaNet's own additions |
| **Remote MCP + Streamable HTTP** | `https://misakanet.org/mcp`, `MCP-Protocol-Version: 2025-06-18`; `CLAUDE.md` / `README.md` / `CONTRIBUTING.md` all curl-based | Coogen MCP gateway `coogen-mcp/mcp` |
| **`llms.txt` entry point** | `docs/llms.txt` (full 83 lines) | Coogen `/llms.txt` |
| **`skill.md` protocol manual** | `docs/skill.md` / `SKILL.md` boot sequence | Coogen `/skill.md` v10.13.0 |
| **No-account MCP intake** | `misakanet_submit_intake` needs no Bearer; `badcase/*/intake.md` entries are all "Submitted via remote MCP (xxx)" | Coogen "Public registration open · invitation-light" |
| **Composite score removed** | `docs/reviews/2026-08-24-repo-and-30-lessons.md` mentions complete E0/E1/E2/E3/E4 governance | Coogen v10.12.0 T6-4 |
| **L3 zero-upload redaction pipeline** | `clean_pipeline` (release notes) | Coogen "L3 zero-upload promise" |
| **Three-intent facade seed** | homepage first screen "search · intake · benchmark" three cards + README three entry points | Coogen `/install` · `/solve` · `/evaluate` |
| **Short-lived pairing tokens** | `POST /mcp/pair` 24h token | Coogen "pairing code valid for X minutes, expired codes can be regenerated" |

## 4. Directions still worth borrowing (by priority and feasibility)

### 🟢 High priority (this week)

1. **`/start` single-door mode + "humans do only two things" narrative**
   Today MisakaNet makes humans choose among CLI / MCP / Docker / Remote / WebMCP — five paths.
   → Learn from Coogen `/start`: a single landing page, "paste one snippet to your agent → pairing code generated on this page → jump to the dashboard".
   Landing: reuse the existing `/connect`, upgrade it to `/start`, CTA copy becomes *"you only do two things — authorize, see results"*.

2. **Three-intent facade + `?intent=` instrumentation**
   Coogen's `?intent=verify|solve|evaluate` is id-only instrumentation, opt-in, never errors.
   Landing:
   - `/install?intent=intake` / `?intent=search` / `?intent=eval`
   - `misakanet_submit_intake` and `misakanet_search` accept an optional `intent` field; invalid values silently dropped
   - Used only for aggregate reporting of "what users came to do", touching no business logic

3. **Grow MCP tools from 6 to 7: `misakanet_me_events`**
   Coogen's `coogen_events` makes "verified / reused" a first-class, agent-scoped citizen.
   MisakaNet currently has `misakanet_search` / `misakanet_get_lesson` / `misakanet_submit_intake` / `misakanet_write_lesson` / `misakanet_preflight` / `misakanet_register`.
   → Add `misakanet_me_events`: cursor pagination, id-only, event types `lesson_found_helpful` / `lesson_cited_in_pr` / `lesson_merged_as_E3` / `lesson_reused_outside`.
   Data source reuses existing GitHub PR comments / `helpful` reactions / `regression_queries.json` — no new storage needed.

4. **Add two sections to `skill.md`: Periodic Growth Check + Auto-Share Triggers**
   These two Coogen sections are highly actionable and reusable.
   MisakaNet's `SKILL.md` / `docs/skill.md` are comparatively lean; adding these two sections aligns with Coogen's "behavior-trigger rules" layer. The "companion-style growth narrative" is deferred — we don't want to turn a lesson library into a community.

### 🟡 Medium priority (two to four weeks)

5. **"Hard constraints excluded outright, not down-weighted" semantics**
   A Coogen solve that violates a hard constraint returns zero results, not a lower rank.
   MisakaNet's current state: search is BM25 keyword scoring, with no structured constraint channel.
   → Add an optional `exclude: { domains: [...], tags_contains_secret: true }` to `misakanet_search`; a hit returns zero results immediately plus a structured `excluded: [...]` report.

6. **Public demand-map page**
   Coogen ships it as a standalone tool (`GET /api/v1/insights/demand-board` needs no key; full `/api/v1/insights/demand-map` needs a key).
   MisakaNet has a similar seed in `data/unsolved_signals.json` (workers README mentions `recordUnsolvedSignal()`).
   → Promote `unsolved_signals.json` to a public `/challenges` page (task_family × 7d/30d × last_seen), alongside the lessons directory.

7. **Dashboard: drop composite, show four tiles independently**
   Coogen v10.12.0 T6-4 removed `credibility_composite`. MisakaNet currently has a two-layer `quality_scorer` + `trust_score`; should public pages show only `trust_score`, and only E3+/E4 counts rather than means dragged down by E0s?
   → Review `docs/search/index.html` and the dashboard: composite scores give contributors no incentive, remove them.

8. **A simplified `/agents/me/events`-style feedback loop**
   = an extension of item 3: add a lightweight "being used" notification on the GitHub side (helpful reaction, PR reference, issue reference), via Webhook rather than a new endpoint.

### 🟠 Long priority (a month or more)

9. **Write the L3 zero-upload promise into the trust layer**
   Coogen makes "raw content is hashed or discarded within your machine boundary; every outbound packet is scanned for raw-content leakage before sending" a standalone page `/install?intent=verify`.
   MisakaNet already has `clean_pipeline`, but no user-facing "collection boundary" page.
   → Add `docs/collection-boundary.md`: list "what we collect / what we don't / zero-upload promise / how to opt out", placed next to the intake flow.

10. **De-duplicate human entry pages**
    Coogen has one door at `/start`; MisakaNet has six: `/`, `/install`, `/connect`, `/search`, `/quickstart`, `/mcp-quickstart`.
    → Pick `/start` or `/connect` as the single door; redirect everything else while keeping it.

## 5. Explicitly **not** to be borrowed

| Coogen practice | Why MisakaNet should not copy it |
|---|---|
| `coogen_` API keys with OpenClaw-specific baggage | MisakaNet uses GitHub issues + MCP bearer; don't invent a new key-prefix system |
| `agent_name` as random `adjective_noun_NNN` | MisakaNet already has Node numbering + profile.json; no need to switch |
| Owner-email-bound claim model | MisakaNet has no "personal reputation across reinstalls" need; keep GitHub identity |
| Evaluate waitlist (`POST /evaluate/waitlist`) | MisakaNet uses public issues / forums, not an email waitlist |
| OKF / lessons as shareable knowledge units | MisakaNet already has the lessons/ directory + OKF; no need to reinvent |
| Identity narrative v3.0 ("Agent / Owner / Steward") | **Downgraded to P3**: Coogen's closed-source track is unproven; MisakaNet keeps its existing "Node / Agent / Maintainer" naming |
| `cost_per_success` prior field | **Downgraded to P3**: needs ground-truth data, and lessons are "knowledge" not "tools" — cost talk invites misuse |
| The "agent knowledge network" track as a whole | **No track change**: open-source clones of Coogen's idea (e.g. `rmolines/agent-knowledge-network`) all have 0 stars and never took off; MisakaNet stays differentiated as "failure-memory for agents" |

## 6. Research method and limitations

### Channel status (important: record this research's boundaries)

| Channel | This run's status | Notes |
|---|---|---|
| `agent-reach` CLI | binary found but `doctor` reports **"No channels installed"** | config complete, 0 plugins, not installed |
| `r.jina.ai` | HTTP 000 even after sandbox upgrade | outbound network layer blocks it, **not a sandbox limitation** |
| `mcporter` | callable, but `mcporter list` only sees Cloudflare's 5 servers | no Exa / GitHub / generic search |
| `web_search` tool | ✅ works | main secondary-source material |
| `curl` direct to GitHub API / HN Algolia / Coogen frontend | ✅ works | primary source for Coogen's actual mechanisms |
| Twitter / X | all 5 candidate handles HTTP 000 | Coogen has no discoverable public social accounts |

### Secondary-source cross-check

| Channel | Hits |
|---|---|
| HN Algolia `coogen.ai` | 0 |
| HN Algolia `coogen "agent knowledge"` | 0 |
| GitHub issue search `coogen.ai` / `verify.adopt.optimize` | 0 |
| GitHub repo search `coogen ai agent` | 1 unrelated project (`lehoa1806/coogent-antigravity`, different spelling) |
| GitHub `coogen-ai` org | 4 forks (`llama` / `llama_index` / `Open-Assistant` / `ChatDB_Magic`), all 0 stars — a placeholder zombie org, not the Coogen team |
| `betterclaw.io · OpenClaw Memory Plugins Compared (2026)` | **does not list Coogen** — confirms Coogen hasn't entered the mainstream OpenClaw plugin comparison pool |

**Key conclusion**: Coogen is **closed-source + private traffic**; treat it as an "independent reference object", not an "industry benchmark".

## 7. Recommended PR order (next release window)

1. `/start` single-door mode — within 5 files, half a day
2. Three-intent facade + `?intent=` instrumentation — 1 day
3. Add `misakanet_me_events` to MCP — 2 days
4. Add Periodic Growth Check + Auto-Share Triggers to `docs/skill.md` — half a day
5. Remove composite from the search page; show only `trust_score` and E3/E4 counts — half a day

→ Items 6+ (public demand-map page, L3 collection boundary, human entry-page de-dup) go to the release after next.
→ "Owner-companion narrative" / `cost_per_success` / changing the overall track — **not doing**.

---

## References

### Coogen primary sources
- Coogen homepage · <https://www.coogen.ai>
- Coogen machine-readable entry · <https://www.coogen.ai/llms.txt>
- Coogen Agent protocol manual · <https://www.coogen.ai/skill.md> (v10.13.0, 380 lines)

### MisakaNet borrowed implementations (in-repo)
- `JOIN.md:136` — "learn Coogen's 'agents connect first, users claim later, contribution behavior loops closed'…"
- `docs/release/v2.16.0-release-notes.md:13` — "One-Time Pairing Code (Coogen-inspired)"
- `docs/field-reports/release-readiness-2026-07-12.md:43` — "Homepage heavier than Coogen"
- `workers/register-proxy-sw.js:2191` — pairing code Coogen-inspired implementation
- `docs/trust-semantics.md` — complete E0–E4 evidence levels
- `docs/llms.txt` — LLM-readable entry
- `docs/mcp-quickstart.md` — Remote MCP Streamable HTTP onboarding

### Same-track open-source clones (the track itself is not to be copied)
- [rmolines/agent-knowledge-network](https://github.com/rmolines/agent-knowledge-network) — 0 stars
- [JamesFireStarter13/agent-knowledge-network](https://github.com/JamesFireStarter13/agent-knowledge-network) — 0 stars

### Mainstream OpenClaw plugin comparison (Coogen not listed)
- [OpenClaw Memory Plugins Compared: QMD, Mem0, Cognee, Honcho & More (2026)](https://www.betterclaw.io/blog/openclaw-memory-plugins-compared)
