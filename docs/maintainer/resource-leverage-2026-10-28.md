# Resource leverage, measured (2026-10-28)

This page tracks the Cloudflare and Google recommendations made during the 2026-10-27/28 round:
**what was actually implemented, what it measurably changed, and — where it applies — whether the
recommendation still holds.** It exists because three of those recommendations were wrong, and a
recommendation nobody re-checks is how a wrong one survives for months.

Read it as a ledger, not a plan. Every "evidence" cell is something that can be re-run.

## 1. What landed, and what it changed

| # | Recommendation | State | Measured effect on the repo |
|---|---|---|---|
| CF-1 | Publish the corpus + benchmarks on R2 behind a versioned manifest | **done** | `data.misakanet.org` serves 6 files (~2.9 MiB) with per-file SHA-256; 3 publishes ran; every file re-downloaded and hash-matched after each |
| CF-2 | Make the version label immutable (`<date>-<sha>`) | **done** (after a defect) | first design used the date alone and **two same-day merges overwrote each other**; the promise in `DATASET.md` was false for one publish |
| CF-3 | Keep the release environment approval, do not automate it | **holding** | 3 publishes, each approved by a human; the approval-watch gate now lists the workflow, so a pending publish is visible |
| G-1 | Use Vertex `gemini-embedding-001` for a retrieval ceiling | **done** | the A/B that measured R@1 0.757 and changed the retrieval roadmap |
| G-2 | Publish the corpus as a queryable BigQuery dataset | **done** | 651 lessons + 267 queries, public (`allAuthenticatedUsers: READER`), joins work; no download needed to ask "how many lessons are `fanuc`" |
| G-3 | `bge-m3` arm (the model production already runs) | **done** | changed the answer: gate ≈18 points, model swap ≈9 |
| G-4 | Decision-queue digest for stalled `decision` issues | **not done** | 94 non-corpus issues open, 41 never commented, 5 `decision` issues from 2026-09-30 still at 0 comments |
| G-5 | Colab notebook: reproduce the benchmark in five minutes | **not done** | dataset is downloadable and queryable; the five-minute path does not exist |
| CF-4 | Migrate `kv_store` out of D1 into KV | **deliberately not done** | `kv_store` is 67,575 rows / 567 MB, D1 total 752 MB of 5 GB, and rows-read stopped being binding on the paid plan — it is an optimisation of a resource that is not scarce |
| CF-5 | Delete the two zero-traffic workers (`misakanet`, `misakanet-api`) | **not done** | both at 0 requests/week; needs a write credential, so it is an owner action |
| CF-6 | Create the Analytics Engine dataset | **blocked** | the API answers 404 for the account; needs dashboard creation, then the "state of agent failures" report has data |

## 2. Where the recommendation was wrong

Three claims from this round were wrong, and they were wrong in the same direction.

| Claim | What was actually true | How it was caught |
|---|---|---|
| "Gemini generation is blocked until $10 of AI Studio prepay" | **Free tier works.** A key in a billing-disabled project generated text (`gemini-3.1-flash-lite`, HTTP 200) and embedded 3072-dim vectors. The 402 was **that project's** depleted prepay, not Gemini's price | created a key in the no-billing project and called it |
| "Vertex publisher models are 404 = Free Trial restriction" | The restriction is **model-class**, not account-level: embedding models on the same endpoint answer 200; generative ones 404 | called `:predict` on an embedding model |
| "`bge-m3`'s pure-vector arm is not reachable from outside the worker" | Workers AI serves it over the REST API; the arm ran in 25 batches | called the REST endpoint |

Every one of them was an **inference from a single error response**, reported as a capability fact.
The third one is the expensive kind: it was published in a merged benchmark report as a limitation,
and the next round could have spent a day re-deriving it.

**The rule that prevents the next one:** an availability claim needs a probe, and the probe must
distinguish *the four different reasons an API refuses* — no permission (403), not enabled (404 with
a "please enable" body), exhausted quota (429/402 with a quota metric), and wrong request shape (400).
Three of those look identical in a one-line summary and mean completely different things. The repo
already applies this to its own tests ("先复现，再解释"); it was not applied to the cloud account.

## 3. What the round changed for the project, in numbers

- **The retrieval roadmap changed direction.** Before: "the vector arm is a ceiling we cannot see;
  consider a stronger embedding". After: the gate that keeps the existing embedding from running is
  worth ~18 points, a model swap ~9, and `bge-m3` is *better* at same-language Chinese. The next
  experiment is a ranking decision, not a dependency.
- **The corpus became citable and queryable** — R2 for files, BigQuery for questions. Before this
  round the only way to answer "how many `fanuc` lessons are there" was to clone and run code.
- **Two process holes got named.** Five of ten Coogen borrowings landed with no issue or PR
  (ADR 0002 now requires the trail); 41 of 94 non-corpus issues have never been commented on, and
  nothing watches the `decision` label.

## 4. Open items and their triggers

| Item | Trigger to act |
|---|---|
| `kv_store` → KV | D1 storage above ~4 GB, or a page load above ~500 ms attributable to the 1.38 MB blobs |
| Analytics Engine dataset | the "state of agent failures" report is scheduled — it needs the dataset first |
| Colab notebook | next time someone outside the project asks how to reproduce a number |
| Decision digest | now: 5 `decision` issues have been silent for 28 days |
| Free-tier Gemini key | before it is used by anything automated: free quota is per project, so a leaked key burns it |

## Related

- `DATASET.md` — what ships, and how to cite it
- `docs/benchmarks/embedding-ab-2026-10-27.md` — the three-arm measurement this page reports
- `docs/adr/0002-end-coogen-borrowing.md` — the decision process this round used for a product call
- `docs/maintainer/handoff-2026-10-27.md` — the cross-volume state
