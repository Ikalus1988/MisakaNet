#!/usr/bin/env python3
"""Score an offline embedding A/B on the L1-267 query set, with no network in the loop.

Why this exists (2026-10-27)
----------------------------
The published L1-267 run measured retrieval through the hosted endpoint, one query at a time, and its
semantic arm lost two of 267 rows to connection errors. Before paying that cost again for a new
embedding model, the question "does model B rank the target higher than model A" needs only the
vectors: the 267 query strings embedded once, the 649 lesson bodies embedded once, cosine similarity,
top-5. With the endpoint out of the loop, a difference between two runs is a difference between two
embedding models rather than between two rate-limit windows.

What it computes
----------------
* **Pure cosine, top-5, no reranking.** Both sides are L2-normalised and ranked over the *whole*
  lesson pool. That is deliberately the dumbest possible retriever: it isolates the embedding from
  BM25, from the semantic fallback's score floor, and from any reranker, so a number that moves is the
  embedding's doing.
* **Per query-language x overlap** (`en/high`, `zh/high`, ...) — the same slicing the published
  L1-267 report uses, so the offline rates can be read next to the live ones.
* **A cross-lingual split by the *target* lesson's language.** A Chinese query aimed at an English
  lesson is not a tokenisation problem and cannot be fixed by a better ranker; folded into one "zh
  recall" number it hides a problem that is structural. A lesson counts as Chinese when CJK
  characters are more than a quarter of the non-whitespace characters in the first 1500 characters of
  its body, frontmatter skipped — the rule the live zh probe uses, kept identical here so the two
  reports can be compared instead of argued about.
* **An optional `--threshold`** on the best cosine, for replaying a score floor such as the hosted
  fallback's 0.62. Off by default.

Two things it refuses to guess
------------------------------
* **A query vector's `id` is the lesson the query was generated from, not a search key.** It is the
  same value as `queries.json`'s `lesson_id`, which is also the *target* of the query — so it labels
  a row, and two queries from one lesson would share it. The join is therefore per-row with a
  duplicate count, never a plain dict overwrite that would quietly drop a query and inflate every
  rate.
* **`--threshold 0.0` is off, not "cosine >= 0".** Cosines can be negative, so a literal
  `best_cosine < threshold` would silently delete every negative row from a run that asked for no
  threshold at all. The gate only applies when the value is non-zero.

It also refuses to *hide* a miss whose cause is upstream: a query target that is not in the corpus,
or a target body that cannot be read for the language split, is reported in the human table instead
of being dropped from a denominator.

What it is not
--------------
Not a generator (producing the vectors is a separate step), not a gate (nothing here decides a
merge), and not a replacement for the live benches — it measures the embedding, not the service.

Usage
-----
    python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab --json
    python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab
    python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab --threshold 0.62

    # the second arm, from the same directory (the corpus and query set are shared)
    python3 scripts/embedding_ab_metrics.py --dir .cache/embed-ab \
        --lesson-vectors .cache/embed-ab/vectors-lessons-1024.jsonl \
        --query-vectors .cache/embed-ab/vectors-queries-1024.jsonl --json

`--dir` defaults to `<repo>/.cache/embed-ab`; the artifacts are written by a separate embedding job,
so a run before that job finishes exits 2 naming the files that do not exist yet.

Inputs (all four are required; a missing one exits 2 and names it):
    corpus.json             [{id, path, title, domain, text}]
    queries.json            [{lesson_id, target_url, query, lang, domain, overlap_bucket}]
    vectors-lessons.jsonl   {id: <lesson id>, vector: [...]} per line
    vectors-queries.jsonl   {id: <lesson_id of the query's target>, vector: [...]} per line

Output: a human table by default; `--json` prints the machine summary, whose shape is fixed:
`n_queries`, `n_lessons`, `dims`, `threshold`, `buckets`, `cross_lingual`, `rows`.
"""

from __future__ import annotations

import argparse
import json
import math
import operator
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / ".cache" / "embed-ab"

CORPUS_FILE = "corpus.json"
QUERIES_FILE = "queries.json"
LESSON_VECTORS_FILE = "vectors-lessons.jsonl"
QUERY_VECTORS_FILE = "vectors-queries.jsonl"
INPUT_FILES = (CORPUS_FILE, QUERIES_FILE, LESSON_VECTORS_FILE, QUERY_VECTORS_FILE)

TOP_K = 5
# A lesson counts as Chinese when CJK characters are more than a quarter of the non-whitespace
# characters in the first block of its body. The threshold is crude on purpose: it separates the two
# populations in this corpus cleanly, and a finer classifier would imply a precision a bucket split
# does not need. It is the same 0.25 / 1500 the live zh probe applies, so the two reports line up.
CJK_RATIO_THRESHOLD = 0.25
LANG_SAMPLE_CHARS = 1500
CJK_RANGE = ("\u4e00", "\u9fff")


class InputError(Exception):
    """An input file is missing or does not match the documented schema.

    Carries the message printed at exit 2: the caller's job is only to render it. A distinct type
    keeps "the artifacts do not exist yet" (a normal state while the embedding job is still running)
    apart from a bug in this scorer.
    """


# ── reading the four input files ────────────────────────────────────────────────────────────────────


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc
    except UnicodeDecodeError as exc:
        raise InputError(f"cannot decode {path} as UTF-8: {exc}") from exc


def _read_json(path: Path) -> Any:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON ({exc.msg} at line {exc.lineno})") from exc


def _read_jsonl(path: Path) -> list[tuple[int, dict]]:
    """(physical line number, object) pairs. The number is carried so a schema error can point at the
    line a reader would open the file on, not at the object's index among non-blank lines."""
    rows: list[tuple[int, dict]] = []
    for lineno, line in enumerate(_read_text(path).splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise InputError(f"{path}:{lineno}: invalid JSON ({exc.msg})") from exc
        if not isinstance(row, dict):
            raise InputError(f"{path}:{lineno}: expected a JSON object, got {type(row).__name__}")
        rows.append((lineno, row))
    if not rows:
        raise InputError(f"{path}: no rows")
    return rows


def _missing_inputs(paths: Iterable[Path]) -> list[Path]:
    return [path for path in paths if not path.is_file()]


def _load_corpus(path: Path) -> list[dict]:
    rows = _read_json(path)
    if not isinstance(rows, list) or not rows:
        raise InputError(f"{path}: expected a non-empty JSON array of lessons")
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InputError(f"{path}: row {i} is not an object")
        for field in ("id", "path"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise InputError(f"{path}: row {i} has no usable `{field}`")
    duplicates = _duplicates([row["id"] for row in rows])
    if duplicates:
        raise InputError(f"{path}: duplicate lesson id(s): {_preview(duplicates)}")
    return rows


def _load_queries(path: Path) -> list[dict]:
    rows = _read_json(path)
    if not isinstance(rows, list) or not rows:
        raise InputError(f"{path}: expected a non-empty JSON array of queries")
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise InputError(f"{path}: row {i} is not an object")
        for field in ("lesson_id", "lang", "overlap_bucket"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise InputError(f"{path}: row {i} has no usable `{field}`")
    return rows


def _load_vectors(path: Path, what: str) -> list[tuple[str, list[float]]]:
    """Rows as (id, vector). `what` is `lesson` or `query` and only appears in error messages."""
    vectors: list[tuple[str, list[float]]] = []
    dims: int | None = None
    for lineno, row in _read_jsonl(path):
        vector_id = row.get("id")
        if not isinstance(vector_id, str) or not vector_id:
            raise InputError(f"{path}: line {lineno}: missing `id`")
        raw = row.get("vector")
        if not isinstance(raw, list) or not raw:
            raise InputError(
                f"{path}: line {lineno} ({vector_id}): `vector` is not a non-empty list"
            )
        try:
            vector = [float(value) for value in raw]
        except (TypeError, ValueError) as exc:
            raise InputError(
                f"{path}: line {lineno} ({vector_id}): `vector` holds a non-numeric value ({exc})"
            ) from exc
        if not all(math.isfinite(value) for value in vector):
            raise InputError(f"{path}: line {lineno} ({vector_id}): `vector` holds NaN/inf")
        if dims is None:
            dims = len(vector)
        elif len(vector) != dims:
            raise InputError(
                f"{path}: line {lineno} ({vector_id}): {len(vector)}-dim vector where the file's first "
                f"{what} vector has {dims} dims"
            )
        vectors.append((vector_id, vector))
    return vectors


def load_inputs(
    data_dir: Path,
    *,
    lesson_vectors: str | Path | None = None,
    query_vectors: str | Path | None = None,
) -> dict[str, Any]:
    """All four artifacts, validated, or `InputError` naming every file that is missing.

    The two vector paths can be overridden because an A/B keeps both arms' vectors side by side under
    different names (`vectors-lessons-1024.jsonl` next to `vectors-lessons.jsonl`). The corpus and the
    query set are shared by both arms, so only the vector names need a switch.
    """
    data_dir = Path(data_dir)
    paths = {
        "corpus": data_dir / CORPUS_FILE,
        "queries": data_dir / QUERIES_FILE,
        "lesson_vectors": Path(lesson_vectors)
        if lesson_vectors
        else data_dir / LESSON_VECTORS_FILE,
        "query_vectors": Path(query_vectors) if query_vectors else data_dir / QUERY_VECTORS_FILE,
    }
    missing = _missing_inputs(paths.values())
    if missing:
        listed = "\n".join(f"  - {path}" for path in missing)
        raise InputError(f"missing input file(s):\n{listed}")
    return {
        "corpus": _load_corpus(paths["corpus"]),
        "queries": _load_queries(paths["queries"]),
        "lesson_vectors": _load_vectors(paths["lesson_vectors"], "lesson"),
        "query_vectors": _load_vectors(paths["query_vectors"], "query"),
    }


# ── language of a lesson body (the cross-lingual split) ─────────────────────────────────────────────


def cjk_ratio(text: str) -> float:
    """Share of CJK characters among non-whitespace characters. Whitespace is dropped first so a
    heavily indented body is not read as English, and an empty body is `0.0` rather than an error."""
    compact = re.sub(r"\s", "", text or "")
    if not compact:
        return 0.0
    start, end = CJK_RANGE
    return sum(1 for ch in compact if start <= ch <= end) / len(compact)


def lesson_language(path: Path) -> str:
    """`zh`, `en`, or `unknown` when the body cannot be read.

    The frontmatter is skipped before measuring: its tags and title are English even on Chinese
    lessons, and counting them pushes Chinese lessons under the threshold. `unknown` is never folded
    into `en` — a guessed language would move a row between the very cells this split reports on.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "unknown"
    body = raw.split("---", 2)[-1]
    return "zh" if cjk_ratio(body[:LANG_SAMPLE_CHARS]) > CJK_RATIO_THRESHOLD else "en"


def _target_language(
    lesson_id: str,
    *,
    corpus_paths: dict[str, str],
    target_urls: dict[str, str],
    repo_root: Path,
    cache: dict[str, str],
) -> str:
    """Language of the lesson a query is supposed to retrieve, cached per target.

    The corpus `path` wins over the query's `target_url` because the corpus row is the thing that gets
    embedded and ranked. For a translated lesson those differ: `path` is the `lessons/en/` copy while
    `target_url` still names the Chinese original, and classifying by a body that is not in the pool
    would report the target as Chinese while the retriever is scored against English text. In the
    L1-267 set that is 4 of 64 zh rows — a small, real difference from the live report's split, not
    a rounding error.

    `target_url` is only a fallback for a target the corpus does not contain (one such row exists in
    the L1-267 set). Neither is guessed.
    """
    if lesson_id in cache:
        return cache[lesson_id]
    relative = corpus_paths.get(lesson_id) or target_urls.get(lesson_id)
    language = "unknown"
    if relative:
        candidate = Path(repo_root) / relative
        if candidate.is_file():
            language = lesson_language(candidate)
    cache[lesson_id] = language
    return language


# ── scoring ────────────────────────────────────────────────────────────────────────────────────────


def _normalise(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Row-normalised copy. A zero row stays zero instead of turning the whole matrix into NaN: a
    vector with no direction has no angles, and one bad row must not erase every other score."""
    out: list[list[float]] = []
    for row in matrix:
        norm = math.sqrt(sum(map(operator.mul, row, row)))
        out.append([value / norm for value in row] if norm > 0 else [0.0] * len(row))
    return out


def _stack(pairs: Sequence[tuple[str, Sequence[float]]], what: str) -> list[list[float]]:
    dims = len(pairs[0][1])
    for vector_id, vector in pairs:
        if len(vector) != dims:
            raise InputError(f"{what}: {vector_id} has {len(vector)} dims, expected {dims}")
    return [[float(value) for value in vector] for _, vector in pairs]


def align_query_vectors(
    queries: Sequence[dict], query_vectors: Sequence[tuple[str, Sequence[float]]]
) -> list[list[float]]:
    """One vector per query row, in `queries.json` order.

    The vector `id` is the query's `lesson_id`, so a query set with two queries from one lesson has
    two vectors under one id. Counts are checked per id and the rows are paired in file order; a
    plain `dict` overwrite here would drop a query and report rates over a denominator that never
    appears anywhere in the output.
    """
    by_id: dict[str, list[list[float]]] = {}
    for vector_id, vector in query_vectors:
        by_id.setdefault(vector_id, []).append([float(value) for value in vector])
    wanted = Counter(query["lesson_id"] for query in queries)
    unexpected = sorted(set(by_id) - set(wanted))
    unmatched = sorted(
        f"{vector_id} ({len(by_id.get(vector_id, ()))} vectors, {need} rows)"
        for vector_id, need in wanted.items()
        if len(by_id.get(vector_id, ())) != need
    )
    if unexpected or unmatched:
        detail = []
        if unmatched:
            detail.append("query rows without exactly one vector: " + _preview(unmatched))
        if unexpected:
            detail.append("vector ids with no query row: " + _preview(unexpected))
        raise InputError(
            f"{QUERY_VECTORS_FILE} does not line up with {QUERIES_FILE} "
            f"(its `id` is the query's `lesson_id`, not a search key): " + "; ".join(detail)
        )
    taken: Counter = Counter()
    matrix = []
    for query in queries:
        lesson_id = query["lesson_id"]
        matrix.append(by_id[lesson_id][taken[lesson_id]])
        taken[lesson_id] += 1
    return matrix


def _top_indices(scores: Sequence[float], top_k: int) -> list[int]:
    """Indices of the `top_k` best scores, ties broken by corpus order.

    `sorted` is stable and the key is the negated score, so two runs over the same files cannot
    disagree about a rank because of sort internals.
    """
    return sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k]


def _scored_rank(rank: int | None, best_cosine: float, threshold: float) -> int | None:
    """The rank the rates are computed from. A threshold can delete a rank, never add one.

    `threshold == 0.0` is the off switch (see the module docstring): cosines go negative, and a bare
    `best_cosine < 0.0` would make "no threshold" drop rows for having an honest negative score.
    """
    if rank is None:
        return None
    if threshold != 0.0 and best_cosine < threshold:
        return None
    return rank


def _rates(ranks: Sequence[int | None], n: int) -> dict[str, float]:
    return {
        "r@1": round(sum(1 for rank in ranks if rank == 1) / n, 3),
        "r@3": round(sum(1 for rank in ranks if rank is not None and rank <= 3) / n, 3),
        "r@5": round(sum(1 for rank in ranks if rank is not None and rank <= 5) / n, 3),
        "no_match": round(sum(1 for rank in ranks if rank is None) / n, 3),
    }


def _overlap_order(values: Iterable[str]) -> list[str]:
    """`high` before `low`, then anything unexpected alphabetically — a stable JSON key order."""
    present = set(values)
    head = [name for name in ("high", "low") if name in present]
    return head + sorted(present - set(head))


def _target_order(values: Iterable[str]) -> list[str]:
    present = set(values)
    head = [name for name in ("zh", "en", "unknown") if name in present]
    return head + sorted(present - set(head))


def evaluate(
    corpus: Sequence[dict],
    queries: Sequence[dict],
    lesson_vectors: Sequence[tuple[str, Sequence[float]]],
    query_vectors: Sequence[tuple[str, Sequence[float]]],
    *,
    threshold: float = 0.0,
    repo_root: Path = REPO_ROOT,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """The machine summary described in the module docstring.

    `rank` in `rows` is the raw retrieval fact (the target's place in the top-`top_k`, or `None` when
    it is outside the window); `buckets` and `cross_lingual` apply `threshold` on top of it. The two
    are kept apart so a threshold's effect can be read off the rows rather than inferred from a rate.
    """
    if not corpus:
        raise InputError(f"{CORPUS_FILE}: no lessons to rank")
    if not queries:
        raise InputError(f"{QUERIES_FILE}: no queries to score")
    if top_k < 1:
        raise InputError(f"top_k must be at least 1, got {top_k}")

    lesson_ids = [row["id"] for row in corpus]
    duplicates = _duplicates(lesson_ids)
    if duplicates:
        raise InputError(f"{CORPUS_FILE}: duplicate lesson id(s): {_preview(duplicates)}")

    vector_by_id: dict[str, list[float]] = {}
    for vector_id, vector in lesson_vectors:
        if vector_id in vector_by_id:
            raise InputError(f"{LESSON_VECTORS_FILE}: duplicate id {vector_id!r}")
        vector_by_id[vector_id] = vector
    missing = [lesson_id for lesson_id in lesson_ids if lesson_id not in vector_by_id]
    if missing:
        raise InputError(
            f"{LESSON_VECTORS_FILE} is missing {len(missing)} of {len(lesson_ids)} lesson vectors: "
            + _preview(missing)
        )
    # Vector rows for lessons outside the corpus are ignored rather than ranked: the corpus is the
    # pool `n_lessons` reports, and adding rows to it would make the number describe something else.

    lessons = _stack(
        [(lesson_id, vector_by_id[lesson_id]) for lesson_id in lesson_ids], LESSON_VECTORS_FILE
    )
    query_matrix = align_query_vectors(queries, query_vectors)
    if len(query_matrix[0]) != len(lessons[0]):
        raise InputError(
            f"{QUERY_VECTORS_FILE} has {len(query_matrix[0])}-dim vectors but "
            f"{LESSON_VECTORS_FILE} has {len(lessons[0])}-dim vectors"
        )
    dims = len(lessons[0])

    # 267 x 651 dot products of 3072 floats is ~10 s in plain Python (measured 2026-10-27), which is
    # fine for a one-off benchmark and keeps this script dependency-free — the repository's core is
    # zero-dependency by design, and a numpy import here would have made the tests skip in CI.
    query_norm = _normalise(query_matrix)
    lesson_norm = _normalise(lessons)
    similarity = [[sum(map(operator.mul, q, lesson)) for lesson in lesson_norm] for q in query_norm]
    order = [_top_indices(row, top_k) for row in similarity]

    rows: list[dict[str, Any]] = []
    scored: list[tuple[dict, int | None]] = []
    for row_index, (query, ranked) in enumerate(zip(queries, order)):
        top_ids = [lesson_ids[i] for i in ranked]
        best_cosine = float(similarity[row_index][ranked[0]])
        target = query["lesson_id"]
        rank = top_ids.index(target) + 1 if target in top_ids else None
        rows.append(
            {
                "lesson_id": target,
                "rank": rank,
                "best_cosine": round(best_cosine, 6),
                "top_ids": top_ids,
            }
        )
        scored.append((query, _scored_rank(rank, best_cosine, threshold)))

    corpus_paths = {row["id"]: row["path"] for row in corpus}
    target_urls: dict[str, str] = {}
    for query in queries:
        url = query.get("target_url")
        if isinstance(url, str) and url:
            target_urls.setdefault(query["lesson_id"], url)
    language_cache: dict[str, str] = {}
    target_language = {
        query["lesson_id"]: _target_language(
            query["lesson_id"],
            corpus_paths=corpus_paths,
            target_urls=target_urls,
            repo_root=Path(repo_root),
            cache=language_cache,
        )
        for query in queries
    }

    buckets: dict[str, dict[str, Any]] = {}
    for language in sorted({query["lang"] for query in queries}):
        for overlap in _overlap_order(query["overlap_bucket"] for query in queries):
            group = [
                scored_rank
                for query, scored_rank in scored
                if query["lang"] == language and query["overlap_bucket"] == overlap
            ]
            if group:
                buckets[f"{language}/{overlap}"] = {"n": len(group), **_rates(group, len(group))}

    cross_lingual: dict[str, dict[str, Any]] = {}
    for language in sorted({query["lang"] for query in queries}):
        for target in _target_order(target_language.values()):
            group = [
                scored_rank
                for query, scored_rank in scored
                if query["lang"] == language and target_language[query["lesson_id"]] == target
            ]
            if group:
                cross_lingual[f"{language}->{target}"] = {
                    "n": len(group),
                    "r@1": round(sum(1 for rank in group if rank == 1) / len(group), 3),
                }

    return {
        "n_queries": len(queries),
        "n_lessons": len(lesson_ids),
        "dims": dims,
        "threshold": threshold,
        "buckets": buckets,
        "cross_lingual": cross_lingual,
        "rows": rows,
    }


# ── output ────────────────────────────────────────────────────────────────────────────────────────


def _duplicates(values: Iterable[str]) -> list[str]:
    return sorted({value for value, count in Counter(values).items() if count > 1})


def _preview(values: Sequence[str], limit: int = 5) -> str:
    shown = ", ".join(repr(value) for value in values[:limit])
    return shown + (f", … (+{len(values) - limit} more)" if len(values) > limit else "")


def render(summary: dict[str, Any], notes: Sequence[str] = ()) -> str:
    threshold = summary["threshold"]
    gate = "off" if threshold == 0.0 else "rows below it count as no_match"
    lines = [
        "offline embedding A/B — cosine similarity, top-5, no reranking",
        f"  queries {summary['n_queries']} · lessons {summary['n_lessons']} · "
        f"dims {summary['dims']} · threshold {threshold:.3f} ({gate})",
        "",
        "  bucket        n    R@1    R@3    R@5   no_match",
    ]
    for name, bucket in summary["buckets"].items():
        lines.append(
            f"  {name:10s} {bucket['n']:4d}  {bucket['r@1']:.3f}  {bucket['r@3']:.3f}  "
            f"{bucket['r@5']:.3f}    {bucket['no_match']:.3f}"
        )
    lines += [
        "",
        "  cross-lingual (query language -> target lesson language)",
        "  bucket       n    R@1",
    ]
    for name, bucket in summary["cross_lingual"].items():
        lines.append(f"  {name:12s} {bucket['n']:4d}  {bucket['r@1']:.3f}")
    if notes:
        lines += [""] + [f"  note: {note}" for note in notes]
    return "\n".join(lines)


def _notes(summary: dict[str, Any], corpus: Sequence[dict], queries: Sequence[dict]) -> list[str]:
    """Anomalies that would otherwise be silent: they change a denominator or a bucket."""
    notes: list[str] = []
    corpus_ids = {row["id"] for row in corpus}
    absent = sorted({query["lesson_id"] for query in queries} - corpus_ids)
    if absent:
        notes.append(
            f"{len(absent)} query target(s) are not in the lesson corpus and cannot be retrieved: "
            f"{_preview(absent, 3)}"
        )
    unreadable = sum(
        bucket["n"]
        for name, bucket in summary["cross_lingual"].items()
        if name.endswith("->unknown")
    )
    if unreadable:
        notes.append(
            f"{unreadable} target body/bodies could not be read; bucketed as `unknown` instead of "
            "guessing a language"
        )
    return notes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Default inputs in --dir: "
        + ", ".join(INPUT_FILES)
        + " (the two vector names can be overridden)",
    )
    parser.add_argument(
        "--dir",
        default=str(DEFAULT_DIR),
        metavar="DIR",
        help=f"artifact directory holding the four input files (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the machine summary, not the table"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        metavar="COSINE",
        help="a row whose best cosine is below this counts as no_match; 0.0 (the default) is off",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        metavar="DIR",
        help="checkout that the lessons/<...>.md bodies are read from (default: this script's repo)",
    )
    parser.add_argument(
        "--lesson-vectors",
        default=None,
        metavar="PATH",
        help=f"lesson vectors (default: {{--dir}}/{LESSON_VECTORS_FILE}); set it to score the second arm "
        "from the same directory",
    )
    parser.add_argument(
        "--query-vectors",
        default=None,
        metavar="PATH",
        help=f"query vectors (default: {{--dir}}/{QUERY_VECTORS_FILE}); must match the arm named by "
        "--lesson-vectors",
    )
    args = parser.parse_args(argv)

    try:
        inputs = load_inputs(
            Path(args.dir),
            lesson_vectors=args.lesson_vectors,
            query_vectors=args.query_vectors,
        )
        summary = evaluate(
            inputs["corpus"],
            inputs["queries"],
            inputs["lesson_vectors"],
            inputs["query_vectors"],
            threshold=args.threshold,
            repo_root=Path(args.repo_root),
        )
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    else:
        print(render(summary, _notes(summary, inputs["corpus"], inputs["queries"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
