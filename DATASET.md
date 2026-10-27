# Dataset

The lesson corpus and the retrieval benchmarks, published as files you can cite, download and re-run
without cloning this repository.

- **Latest:** `https://data.misakanet.org/latest.json` — points at the current version
- **This version:** `https://data.misakanet.org/v<YYYY-MM-DD>/manifest.json`
- **What ships:** 651 lessons, 267 benchmark queries, four published run artifacts, ~2.9 MiB
- **Built by:** [`scripts/build_dataset_bundle.py`](scripts/build_dataset_bundle.py), published by
  [`.github/workflows/publish-dataset.yml`](.github/workflows/publish-dataset.yml)

## Files

| File | What it is | License |
|---|---|---|
| `lessons.jsonl` | One lesson per line: title, description, tags, domain, evidence level, repo path | Apache-2.0 |
| `lessons.json` | The same corpus as a JSON array with stable ids | Apache-2.0 |
| `benchmarks/retrieval-l1-267-queries.jsonl` | The 267-query retrieval set, with each query's target lesson | CC0-1.0 |
| `benchmarks/retrieval-l1-267-2026-10-27.json` | BM25 vs semantic-fallback run on those queries | CC0-1.0 |
| `benchmarks/retrieval-zh-crosslingual-2026-10-27.json` | Chinese queries split by the target lesson's language | CC0-1.0 |
| `benchmarks/embedding-ab-2026-10-27.json` | Pure-cosine embedding arms, and the miss-shape analysis | CC0-1.0 |
| `manifest.json` | File list with sizes and SHA-256, licenses, schema, citation | — |

Nothing in the bundle is a link into this repository: `url` fields are repository paths, reproduced
verbatim so an id stays traceable to its source. Everything a consumer needs is in the bundle.

## Licenses, and why they differ

**The corpus is Apache-2.0.** This repository is Apache-2.0 and lesson text was contributed under it,
so the corpus ships under the license it was submitted under. The project cannot grant a different one,
and a dataset that quietly relicensed its contributions would be a defect, not a gift.

**The benchmark artifacts are CC0-1.0.** The query sets and run results are produced by this project,
not contributed. They are dedicated to the public domain because the point of publishing them is that
somebody else runs them — an attribution requirement would add friction to the only outcome that
matters, which is more independent measurement of retrieval.

Both licenses are machine-readable in `manifest.json` (`licenses`, and `license` per file), and the
license texts ship in the bundle (`LICENSE`, `LICENSE-CC0`).

## Citation

```
MisakaNet contributors (2026). MisakaNet — a corpus of agent failure lessons and retrieval
benchmarks. https://misakanet.org/dataset
```

Citing is requested, not required. If you build on the corpus, mention the version
(`v2026-10-27`) — the files are immutable per version, so a citation stays verifiable.

## Versioning

- A version is a date, and a version's files never change. Corrections publish a new version.
- `latest.json` is the only mutable object; everything under `v<date>/` is written once.
- `manifest.json` carries a SHA-256 per file, so a consumer can verify a download without trusting
  this page.

## Re-running the benchmarks

The query set and the run artifacts are enough to replay the retrieval side against any endpoint; the
published reports each carry their own method and limitations section. The two runs added on
2026-10-27 are reproducible with the scripts in `scripts/`:

```bash
python3 scripts/bench_zh_crosslingual.py --attempts 5   # live path, 64 Chinese queries
python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab   # offline cosine arms
```

## What this dataset is not

- **Not a leaderboard.** The benchmarks measure *this* retrieval system on *this* corpus. A number
  from them is not a statement about another system.
- **Not ground truth.** A lesson records one failure somebody actually hit and how it was resolved;
  `evidence_level` says how strongly it has been corroborated, and most are `E0`/`E1`.
- **Not deduplicated by topic.** 651 lessons across 49 domains, including overlapping ones.
