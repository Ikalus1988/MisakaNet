#!/usr/bin/env python3
"""`scripts/embedding_ab_metrics.py` — the scoring half of the offline embedding A/B.

Why a test for a scorer
-----------------------
The script exists to answer one question cheaply: does embedding A put the target lesson higher than
embedding B on the L1-267 query set? Its output is a table of rates plus the rows behind them, and a
wrong rate is worse than no rate — it is a confident number produced exactly when someone is deciding
whether to ship a model. So everything that can silently be wrong is pinned here: the cosine ranking
on a 3x3 example small enough to do by hand, the R@k / `no_match` tallies, the threshold rule
(including the part where 0.0 must mean *off*), both bucketings, the query-vector join that would
quietly drop a query if it were a plain dict, the missing-file exit, and the JSON shape a downstream
report consumes.

The live endpoint is not involved, and no real vector artifact is read: `corpus.json` and the
`vectors-*.jsonl` files are produced by a separate job run and do not exist in the checkout, so every
input here is synthetic bytes written to `tmp_path`. The one exception is deliberate — the
cross-lingual split is checked against two real lesson files under `lessons/`, because that bucket is
defined by the repository's own Chinese-lesson rule and a fixture would only test the fixture.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

# The scorer is numpy-based (649 x 3072 cosine, per query). numpy is not in `requirements.txt` — it is
# an analysis dependency, like the other bench scripts — so a checkout without it skips this file
# instead of failing collection for the whole suite.

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import embedding_ab_metrics as ab  # noqa: E402

# Two real lessons, used only by the cross-lingual test. Both are asserted to exist before use: a
# rename should fail this test loudly rather than turn the split into `unknown` and pass.
REAL_ZH_LESSON = "lessons/contrib/astro-dev-stale-css-screenshot.md"
REAL_EN_LESSON = "lessons/core/a-security-fix-that-turns-tests-red-is-the-fix-working.md"


# ── synthetic artifacts ─────────────────────────────────────────────────────────────────────────────


def lesson_row(lesson_id: str, path: str | None = None) -> dict:
    """A corpus row. `text` is carried for schema parity; the scorer reads `id` and `path` only."""
    return {
        "id": lesson_id,
        "path": path or f"lessons/not-in-this-checkout/{lesson_id}.md",
        "title": f"lesson {lesson_id}",
        "domain": "test",
        "text": "synthetic body; the scorer must not need it",
    }


def query_row(
    lesson_id: str, *, lang: str = "en", overlap: str = "high", target_url: str | None = None
) -> dict:
    return {
        "lesson_id": lesson_id,
        "target_url": target_url or f"lessons/not-in-this-checkout/{lesson_id}.md",
        "query": f"how do I fix {lesson_id}",
        "lang": lang,
        "domain": "test",
        "overlap_bucket": overlap,
    }


def write_artifacts(
    root: Path,
    *,
    corpus: list[dict],
    queries: list[dict],
    lesson_vectors: list[tuple[str, list[float]]],
    query_vectors: list[tuple[str, list[float]]],
) -> Path:
    """The four files, byte-for-byte as the schema documents them."""
    root.mkdir(parents=True, exist_ok=True)
    (root / ab.CORPUS_FILE).write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    (root / ab.QUERIES_FILE).write_text(json.dumps(queries, ensure_ascii=False), encoding="utf-8")
    for name, rows in (
        (ab.LESSON_VECTORS_FILE, lesson_vectors),
        (ab.QUERY_VECTORS_FILE, query_vectors),
    ):
        body = "\n".join(json.dumps({"id": key, "vector": vector}) for key, vector in rows)
        (root / name).write_text(body + "\n", encoding="utf-8")
    return root


def score(
    corpus: list[dict],
    queries: list[dict],
    lesson_vectors: list[tuple[str, list[float]]],
    query_vectors: list[tuple[str, list[float]]],
    **kwargs,
) -> dict:
    return ab.evaluate(corpus, queries, lesson_vectors, query_vectors, **kwargs)


# ── the ranking, on an example small enough to check by hand ───────────────────────────────────────


def test_cosine_ranking_on_a_hand_computed_3x3_example():
    """Three lessons in 2-D, four queries, every cosine written out below.

    `cos-xy` is the point of using [1, 1] rather than a unit vector: without L2 normalisation it would
    tie with `cos-x` at 1.0 on the first query, and the ranking would be a coin flip on file order.
    Normalised, its cosine drops to 1/sqrt(2) and the expected order is unambiguous.
    """
    corpus = [lesson_row("cos-x"), lesson_row("cos-y"), lesson_row("cos-xy")]
    lesson_vectors = [("cos-x", [1.0, 0.0]), ("cos-y", [0.0, 1.0]), ("cos-xy", [1.0, 1.0])]
    queries = [
        query_row("cos-x"),  # q1
        query_row("cos-xy"),  # q2
        query_row("cos-y"),  # q3
        query_row("cos-x"),  # q4
    ]
    query_vectors = [
        ("cos-x", [1.0, 0.0]),  # q1: cos = x 1.0, y 0.0, xy 0.7071
        ("cos-xy", [0.0, 1.0]),  # q2: cos = x 0.0, y 1.0, xy 0.7071
        ("cos-y", [1.0, -1.0]),  # q3: cos = x 0.7071, y -0.7071, xy 0.0
        ("cos-x", [1.0, 1.0]),  # q4: cos = x 0.7071, y 0.7071, xy 1.0
    ]

    summary = score(corpus, queries, lesson_vectors, query_vectors)

    expected = [
        # lesson_id, rank of the target, best cosine, full ranking
        ("cos-x", 1, 1.0, ["cos-x", "cos-xy", "cos-y"]),
        ("cos-xy", 2, 1.0, ["cos-y", "cos-xy", "cos-x"]),
        ("cos-y", 3, 0.707107, ["cos-x", "cos-xy", "cos-y"]),
        ("cos-x", 2, 1.0, ["cos-xy", "cos-x", "cos-y"]),
    ]
    assert [
        (row["lesson_id"], row["rank"], row["best_cosine"], row["top_ids"])
        for row in summary["rows"]
    ] == expected

    # Four queries, one bucket: R@1 is one row, R@3 is all four (ranks 1, 2, 3, 2).
    assert summary["n_lessons"] == 3 and summary["n_queries"] == 4 and summary["dims"] == 2
    assert summary["buckets"]["en/high"] == {
        "n": 4,
        "r@1": 0.25,
        "r@3": 1.0,
        "r@5": 1.0,
        "no_match": 0.0,
    }


def test_a_tie_keeps_corpus_order_so_two_runs_cannot_disagree():
    """The q4 row above ties `cos-x` and `cos-y` at 0.7071; the expected list already fixes the
    order, but state the rule here so a future switch to an unstable sort fails a named test rather
    than a rank."""
    corpus = [lesson_row("cos-x"), lesson_row("cos-y"), lesson_row("cos-xy")]
    lesson_vectors = [("cos-x", [1.0, 0.0]), ("cos-y", [0.0, 1.0]), ("cos-xy", [1.0, 1.0])]
    summary = score(corpus, [query_row("cos-x")], lesson_vectors, [("cos-x", [1.0, 1.0])])
    assert summary["rows"][0]["top_ids"] == ["cos-xy", "cos-x", "cos-y"]


# ── R@k arithmetic ─────────────────────────────────────────────────────────────────────────────────

# Six axis-aligned unit lessons, so the cosine of a ladder query with lesson i is just q[i] / ||q||.
BASIS = [f"t{i}" for i in range(1, 7)]


def basis_lessons() -> list[dict]:
    return [lesson_row(lesson_id) for lesson_id in BASIS]


def basis_vectors() -> list[tuple[str, list[float]]]:
    return [
        (lesson_id, [1.0 if j == i else 0.0 for j in range(6)]) for i, lesson_id in enumerate(BASIS)
    ]


# Query k has its target at rank k: every earlier component is larger, every later one smaller.
LADDER = {
    1: [1.0, 0.5, 0.2, 0.0, 0.0, 0.0],  # t1 1.0, t2 0.5, t3 0.2, t4..t6 0
    2: [1.0, 0.9, 0.1, 0.0, 0.0, 0.0],  # t1 1.0, t2 0.9, t3 0.1
    3: [1.0, 0.9, 0.8, 0.1, 0.0, 0.0],  # t1, t2, t3
    4: [1.0, 0.9, 0.8, 0.7, 0.1, 0.0],  # t1..t4
    5: [1.0, 0.9, 0.8, 0.7, 0.6, 0.0],  # t1..t5
    6: [1.0, 0.9, 0.8, 0.7, 0.6, 0.5],  # t1..t6 -> outside the top-5 window
}


def ladder_queries(
    meta: dict[str, tuple[str, str]],
) -> tuple[list[dict], list[tuple[str, list[float]]]]:
    """`meta` maps target id -> (lang, overlap); the vector ladder is fixed by the target's rank."""
    queries = [
        query_row(f"t{rank}", lang=meta[f"t{rank}"][0], overlap=meta[f"t{rank}"][1])
        for rank in range(1, 7)
    ]
    query_vectors = [(f"t{rank}", LADDER[rank]) for rank in range(1, 7)]
    return queries, query_vectors


def test_r_at_k_and_no_match_are_tallied_from_the_ranks_the_ladder_produces():
    queries, query_vectors = ladder_queries({lesson_id: ("en", "high") for lesson_id in BASIS})
    summary = score(basis_lessons(), queries, basis_vectors(), query_vectors)

    assert [row["rank"] for row in summary["rows"]] == [1, 2, 3, 4, 5, None]
    # The sixth target is retrievable in principle but outside the window, so it is `no_match`
    # rather than a rank-6 miss: there is no rank-6 rate in the output to put it in.
    assert "t6" not in summary["rows"][5]["top_ids"]
    assert len(summary["rows"][5]["top_ids"]) == ab.TOP_K

    # 6 rows: ranks 1,2,3,4,5,None -> R@1 1/6, R@3 3/6, R@5 5/6, no_match 1/6.
    assert summary["buckets"]["en/high"] == {
        "n": 6,
        "r@1": 0.167,
        "r@3": 0.5,
        "r@5": 0.833,
        "no_match": 0.167,
    }


def test_buckets_are_query_language_times_overlap():
    meta = {
        "t1": ("en", "high"),  # rank 1
        "t2": ("en", "low"),  # rank 2
        "t3": ("zh", "high"),  # rank 3
        "t4": ("zh", "low"),  # rank 4
        "t5": ("en", "high"),  # rank 5
        "t6": ("zh", "high"),  # outside the window
    }
    queries, query_vectors = ladder_queries(meta)
    summary = score(basis_lessons(), queries, basis_vectors(), query_vectors)

    assert list(summary["buckets"]) == ["en/high", "en/low", "zh/high", "zh/low"]
    assert summary["buckets"]["en/high"] == {
        "n": 2,
        "r@1": 0.5,
        "r@3": 0.5,
        "r@5": 1.0,
        "no_match": 0.0,
    }
    assert summary["buckets"]["en/low"] == {
        "n": 1,
        "r@1": 0.0,
        "r@3": 1.0,
        "r@5": 1.0,
        "no_match": 0.0,
    }
    assert summary["buckets"]["zh/high"] == {
        "n": 2,
        "r@1": 0.0,
        "r@3": 0.5,
        "r@5": 0.5,
        "no_match": 0.5,
    }
    assert summary["buckets"]["zh/low"] == {
        "n": 1,
        "r@1": 0.0,
        "r@3": 0.0,
        "r@5": 1.0,
        "no_match": 0.0,
    }


# ── the threshold ─────────────────────────────────────────────────────────────────────────────────

# One query at 2-D: cos(unit-y) = 1.5/sqrt(3.25) = 0.832050…, cos(unit-x) = 0.5547….
THRESHOLD_BEST = 1.5 / (3.25**0.5)


def threshold_dataset() -> tuple[
    list[dict], list[dict], list[tuple[str, list[float]]], list[tuple[str, list[float]]]
]:
    return (
        [lesson_row("unit-x"), lesson_row("unit-y")],
        [query_row("unit-y")],
        [("unit-x", [1.0, 0.0]), ("unit-y", [0.0, 1.0])],
        [("unit-y", [1.0, 1.5])],
    )


def test_a_row_below_the_threshold_is_a_no_match_even_though_it_was_ranked_first():
    corpus, queries, lesson_vectors, query_vectors = threshold_dataset()

    scored = score(corpus, queries, lesson_vectors, query_vectors, threshold=0.9)
    assert scored["threshold"] == 0.9
    assert scored["rows"][0]["rank"] == 1  # the raw retrieval fact is kept
    assert scored["rows"][0]["best_cosine"] == round(THRESHOLD_BEST, 6)
    assert scored["buckets"]["en/high"] == {
        "n": 1,
        "r@1": 0.0,
        "r@3": 0.0,
        "r@5": 0.0,
        "no_match": 1.0,
    }
    # The same gate applies to the cross-lingual view, or the two halves of the report would
    # disagree about whether a row was retrieved.
    assert scored["cross_lingual"]["en->unknown"] == {"n": 1, "r@1": 0.0}

    # 0.83 is below the best cosine, so this row survives the same gate.
    assert (
        score(corpus, queries, lesson_vectors, query_vectors, threshold=0.8)["buckets"]["en/high"][
            "r@1"
        ]
        == 1.0
    )

    # The comparison is strictly `<`: a threshold equal to the score does not delete the row.
    assert (
        score(corpus, queries, lesson_vectors, query_vectors, threshold=THRESHOLD_BEST)["buckets"][
            "en/high"
        ]["r@1"]
        == 1.0
    )


def test_zero_threshold_is_off_and_does_not_drop_a_negative_cosine():
    """Cosines can be negative. If 0.0 were applied literally, the default run would score every
    honest negative row as `no_match` — the threshold would be on for everyone who did not ask."""
    corpus = [lesson_row("unit-x")]
    queries = [query_row("unit-x")]
    lesson_vectors = [("unit-x", [1.0, 0.0])]
    query_vectors = [("unit-x", [-1.0, 0.0])]  # cosine = -1.0, rank 1

    default = score(corpus, queries, lesson_vectors, query_vectors)
    assert default["rows"][0]["best_cosine"] == -1.0
    assert default["buckets"]["en/high"]["r@1"] == 1.0

    # A non-zero threshold is on, including a negative one.
    gated = score(corpus, queries, lesson_vectors, query_vectors, threshold=-0.5)
    assert gated["buckets"]["en/high"]["no_match"] == 1.0


# ── the cross-lingual split, on real lesson bodies ─────────────────────────────────────────────────


def independent_cjk_share(path: Path) -> float:
    """The repository's lesson-language rule, written out here rather than imported: the point is to
    check the scorer against the *documented* rule, not against itself."""
    body = path.read_text(encoding="utf-8").split("---", 2)[-1][:1500]
    compact = re.sub(r"\s", "", body)
    assert compact, f"empty body in {path}"
    return sum(1 for ch in compact if "\u4e00" <= ch <= "\u9fff") / len(compact)


def test_cjk_ratio_counts_cjk_among_non_whitespace_only():
    assert ab.cjk_ratio("中文abc  \n") == pytest.approx(2 / 5)
    assert ab.cjk_ratio("plain english") == 0.0
    assert ab.cjk_ratio("   \n\t ") == 0.0


def test_cross_lingual_buckets_use_the_target_lessons_own_language(tmp_path):
    zh_path = REPO / REAL_ZH_LESSON
    en_path = REPO / REAL_EN_LESSON
    assert zh_path.is_file(), f"the Chinese fixture lesson moved: {REAL_ZH_LESSON}"
    assert en_path.is_file(), f"the English fixture lesson moved: {REAL_EN_LESSON}"
    # Independent check that the two files really are the two populations, before trusting the split.
    assert independent_cjk_share(zh_path) > ab.CJK_RATIO_THRESHOLD, independent_cjk_share(zh_path)
    assert independent_cjk_share(en_path) <= ab.CJK_RATIO_THRESHOLD, independent_cjk_share(en_path)
    assert ab.lesson_language(zh_path) == "zh"
    assert ab.lesson_language(en_path) == "en"
    assert ab.lesson_language(tmp_path / "nope.md") == "unknown"

    corpus = [
        lesson_row("real-zh", REAL_ZH_LESSON),
        lesson_row("real-en", REAL_EN_LESSON),
        lesson_row("ghost"),  # no body in the checkout -> `unknown`, never folded into `en`
    ]
    lesson_vectors = [("real-zh", [1.0, 0.0]), ("real-en", [0.0, 1.0]), ("ghost", [-1.0, 0.0])]
    queries = [
        query_row("real-zh", lang="zh", target_url=REAL_ZH_LESSON),
        query_row("real-en", lang="zh", target_url=REAL_EN_LESSON),
        query_row("real-zh", lang="en", target_url=REAL_ZH_LESSON),
        query_row("real-en", lang="en", target_url=REAL_EN_LESSON),
        query_row("ghost", lang="zh"),
    ]
    query_vectors = [
        ("real-zh", [1.0, 0.1]),  # zh -> zh lesson, rank 1
        ("real-en", [0.1, 1.0]),  # zh -> en lesson, rank 1
        ("real-zh", [1.0, 0.1]),  # en -> zh lesson, rank 1
        ("real-en", [0.1, 1.0]),  # en -> en lesson, rank 1
        ("ghost", [-1.0, 0.0]),  # zh -> unreadable target, rank 1
    ]

    summary = score(corpus, queries, lesson_vectors, query_vectors, repo_root=REPO)

    assert summary["cross_lingual"] == {
        "en->en": {"n": 1, "r@1": 1.0},
        "en->zh": {"n": 1, "r@1": 1.0},
        "zh->en": {"n": 1, "r@1": 1.0},
        "zh->zh": {"n": 1, "r@1": 1.0},
        "zh->unknown": {"n": 1, "r@1": 1.0},
    }


def test_a_target_missing_from_the_corpus_is_classified_from_its_target_url():
    """The L1-267 set has one such row: `proxy-corporativo-curl-timeout` has no corpus entry, so it
    can never be retrieved, but its body is still readable through `target_url`. Classifying it beats
    dropping it into `unknown` — and it stays a miss either way."""
    corpus = [lesson_row("real-en", REAL_EN_LESSON)]
    queries = [query_row("absent", lang="zh", target_url=REAL_EN_LESSON)]
    summary = score(corpus, queries, [("real-en", [1.0, 0.0])], [("absent", [1.0, 0.0])])

    assert summary["rows"][0]["rank"] is None
    assert summary["cross_lingual"] == {"zh->en": {"n": 1, "r@1": 0.0}}


# ── the query-vector join ──────────────────────────────────────────────────────────────────────────


def test_two_queries_from_one_lesson_both_get_scored():
    """The vector `id` is the query's `lesson_id`, so it is not a unique key for the row. A dict join
    would keep one of these two and report rates over `n_queries == 1`."""
    corpus = [lesson_row("t1"), lesson_row("t2")]
    lesson_vectors = [("t1", [1.0, 0.0]), ("t2", [0.0, 1.0])]
    queries = [query_row("t1"), query_row("t1", lang="zh")]
    query_vectors = [("t1", [1.0, 0.0]), ("t1", [0.0, 1.0])]  # second one prefers t2

    summary = score(corpus, queries, lesson_vectors, query_vectors)

    assert summary["n_queries"] == 2
    assert [row["rank"] for row in summary["rows"]] == [1, 2]
    assert summary["buckets"]["en/high"]["n"] == 1
    assert summary["buckets"]["zh/high"]["n"] == 1


def test_a_short_query_vector_file_is_an_input_error_not_a_silent_drop():
    corpus = [lesson_row("t1"), lesson_row("t2")]
    queries = [query_row("t1"), query_row("t2")]
    with pytest.raises(ab.InputError) as excinfo:
        score(corpus, queries, [("t1", [1.0, 0.0]), ("t2", [0.0, 1.0])], [("t1", [1.0, 0.0])])
    assert ab.QUERY_VECTORS_FILE in str(excinfo.value)
    assert "t2" in str(excinfo.value)


# ── the CLI ───────────────────────────────────────────────────────────────────────────────────────


def shape_dataset() -> dict:
    corpus = basis_lessons()
    queries = [
        query_row("t1", lang="en", overlap="high"),
        query_row("t2", lang="en", overlap="low"),
        query_row("t3", lang="zh", overlap="high"),
        query_row("t4", lang="zh", overlap="low"),
    ]
    lesson_vectors = basis_vectors()
    query_vectors = [("t1", LADDER[1]), ("t2", LADDER[2]), ("t3", LADDER[3]), ("t4", LADDER[4])]
    return {
        "corpus": corpus,
        "queries": queries,
        "lesson_vectors": lesson_vectors,
        "query_vectors": query_vectors,
    }


def test_a_missing_artifact_names_it_and_exits_2(tmp_path, capsys):
    rc = ab.main(["--dir", str(tmp_path / "absent"), "--json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    for name in ab.INPUT_FILES:
        assert str(tmp_path / "absent" / name) in captured.err

    # Only the files that are actually absent are listed; the present ones are not noise.
    (tmp_path / ab.CORPUS_FILE).write_text("[]", encoding="utf-8")
    rc = ab.main(["--dir", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert ab.QUERIES_FILE in captured.err
    assert ab.LESSON_VECTORS_FILE in captured.err
    assert ab.QUERY_VECTORS_FILE in captured.err
    assert ab.CORPUS_FILE not in captured.err


def test_a_second_arms_vectors_are_scored_through_the_overrides(tmp_path, capsys):
    """An A/B keeps both arms under one artifact directory (`vectors-lessons-1024.jsonl` next to
    `vectors-lessons.jsonl`). Without the overrides the CLI would score the same arm twice and the
    "difference" would be zero by construction."""
    write_artifacts(tmp_path, **shape_dataset())
    alt_lessons = tmp_path / "vectors-lessons-1024.jsonl"
    alt_queries = tmp_path / "vectors-queries-1024.jsonl"
    alt_lessons.write_text(
        "\n".join(json.dumps({"id": lesson_id, "vector": [1.0, 0.0]}) for lesson_id in BASIS)
        + "\n",
        encoding="utf-8",
    )
    alt_queries.write_text(
        "\n".join(json.dumps({"id": f"t{rank}", "vector": [1.0, 0.0]}) for rank in range(1, 5))
        + "\n",
        encoding="utf-8",
    )

    assert (
        ab.main(
            [
                "--dir",
                str(tmp_path),
                "--json",
                "--lesson-vectors",
                str(alt_lessons),
                "--query-vectors",
                str(alt_queries),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["dims"] == 2, "the override was ignored and the canonical 6-dim arm was scored"
    assert summary["n_lessons"] == 6

    # Without the overrides the same directory still scores the canonical arm.
    assert ab.main(["--dir", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["dims"] == 6

    # A missing override is named like any other missing input.
    rc = ab.main(
        ["--dir", str(tmp_path), "--json", "--lesson-vectors", str(tmp_path / "nope.jsonl")]
    )
    captured = capsys.readouterr()
    assert rc == 2 and "nope.jsonl" in captured.err


def test_json_output_has_the_exact_shape_a_downstream_report_consumes(tmp_path, capsys):
    data = shape_dataset()
    write_artifacts(tmp_path, **data)

    assert ab.main(["--dir", str(tmp_path), "--json"]) == 0
    captured = capsys.readouterr()
    summary = json.loads(captured.out)  # stdout must be nothing but the summary

    assert list(summary) == [
        "n_queries",
        "n_lessons",
        "dims",
        "threshold",
        "buckets",
        "cross_lingual",
        "rows",
    ]
    assert (summary["n_queries"], summary["n_lessons"], summary["dims"]) == (4, 6, 6)
    assert summary["threshold"] == 0.0
    assert all(isinstance(summary[key], int) for key in ("n_queries", "n_lessons", "dims"))

    assert list(summary["buckets"]) == ["en/high", "en/low", "zh/high", "zh/low"]
    for bucket in summary["buckets"].values():
        assert set(bucket) == {"n", "r@1", "r@3", "r@5", "no_match"}
        assert bucket["n"] == 1
        # Rates are rounded to three decimals, not emitted as recurring floats.
        for rate in ("r@1", "r@3", "r@5", "no_match"):
            assert bucket[rate] == round(bucket[rate], 3), bucket

    # The synthetic bodies are not in the checkout, so every target is `unknown`; the point here is
    # the shape of a cross-lingual bucket, not its value.
    assert summary["cross_lingual"]
    for bucket in summary["cross_lingual"].values():
        assert set(bucket) == {"n", "r@1"}

    assert len(summary["rows"]) == summary["n_queries"]
    for row in summary["rows"]:
        assert set(row) == {"lesson_id", "rank", "best_cosine", "top_ids"}
        assert len(row["top_ids"]) == ab.TOP_K
        assert row["rank"] in (1, 2, 3, 4, 5, None)


def test_the_human_table_reports_the_threshold_it_used(tmp_path, capsys):
    write_artifacts(tmp_path, **shape_dataset())

    assert ab.main(["--dir", str(tmp_path), "--threshold", "0.9"]) == 0
    table = capsys.readouterr().out
    assert "en/high" in table and "zh/low" in table
    assert "threshold 0.900" in table
    assert "cross-lingual" in table

    assert ab.main(["--dir", str(tmp_path)]) == 0
    assert "threshold 0.000 (off)" in capsys.readouterr().out
