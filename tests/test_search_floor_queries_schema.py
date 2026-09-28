#!/usr/bin/env python3
"""`data/search-floor-queries.jsonl` — the dual-language search bench, as a checked data file.

Why a schema test for a query list
----------------------------------
Issue #2357 asks for one bench with two floors, because every earlier attempt at CJK recall was judged
on the Chinese side alone and quietly cost English recall (#2250 records four such designs). A list
that *is* the measurement has to be checkable in its own right, or the floor it produces is a number
nobody can audit:

* a row whose `expected` lesson does not exist can never be found, so it silently lowers every floor;
* a row labelled `body-only` whose token is actually in a title is not testing what it claims;
* a truncated or duplicated list changes the denominator, which changes the floor's meaning.

Each rule below has a red case in `RED_CASES`-style fixtures — the tests build the broken row and
assert the checker rejects it — because a schema rule that cannot fail is decoration.

Two deliberate exclusions, both recorded here so they are decisions rather than gaps:

* `data/regression_queries.json`'s `mcp-001` ("MCP server setup error") has an **empty**
  `expected_lessons`, so it has no lesson that must be returned. It stays in the calibration harness,
  which measures corpus coverage, and is out of a bench whose premise is "the corpus answers this".
* `docs/**` prose is not a source of rows: every row's `source` is a repository file that exists, or
  the dated corpus sweep that produced it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JSONL = REPO / "data" / "search-floor-queries.jsonl"
LESSONS = REPO / "data" / "lessons.json"
BENCH = REPO / "workers" / "search-dual-floor.test.mjs"
REGRESSION = REPO / "data" / "regression_queries.json"

REQUIRED = ("id", "language", "shape", "query", "expected", "source")
OPTIONAL = ("note", "body_only_token")
LANGUAGES = ("en", "zh")
SHAPES = ("latin", "body-only", "cjk", "mixed", "two-char")
MIN_PER_LANGUAGE = 20


def rows() -> list[dict]:
    return [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]


def problems(items: list[dict] | None = None) -> list[str]:
    """Every problem with the file, so a full run reports all of them rather than the first."""
    items = rows() if items is None else items
    found: list[str] = []
    lesson_ids = {lesson["id"] for lesson in json.loads(LESSONS.read_text(encoding="utf-8"))}
    titles = " ".join((lesson.get("title") or "") for lesson in
                      json.loads(LESSONS.read_text(encoding="utf-8"))).lower()
    bodies = {lesson["id"]: f"{lesson.get('title', '')} {lesson.get('summary', '')} "
                            f"{lesson.get('preview', '')}".lower()
              for lesson in json.loads(LESSONS.read_text(encoding="utf-8"))}

    seen_ids: set[str] = set()
    seen_queries: set[str] = set()
    for index, row in enumerate(items, 1):
        where = f"row {index} ({row.get('id', 'no id')})"
        missing = [key for key in REQUIRED if key not in row]
        if missing:
            found.append(f"{where}: missing {missing}")
            continue
        unknown = sorted(set(row) - set(REQUIRED) - set(OPTIONAL))
        if unknown:
            found.append(f"{where}: unknown field(s) {unknown} — a typo'd field would be ignored")
        if row["id"] in seen_ids:
            found.append(f"{where}: duplicate id")
        seen_ids.add(row["id"])
        if row["query"].strip().lower() in seen_queries:
            found.append(f"{where}: duplicate query {row['query']!r}")
        seen_queries.add(row["query"].strip().lower())
        if row["language"] not in LANGUAGES:
            found.append(f"{where}: language {row['language']!r} not in {LANGUAGES}")
        if row["shape"] not in SHAPES:
            found.append(f"{where}: shape {row['shape']!r} not in {SHAPES}")
        if not str(row["query"]).strip():
            found.append(f"{where}: empty query")
        expected = row["expected"]
        if not isinstance(expected, list) or not expected:
            found.append(f"{where}: `expected` must be a non-empty list — a row that can never be "
                         "found only lowers the floor")
            continue
        for lesson_id in expected:
            if lesson_id not in lesson_ids:
                found.append(f"{where}: expected lesson {lesson_id!r} is not in data/lessons.json")
        source = str(row["source"])
        if "/" in source and not (REPO / source).exists():
            found.append(f"{where}: source {source!r} does not exist in this repository")
        if row["shape"] == "body-only":
            token = row.get("body_only_token")
            if not token:
                found.append(f"{where}: a body-only row must name the `body_only_token` it is about, "
                             "or the label is unfalsifiable")
                continue
            actual = [lesson_id for lesson_id in expected if token.lower() in bodies.get(lesson_id, "")]
            if not actual:
                found.append(f"{where}: {token!r} does not appear in the body of {expected}")
            if token.lower() in titles:
                found.append(f"{where}: {token!r} appears in a lesson *title*, so this row would pass "
                             "a title-only matcher and is not evidence about the body")
        elif "body_only_token" in row:
            found.append(f"{where}: `body_only_token` on a row that is not body-only")

    for language in LANGUAGES:
        count = sum(1 for row in items if row.get("language") == language)
        if count < MIN_PER_LANGUAGE:
            found.append(f"{language}: {count} rows, fewer than the {MIN_PER_LANGUAGE} the bench is "
                         "defined as covering (#2357)")
    shapes = {row.get("shape") for row in items}
    for shape in SHAPES:
        if shape not in shapes:
            found.append(f"no row has shape {shape!r} — #2357 asks for CJK-only, mixed, a two-character "
                         "word, and a body-only English query")
    return found


def test_the_bench_data_is_valid():
    found = problems()
    assert found == [], "data/search-floor-queries.jsonl:\n  - " + "\n  - ".join(found)


# ── every rule can go red ─────────────────────────────────────────────────────────────────────────
#
# The checker is called with a mutated copy rather than through the file, so a red case cannot depend
# on the real list being broken. Each entry is (label, mutate) and each must produce a problem whose
# text names the thing that was mutated.
_BASE = [
    {"id": "en-x", "language": "en", "shape": "latin", "query": "query one",
     "expected": ["pip-install-timeout-ssl"], "source": "data/regression_queries.json"},
    {"id": "en-y", "language": "en", "shape": "body-only", "query": "query two",
     "expected": ["pull-request-welcome-trigger-trap"], "body_only_token": "first_time_contributor",
     "source": "corpus sweep 2026-09-28"},
    {"id": "zh-x", "language": "zh", "shape": "cjk", "query": "查询", "expected": ["cron-job-not-running"],
     "source": "scripts/eval_query_aliases.py"},
    {"id": "zh-y", "language": "zh", "shape": "two-char", "query": "乱码",
     "expected": ["python-gbk-encoding-error"], "source": "corpus sweep 2026-09-28"},
    {"id": "zh-z", "language": "zh", "shape": "mixed", "query": "pip 安装", "expected": ["disk-space-cleanup"],
     "source": "scripts/eval_query_aliases.py"},
]


def _padded() -> list[dict]:
    """The fixture grown to the minimum row count, so a red case is about one thing only."""
    items = [dict(row) for row in _BASE]
    while sum(1 for row in items if row["language"] == "en") < MIN_PER_LANGUAGE:
        items.append({"id": f"en-pad-{len(items)}", "language": "en", "shape": "latin",
                      "query": f"padding query {len(items)}", "expected": ["cron-job-not-running"],
                      "source": "corpus sweep 2026-09-28"})
    while sum(1 for row in items if row["language"] == "zh") < MIN_PER_LANGUAGE:
        items.append({"id": f"zh-pad-{len(items)}", "language": "zh", "shape": "cjk",
                      "query": f"填充查询 {len(items)}", "expected": ["cron-job-not-running"],
                      "source": "corpus sweep 2026-09-28"})
    return items


def test_the_padded_fixture_is_clean():
    """The control for every red case below: without this, a checker that failed everything would
    'prove' all of them."""
    assert problems(_padded()) == [], problems(_padded())


def test_each_red_case_is_caught():
    def drop_expected(items):
        items[0]["expected"] = []

    def unknown_lesson(items):
        items[0]["expected"] = ["no-such-lesson"]

    def duplicate_id(items):
        items[1]["id"] = items[0]["id"]

    def duplicate_query(items):
        items[1]["query"] = items[0]["query"]

    def bad_language(items):
        items[0]["language"] = "de"

    def bad_shape(items):
        items[0]["shape"] = "greek"

    def unknown_field(items):
        items[0]["expectd"] = ["x"]

    def typo_in_body_only(items):
        items[1]["body_only_token"] = "not-in-any-body"

    def title_token_labelled_body_only(items):
        # "cron-job-not-running" is that lesson's *id* and appears in its title text, which is what a
        # row abusing the `body-only` label would look like.
        items[1]["expected"] = ["cron-job-not-running"]
        items[1]["body_only_token"] = "cron"

    def missing_body_only_token(items):
        items[1].pop("body_only_token")

    def token_on_a_non_body_row(items):
        items[0]["body_only_token"] = "pip"

    def missing_language(items):
        items[:] = [row for row in items if row["language"] != "zh"]

    def missing_shape(items):
        items[:] = [row for row in items if row["shape"] != "two-char"]

    def missing_required_field(items):
        items[0].pop("query")

    def dead_source(items):
        items[0]["source"] = "docs/does-not-exist.md"

    red_cases = {
        "no expected lesson": (drop_expected, "non-empty"),
        "expected lesson not in the corpus": (unknown_lesson, "not in data/lessons.json"),
        "duplicate id": (duplicate_id, "duplicate id"),
        "duplicate query": (duplicate_query, "duplicate query"),
        "unknown language": (bad_language, "not in"),
        "unknown shape": (bad_shape, "not in"),
        "mis-spelled field": (unknown_field, "unknown field"),
        "body-only token that is in no body": (typo_in_body_only, "does not appear in the body"),
        "token that is really in a title": (title_token_labelled_body_only, "appears in a lesson *title*"),
        "body-only row with no token": (missing_body_only_token, "must name the `body_only_token`"),
        "token on a row that is not body-only": (token_on_a_non_body_row, "not body-only"),
        "a language below its minimum": (missing_language, "fewer than"),
        "a shape the issue asks for, gone": (missing_shape, "two-char"),
        "a required field deleted": (missing_required_field, "missing"),
        "a source that does not exist": (dead_source, "does not exist"),
    }
    for label, (mutate, expected_text) in red_cases.items():
        items = _padded()
        mutate(items)
        found = problems(items)
        assert any(expected_text in problem for problem in found), (
            f"the checker did not reject {label!r}: {found}"
        )


# ── the two files that have to agree ──────────────────────────────────────────────────────────────

def test_the_english_set_covers_the_repository_regression_queries():
    """`data/regression_queries.json` is the suite's high-signal set; a new row there is a query the
    bench should be measuring, and silently missing it is the gap this test exists for.

    Only the rows with an `expected_lessons` are required: `mcp-001` has none (see the module
    docstring), so there is nothing for it to return.
    """
    bench_queries = {row["query"] for row in rows()}
    regression = json.loads(REGRESSION.read_text(encoding="utf-8"))["queries"]
    missing = [q["query"] for q in regression if q["expected_lessons"] and q["query"] not in bench_queries]
    assert missing == [], (
        f"these `data/regression_queries.json` queries are not in the bench: {missing}. Add a row to "
        "`data/search-floor-queries.jsonl` (the floor may rise with it)."
    )


def test_the_floors_in_the_bench_are_achievable():
    """A floor larger than its own set is unsatisfiable, and a bench with no floor is not a gate."""
    source = BENCH.read_text(encoding="utf-8")
    declared = re.findall(r"export const (EN_FLOOR|ZH_FLOOR) = \{ hit1: (\d+), hit3: (\d+) \};", source)
    floors = {name: (int(hit1), int(hit3)) for name, hit1, hit3 in declared}
    assert set(floors) == {"EN_FLOOR", "ZH_FLOOR"}, (
        f"the bench no longer declares both floors in the shape this test reads: {sorted(floors)}"
    )
    assert "export const MEASURED_ON" in source, (
        "the bench no longer records the corpus and date its floors were measured on, so a reader "
        "cannot tell how old they are"
    )
    for name, language in (("EN_FLOOR", "en"), ("ZH_FLOOR", "zh")):
        total = sum(1 for row in rows() if row["language"] == language)
        for value, label in zip(floors[name], ("hit1", "hit3")):
            assert value <= total, (
                f"{name} {label} = {value} but there are only {total} {language} rows — an "
                "unsatisfiable floor reds the bench for a reason no change can fix"
            )
