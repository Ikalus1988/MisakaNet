# AAIF blog submission package — 2026-09

Everything needed to file the submission through the AAIF content form.
Article: [`failure-memory-layer-article.md`](./failure-memory-layer-article.md)

---

## 1. Submission essentials (paste into the form)

| Field | Value |
|---|---|
| **Suggested title** | Building a Failure Memory Layer for Coding Agents using MCP and AGENTS.md |
| **Author name** | Ikalus1988 (maintainer, MisakaNet) |
| **Author bio** | Ikalus1988 is the maintainer of MisakaNet, an open-source failure-memory network for AI coding agents. The project collects real CI failure patterns from external repositories, turns them into reviewed lessons, and exposes them to agents over MCP. He writes about agent reliability, failure data, and the plumbing that keeps shared knowledge trustworthy. |
| **Headshot / logo** | ⚠️ **Needs upload at submission** — the form requires a high-resolution headshot or project logo. A ready project mark lives in this repo: [`docs/assets/misaka-avatar-crop.png`](../../docs/assets/misaka-avatar-crop.png) (plus `misaka-avatar-fallback.svg`). A real headshot is preferred if available |
| **Category / track** | Community Contributor — case study + technical how-to (MCP + AGENTS.md) |
| **Preferred publish date** | Any; ~2 weeks lead time means mid/late September 2026 |
| **Length** | ~1,250 words (guideline: 600–1,500) |
| **Originality** | Unpublished elsewhere; written for this submission |

## 2. Social media copy (required by the guidelines)

**Preferred hashtags:** `#AgenticAI #MCP #AGENTSdotmd #AIAgents #OpenSource`

**Short post (~280 chars):**
> Coding agents re-solve the same bug every session. We built a failure memory they query over MCP before guessing — and learned the hard part isn't search, it's keeping the corpus trustworthy. New post: how MCP + AGENTS.md make failure memory work. #AgenticAI #MCP #AGENTSdotmd

**Longer post (LinkedIn / community):**
> Agents don't lack intelligence — they lack memory. Every session re-discovers the same proxy timeout, the same permissions error. We've been running a public failure-memory layer that agents query over MCP before they start guessing, with AGENTS.md as the instruction layer.
>
> Two lessons worth sharing: (1) a knowledge base that agents read is an *input surface* — one of our published lessons had an agent transcript pasted into its Problem section, turn markers and all; (2) "run this command" is a suggestion to a human and an executable step to an agent, so retrieved content has to be labeled as data, not instructions.
>
> The post covers the plumbing: low-friction anonymous intake, write-time screening, gap lifecycle, and the trust boundary we now declare in AGENTS.md. #AgenticAI #MCP #AGENTSdotmd #AIAgents #OpenSource

## 3. Self-check against the published guidelines

| Guideline | Status |
|---|---|
| Narrative format (not press release) | ✅ written as a first-person engineering narrative |
| 600–1,500 words | ✅ ~1,250 |
| Vendor-neutral | ✅ no competitor comparisons; the pattern is presented as reusable by any team; AAIF projects (MCP, AGENTS.md) are the frame |
| Original, not published elsewhere | ✅ new draft |
| Recent work (within ~2 months) | ✅ built on Aug–Sep 2026 work (pilot reports, injection scanner, gap lifecycle) |
| No paid/sponsored/promotional tone | ✅ one closing link block to the repository, as permitted |
| Includes title, author name, bio, headshot slot | ⚠️ headshot/logo must be attached at submission time |
| Social copy + hashtags included | ✅ §2 |
| No criticism of other projects | ✅ |

## 4. What the form needs from you (human-in-the-loop)

1. **Headshot or project logo** (high-resolution) — the one item I cannot produce.
2. **Submitter email / Asana form access** — the form
   ([form.asana.com/?k=Bq-lRvAXGzHQIXH_etPOxA](https://form.asana.com/?k=Bq-lRvAXGzHQIXH_etPOxA&d=9283783873717))
   is answered by the LF team; it expects a person as the contact.
3. Confirm whether to use "Ikalus1988" or a legal name in the byline (bio above assumes the handle).

The article file is final-draft quality; no further edits are expected after submission, per
the guidelines.

## 5. Plan B (Ambassador) — readiness note

The Ambassador programme asks for recurring output (monthly tutorial, talk, or blog). This
submission is the prerequisite artefact; the follow-up cadence we can realistically sustain:

- already published / publishable material: external pilot reports, the injection-defense
  write-up (`docs/agents/content-injection-defense.md`), benchmark notes;
- a second post candidate: "What 380 lessons taught us about error-signature indexing";
- a third: "Running an anonymous intake channel without getting flooded".

Suggested outreach once published: reference the published AAIF post URL when contacting
**Jake Pineda** about the Ambassador programme (application strength comes from the
published post, per the programme's own framing).
