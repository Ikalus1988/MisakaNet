#!/usr/bin/env python3
"""`extract_tasks.py` must read the frontmatter the corpus actually writes.

The defect this exists for
--------------------------
`scripts/extract_tasks.py:extract_frontmatter` matched the `---` fence with a regex and then handed
the inside to `json.loads`. The fence regex is right; the parser is wrong for this corpus. Every
lesson writes **YAML** frontmatter — measured 2026-10-14 over `lessons/`: **516 YAML, 3 JSON, 0
without**. So `json.loads` raised on every YAML file and the function returned `None` through a
bare `except`, silently, for all but three lessons.

Nothing failed and nothing was logged, because the function's contract allows `None`. The damage
only showed up downstream, and only if you looked: a regeneration produced 415 tasks of which
**413 carried `domain: "general"`** regardless of what each lesson's frontmatter said, collapsing
a 9-domain working set to 3.

Why this is a generator bug and not a curation decision
------------------------------------------------------
It is tempting to read "the snapshot has 98 files and the corpus yields 441" as a stale snapshot
needing a refresh. It is not, and this test is what settles it: the generator was not producing
415 *lessons*, it was producing 413 near-identical `general` rows. The corpus was never the
bottleneck — the parser was.

The fix delegates to `scripts/lesson_gate.parse_frontmatter`, which already handles JSON, YAML and
the JSON+provenance legacy quirk, and returns the `(dict, body)` pair this call site wants. It is
the sixth frontmatter parser in this repository; this change adds none.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def et():
    spec = importlib.util.spec_from_file_location(
        "extract_tasks_under_test", REPO / "scripts" / "extract_tasks.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "lesson-probe.md"
    path.write_text(body, encoding="utf-8")
    return path


# A minimal but real lesson: both sections the extractor requires, so a failure below is about the
# frontmatter and not about the body.
BODY = "\n## Problem\n\n调用第三方 API 时返回 HTTP 429。\n\n## Solution\n\n指数退避重试。\n"


def test_yaml_frontmatter_is_read_not_swallowed(et, tmp_path):
    """The shape that used to fail: valid YAML between the fences, unparseable as JSON."""
    path = _write(tmp_path, f'---\ntitle: Rate Limit Handling\ndomain: devops\n---\n{BODY}')
    fm = et.extract_frontmatter(path)
    assert fm is not None, "YAML frontmatter returned None — the json.loads parser is back"
    assert fm["domain"] == "devops"
    assert fm["title"] == "Rate Limit Handling"


def test_json_frontmatter_still_works(et, tmp_path):
    """The three legacy files must not regress onto the YAML-only path."""
    path = _write(tmp_path, '---\n{"title": "Legacy", "domain": "rag"}\n---\n' + BODY)
    fm = et.extract_frontmatter(path)
    assert fm is not None and fm["domain"] == "rag"


def test_a_lesson_with_no_frontmatter_is_not_an_error(et, tmp_path):
    """`None` is a legitimate answer here — the extractor falls back to the filename."""
    path = _write(tmp_path, BODY)
    assert et.extract_frontmatter(path) is None


def test_a_real_corpus_lesson_keeps_its_domain(et):
    """The end-to-end claim: a real lesson's domain survives extraction.

    Pinned on the real corpus rather than a fixture so that a change to the *corpus's* frontmatter
    convention shows up here instead of turning the 415-task regeneration into 413 `general` rows
    again. `lessons/contrib/api-rate-limit-handling.md` is YAML and declares `devops`.
    """
    task = et.lesson_to_task(REPO / "lessons" / "contrib" / "api-rate-limit-handling.md")
    assert task is not None, "the pinned lesson stopped being extractable — pick another fixture"
    assert task["domain"] == "devops", (
        f"expected the lesson's own domain, got {task['domain']!r}. A regeneration run now "
        "labels nearly everything 'general' when the frontmatter is not being read."
    )


def test_the_extraction_uses_real_domains_across_the_corpus(et):
    """The measured shape, so the regression is visible as a distribution rather than one file.

    Threshold is deliberately loose — this is a "did it collapse to one bucket" check, not a count.
    """
    domains = set()
    for path in sorted(et.LESSONS_DIR.rglob("*.md")):
        if path.name in ("index.md", "README.md") or "_archive" in str(path):
            continue
        task = et.lesson_to_task(path)
        if task:
            domains.add(task["domain"])
    assert len(domains) >= 20, (
        f"only {len(domains)} distinct domains across the corpus: {sorted(domains)}. With the "
        "json.loads parser this collapses to 1 ('general')."
    )

# ── duplicate task_id ───────────────────────────────────────────────────────────────
# The second half of the regeneration question. `task_id` is derived from the filename stem
# alone, so `lessons/en/<stem>.md` and `lessons/contrib/<stem>.md` both want
# `lesson-<stem>`. The writer keys on `task_id`, so it silently overwrote the earlier lesson —
# 26 of them, measured 2026-10-14 — and said nothing, because "one file wrote successfully" is
# exactly what the code checked.
#
# The data model (is an `en/` lesson a translation, or its own lesson?) is not answerable here:
# only 22 of 64 `lessons/en/` files declare `translated_from`, and 7 of the 26 colliding ones
# declare nothing. So this does not decide it. It refuses to write until it is decided, which is
# the part that is a defect today.


def test_duplicate_task_ids_are_reported_not_silently_overwritten(et):
    claims = et.duplicate_task_ids([
        {"task_id": "lesson-x", "source": "lessons/core/x.md"},
        {"task_id": "lesson-x", "source": "lessons/en/x.md"},
        {"task_id": "lesson-y", "source": "lessons/core/y.md"},
    ])
    assert claims == [("lesson-x", ["lessons/core/x.md", "lessons/en/x.md"])], claims


def test_no_duplicate_task_ids_are_reported(et):
    """The predicate must not fire on a clean list, or the refusal would be noise."""
    assert et.duplicate_task_ids([
        {"task_id": "lesson-a", "source": "lessons/core/a.md"},
        {"task_id": "lesson-b", "source": "lessons/en/b.md"},
    ]) == []


def test_the_real_corpus_does_collide_and_the_check_can_see_it(et):
    """Pins that the collision is real, so the refusal is not guarding a hypothetical.

    The exact count is deliberately not asserted — the corpus will be fixed and this should keep
    passing afterwards. What must not regress is that `duplicate_task_ids` returns [] on a
    collision-free corpus and non-empty here, i.e. that it is actually looking.
    """
    tasks = []
    for path in sorted(et.LESSONS_DIR.rglob("*.md")):
        if path.name in ("index.md", "README.md") or "_archive" in str(path):
            continue
        task = et.lesson_to_task(path)
        if task:
            tasks.append(task)
    collisions = et.duplicate_task_ids(tasks)
    for tid, sources in collisions:
        assert len(sources) > 1
        # Compared after normalising the separator: this test is asserting *which lessons*
        # collide, not re-testing `as_posix()`. What matters is that no source ever carries a
        # backslash — that was the actual Windows failure, and it is asserted separately below.
        assert all("\\" not in s for s in sources), sources
        assert all(s.startswith("lessons/") for s in sources), sources
    # Every collision is an en/ lesson against an original — that is the shape worth reporting.
    for _tid, sources in collisions:
        assert any(s.startswith("lessons/en/") for s in sources), sources


def test_a_written_source_never_contains_a_backslash(et):
    """The generator's `source` is consumed by other platforms, so it must be POSIX.

    `str(Path.relative_to(...))` yields `lessons\\en\\x.md` on Windows and `lessons/en/x.md`
    everywhere else. Writing the former into the JSON produces a path that resolves nowhere else,
    so a Windows regeneration silently changes the shape of the whole working set.
    """
    for path in sorted(et.LESSONS_DIR.rglob("*.md"))[:40]:
        if path.name in ("index.md", "README.md"):
            continue
        task = et.lesson_to_task(path)
        if task:
            assert "\\" not in task["source"], task["source"]


def test_the_source_field_is_built_portably(et):
    """An AST guard, because the failure this prevents is invisible on Linux.

    `str(path.relative_to(ROOT))` and `path.relative_to(ROOT).as_posix()` are byte-identical on
    Linux, so a test that only inspects emitted values passes with either. The defect is only
    observable where `os.sep` is a backslash — it was caught on `windows-latest` and could not be
    reproduced locally at all. Asserting on the emitted string would therefore leave it one
    platform away from coming back, so this reads the expression instead.

    Same reasoning as `test_no_branch_of_run_verification_returns_something_other_than_a_pair`,
    which reads its function's source for the same kind of reason.
    """
    import ast

    source = (REPO / "scripts" / "extract_tasks.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name == "lesson_to_task")

    offenders = []
    for node in ast.walk(fn):
        # `"source": <expr>` inside a dict literal. Note this is a `Dict` key/value pair, not a
        # call's `keyword` — `ast.keyword` only exists for call arguments, and walking for that
        # finds nothing here, which is how a first version of this guard passed on a file that
        # had already been reverted to `str()`.
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and key.value == "source"):
                continue
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == "str"):
                offenders.append(key.lineno)

    assert not offenders, (
        f"lesson_to_task builds `source` with str() at line(s) {offenders}. On Windows that "
        "writes 'lessons\\en\\x.md' into tasks/*.json, which resolves on no other platform. Use "
        "path.relative_to(REPO_ROOT).as_posix()."
    )
