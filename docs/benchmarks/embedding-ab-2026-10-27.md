# Embedding A/B, and what the cross-lingual misses actually are (2026-10-27)

**Status:** one-off offline benchmark. Two questions, one measurement each. It does not change
production and does not propose a model swap on its own.

**Question 1.** The live path misses cross-lingual queries badly — on the 64 Chinese queries of the
L1-267 set, `zh → en` scores **R@1 0.455** while `zh → zh` scores 0.710
([zh cross-lingual probe](retrieval-zh-crosslingual-2026-10-27.md)). Is that a *ranking/gating*
problem, or would a stronger multilingual embedding simply find the lesson?

**Question 2.** The obvious mechanism was that a Chinese query carrying Latin technical tokens
("GitHub Actions", "CDP", "docker-compose") matches an unrelated English lesson on those tokens alone
and never reaches the semantic fallback. Is that what the misses actually look like?

## 1. The embedding arm

**Method.** Embed all 651 published lessons (title + body, first 6000 chars) and the 267 L1-267
queries with `gemini-embedding-001` on Vertex AI, then rank by cosine and take top-5. No BM25, no
fusion, no reranking, no threshold — this is the vector path alone, scored with the same query set
and the same target lessons as the published [L1-267 report](retrieval-l1-267-2026-10-27.md).

| bucket | n | R@1 | R@3 | R@5 | target not in top-5 |
|---|---|---|---|---|---|
| en / high overlap | 78 | 0.923 | 0.987 | 0.987 | 0.013 |
| en / low overlap | 124 | 0.661 | 0.790 | 0.831 | 0.169 |
| zh / high overlap | 37 | **0.838** | 0.946 | 0.946 | 0.054 |
| zh / low overlap | 27 | 0.630 | 0.778 | 0.852 | 0.148 |
| ko / low | 1 | 0.000 | — | — | 1.000 |
| **all** | **267** | **0.757** | **0.865** | **0.891** | **0.109** |

Against the two published arms on the same 267 queries: BM25 alone **R@1 0.210**,
BM25 + semantic fallback **R@1 0.446**. Pure cosine with this model scores **0.757**.

The number that matters for §2.2 of the handoff is the cross-lingual one:

| arm | zh → zh | zh → en |
|---|---|---|
| live production, measured today ([source](retrieval-zh-crosslingual-2026-10-27.json)) | 0.710 (n=31) | **0.455** (n=33) |
| pure cosine, `gemini-embedding-001` @3072 | 0.774 (n=31) | **0.727** (n=33) |
| same, at 1024 dims | 0.742 (n=31) | **0.727** (n=33) |

**Dimensionality barely matters.** 3072 dims scores R@1 0.757 overall, 1024 dims **0.753** — four
thousandths apart, and the cross-lingual bucket is identical (0.727). That matters for adoption
because Cloudflare Vectorize indexes are 1024-dimensional for the `bge-m3` arm today; a 3072-dim
index would be three times the storage for no measured gain.

## 2. The Latin-token hypothesis: refuted

For all 63 usable rows of the live zh probe: 20 misses, of which 13 returned a wrong lesson and 7
returned nothing.

- **17 of the 20 misses contain no Latin token at all.**
- **3 of 20** are "explained by Latin matching" in the broad sense (the wrong lesson contains a query
  token the target also contains) and **0 of 20** in the strict sense (the wrong lesson contains a
  token the target *lacks*).
- The only three shared tokens are `ai`, `ci`, `pr` — one query each, document frequency 39/82/86 of
  651, and **the target lesson contains each of them too**. None discriminates.
- The motivating tokens never appear in a miss: `GitHub`/`Actions` occur in exactly one query and it
  is a rank-2 **hit**; `CDP`, `docker-compose` and `YAML` occur in no query at all.

What the misses do share is CJK lexical proximity: **10 of the 13 wrong-hit misses share at least one
CJK bigram with the lesson they wrongly returned** (1 shares more bigrams with the wrong lesson than
with the target). That is consistent with the CJK bigram channel (#2355) doing its job — matching
Chinese text to Chinese text — and the wrong Chinese-adjacent lesson winning.

So the strong form of the hypothesis is **untested, not disproven**: this query set contains no
rare-technical-token Chinese queries. But it cannot explain the measured cross-lingual miss rate, and
the fix it would suggest (a stoplist on Latin tokens) would not move these numbers.

## 3. What the two results say together

The cross-lingual gap is **not** a vocabulary problem the current tokenizer can reach, and it is
**not** a ranking floor — a plain cosine over a multilingual embedding finds the right English
lesson from a Chinese query 73% of the time, where the live path finds it 45% of the time. The
ceiling is high; production is not near it.

What this does **not** establish is that `gemini-embedding-001` is the model to switch to. The only
isolated arm measured here is that model. **`bge-m3`'s pure-vector arm was not measured** — it lives
inside the worker's binding and there is no route to it from outside, so the honest comparison is
"gemini-embedding vs the system as delivered", not "gemini-embedding vs bge-m3". If `bge-m3` is
already this good on the same corpus, the lever is the *gate* (the fallback runs only on an empty
BM25 result, and 13 of the 20 misses returned a confident wrong hit that suppressed it), not the
model.

That is the next experiment, and it is cheap: score the same 267 queries with the vectors the worker
already has, or with `bge-m3` called directly. Only if that arm lands near 0.45 while this one sits at
0.76 is a model swap the answer.

## 4. What this does not show

- **The queries were generated from the target lesson.** Absolute rates flatter any retriever; the
  arm-to-arm and arm-to-live deltas are the deliverable, not the level.
- **Pure cosine is not the production path.** Production is BM25 first, semantic fallback only on an
  empty result. The 0.757 is a ceiling for the vector path, not a forecast of end-to-end retrieval.
- **`no_match` is not comparable across arms.** Here it means "target not in top-5"; in the live
  report it means "the endpoint returned nothing". They are different quantities.
- **The published L1-267 arms ran on an eval corpus that was not refreshed**, so the comparison to
  them is directional; the live 64-zh comparison is the same-day one and is the one to lean on.
- **8 of 651 lessons exceeded the model's 2048-token input limit** and were auto-truncated (e.g.
  `github-connectivity-4-fallbacks`, `fanuc-karel-core-utility-modules`); their vectors cover the
  first ~2048 tokens only.
- **One query target (`proxy-corporativo-curl-timeout`) has no corpus row**, so it can only miss; it
  is scored against its `target_url` path.
- **One query is Korean** (`ko`), kept in the denominator rather than silently dropped, which is why
  the table sums to 267 and not 266.

## 5. Cost and reproduction

The whole corpus plus the query set is **615,060 input tokens** of embeddings (reported by the API:
610,548 for the 651 lessons, 4,512 for the 267 queries). No generative model was called and no other
Google Cloud service was used; nothing was written to production.

```bash
# 1) embed the corpus and the queries (resumable; --dims 1024 for the second arm)
python3 scripts/embed_vertex.py --in .cache/embed-ab/corpus.json \
  --out .cache/embed-ab/vectors-lessons.jsonl --dims 3072
python3 scripts/embed_vertex.py --in .cache/embed-ab/queries.json \
  --out .cache/embed-ab/vectors-queries.jsonl --field query --id-field lesson_id --dims 3072

# 2) score both arms
python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab
python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab \
  --lesson-vectors .cache/embed-ab/vectors-lessons-1024.jsonl \
  --query-vectors .cache/embed-ab/vectors-queries-1024.jsonl

# 3) what the misses actually look like
python3 scripts/zh_latin_token_analysis.py --json
```

The corpus is built from `data/lessons.json`'s `url` field, not from a glob over `lessons/`: 30
lesson ids exist twice (`lessons/contrib/<id>.md` and `lessons/en/<id>.md`), and globbing picks the
English translation for those, which moves 4 of the 64 Chinese queries into the wrong cross-lingual
bucket. That defect was caught by cross-checking the two arms' bucket counts against the live probe
and is why the corpus now joins on `url`.

## Artifacts

- [Machine-readable results](embedding-ab-2026-10-27.json) — both arms with per-query rows, the
  Latin-token headline, the reference arms, and the limitations above.
- [`scripts/embed_vertex.py`](../../scripts/embed_vertex.py) — the resumable Vertex embedding
  client (stdlib only).
- [`scripts/embedding_ab_metrics.py`](../../scripts/embedding_ab_metrics.py) — cosine top-k scoring
  and bucketing (stdlib only; the full 267×651×3072 matrix scores in ~11 s).
- [`scripts/zh_latin_token_analysis.py`](../../scripts/zh_latin_token_analysis.py) — the miss-shape
  analysis behind §2.
