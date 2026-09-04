---
title: 'Async question answers are pulled, not pushed (stateless MCP)'
domain: mcp
tags:
- mcp
- question
- intake
- faq
- d1
- async
- answer-delivery
- agent
status: published
created: '2026-09-03'
language: en
source: issue-1457
evidence_level: E2
---

## Problem

An agent asks a question through MCP (`misakanet_submit_intake` with `kind="question"`), a maintainer answers hours or days later on the linked GitHub issue — and the asker never receives the answer. MCP tool calls are synchronous one-shot requests; the client disconnects after the response, there is no server-initiated callback, and anonymous askers have no durable identity. Before the fix the answer simply sat in an issue comment: the asker (and every future agent with the same question) kept paying the cost of an unanswered knowledge gap.

## Root Cause

Three design facts compound into the lost answer:

1. **Stateless, synchronous MCP transport** — no push channel exists; a tool response is the only moment of contact.
2. **Anonymous, identity-less askers** — no mailbox, no session, no way to "notify later" even if a push channel existed.
3. **Short-lived dedup state** — the only record of a submitted question was a KV key with a 7-day TTL, and a duplicate submission returned a bare "already submitted" pointer, never the outcome.

Competitor research (claimidx "ask before retry", unstuck-mcp retry gating, knoten "has anyone tried X?", Casebook read-only corpus, Sentinela "no self-graded verdicts", loop-in-mcp/hitl-mcp state-persistent HITL) confirmed nobody pushes: every failure-memory system makes knowledge **re-queryable** and expects the agent to query at its next decision point.

## Fix

Make the answer a re-queryable artifact and give the asker an explicit way to pull it, keyed to the time horizon:

1. **Durable state** — a D1 `questions` table (issue_number UNIQUE, dedup_hash, status `pending`/`answered`, answer, issue_url). The worker records a `pending` row on submit; the dedup path consults D1 (not just the 7-day KV), so re-submissions find the row for as long as it exists.
2. **Short wait — same-question re-submission returns the answer**: the dedup-hit response fetches the row; if `answered`, it returns `{answered: true, answer: <maintainer answer>}`; if still `pending`, it returns a pointer to the open issue.
3. **Long tail — answered questions become FAQ hits**: `misakanet_search` appends answered rows as results (`type="faq"` with the full answer), suppressing `no_match` — any future agent searching the topic "receives" the answer without ever having asked.
4. **Follow-up contract** — the submit response carries `follow_up` (intake_id + issue_url + how to pull later), and tool descriptions teach the re-ask pattern.
5. **Authority gate** — only issues a maintainer closed with the `answered` label enter the store/FAQ corpus (answers are extracted from marker comments `<!-- misakanet-answer -->` / `## ✅ Answered`); an agent can never write its own answer into the corpus (Sentinela's no-self-graded-verdicts rule).
6. **Sync** — `scripts/sync_answered_questions.py` mirrors the worker's FNV-1a dedup hash and upserts pending/answered rows (daily workflow + manual dispatch).

## Verification

Live on the production MCP (`misakanet.org/mcp`, 2026-09-03):

1. Submitted a question (`kind="question"`) → issue opened as `[Question]`, response carried `follow_up`.
2. Answered in-issue (marker comment) → added `answered` label → closed → ran the sync → D1 row flipped to `answered`.
3. Re-submitted the exact same problem text → response: `{duplicate: true, answered: true, answer: <full maintainer answer>}`.
4. `misakanet_search` on the topic returned the `faq-issue-*` entry with the answer alongside lesson hits.

Worker test suite: 107 tests pass, including pending-record, answered-pull, pending-pointer and FAQ-search-hit cases. D1 schema applied via `wrangler d1 execute --remote --file=workers/d1/schema.sql`; worker + schema deployments verified on the live endpoint.
