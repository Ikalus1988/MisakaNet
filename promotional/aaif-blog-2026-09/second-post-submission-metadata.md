# AAIF blog submission #2 — metadata

Article: [`second-post-error-signature-indexing.md`](./second-post-error-signature-indexing.md)

> Submit **after** post #1 (`failure-memory-layer-article.md`) is published, or as a
> follow-up in the same thread. Community contributors may submit up to two posts per month,
> so both can coexist.

---

## 1. Submission essentials

| Field | Value |
|---|---|
| **Suggested title** | Error Strings Are Not Queries: What 380 Lessons Taught Us About Indexing Failures |
| **Author name** | Ikalus1988 (maintainer, MisakaNet) |
| **Author bio** | Same as post #1 — see [`submission-metadata.md`](./submission-metadata.md) §1 (reuse verbatim so bylines stay consistent) |
| **Headshot / logo** | Reuse the one submitted with post #1 ([`docs/assets/misaka-avatar-crop.png`](../../docs/assets/misaka-avatar-crop.png) as fallback) |
| **Category / track** | Community Contributor — technical deep-dive / how-to |
| **Length** | ~1,050 words (guideline: 600–1,500) ✓ |
| **Originality** | Unpublished elsewhere; distinct from post #1 (that one is about the memory layer and trust boundaries; this one is about making the corpus *retrievable*) |
| **Preferred publish date** | ≥2 weeks after post #1 |

## 2. Social media copy

**Preferred hashtags:** `#AgenticAI #MCP #RAG #SearchQuality #OpenSource`

**Short post (~280 chars):**
> We searched our own failure library for "rag performance latency optimization" — with 14 RAG lessons indexed — and got nothing. Not a knowledge gap: an indexing gap. What 380 lessons taught us about making failure knowledge retrievable for agents. #AgenticAI #SearchQuality

**Longer post (LinkedIn / community):**
> The most expensive search result is the empty one: an agent that gets nothing does not reword its query — it concludes the knowledge does not exist and starts from zero.
>
> We measured why ours came back empty. A troubleshooting lesson is written in specific nouns (library names, error classes); a searcher arrives with a summary. Of the four content words in one real query, exactly one appeared in any matching lesson title.
>
> Three fixes, in order of cheapness: fix tokenizer assumptions (hyphenated identifiers), make matching stack-aware (cross-language false positives went from 19/50 to 0–1/9), and — still in progress — index normalized failure *signatures* instead of prose. Plus one discipline: treat a miss as data, record it, and retire it when a lesson finally covers it.
>
> We published our unflattering number too: prose-only matching finds a relevant lesson ~49% of the time. #AgenticAI #MCP #SearchQuality

## 3. Self-check against the guidelines

| Guideline | Status |
|---|---|
| Narrative format | ✅ first-person engineering narrative with measured numbers |
| 600–1,500 words | ✅ ~1,050 |
| Vendor-neutral | ✅ no competitor claims; the pattern (prose corpus vs. summary queries) is presented as general, with our implementation as the example |
| Original / not published elsewhere | ✅ new draft |
| Recent work (≤2 months) | ✅ Aug–Sep 2026 work (tokenizer fix, stack gate, gap lifecycle, pilot) |
| Includes title, author, bio, headshot slot, social copy + hashtags | ✅ |
| No criticism of other projects | ✅ |

## 4. Facts and their sources (for review, not for the post)

| Claim in the draft | Source in the repo |
|---|---|
| More than a dozen RAG lessons while the query returned nothing | `lessons/**/rag-*.md` (14 files) + the gap record for that query |
| One of four content words matched, once | word-overlap measurement recorded in issue #1562 |
| Cross-language false positives 19/50 → 0–1/9 | intake-bot v1.0 rewrite (PR #1539) |
| Prose-only matching finds a relevant lesson ~49% of the time | benchmark baseline 0.489, `docs/agents/failure-feedback-flywheel-research.md` |
| Two of nineteen gap queries were false blind spots | KV gap analysis, 2026-09-07 (19 gaps → 2 recall defects) |
| External pilot: 25 failures, 10/10 on-target | `docs/external-pilots/roof4u-2026-09-08.md` |
| Gap lifecycle retires covered gaps | PR #1586 (`cleanupCoveredGaps`) |
