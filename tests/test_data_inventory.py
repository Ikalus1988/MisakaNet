#!/usr/bin/env python3
"""Every generated file must name a generator that exists, and a consumer someone can point at.

`data/README.md` described five files out of 26, and one of the five named a generator that is **not
in this repository**: `batch_lesson_upgrade.py`. The real generator of `data/lessons.json` is
`scripts/update_lessons_json.py`, and getting that wrong is the whole subject of #1374 ("用
`misakanet-index.py` 会静默回滚线上统计") — a reader who believed the table would have gone looking
for a script that does not exist.

The other half of the problem was silence: **no row named a consumer**, which is how
`sync-data.yml` could publish `counter.json` and `lessons.json` to the `data` branch for weeks with
nothing reading them, and how `data/quality_scores.json` (a 141-lesson snapshot, taken when the corpus
was 402/141 = about a third of its current size) can sit in the tree with no live writer and no reader
without anyone noticing (#1985).

So the rule is not "the table is complete"; it is that the table cannot lie in the ways it did: a
missing row, a row for a file that is gone, or a generator path that is not in the tree.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
README = DATA / "README.md"

# Rows that are not generated artifacts, and the honest markers a generator cell may carry instead of
# a path. Anything else must name a file that exists.
NOT_ARTIFACTS = {".gitkeep", "README.md"}
HONEST_GENERATOR_MARKERS = ("手写", "孤儿", "无现存生成者", "手动", "—")
TABLE_HEADER = "| 文件 | 生成者 | 消费者 | 频率 |"
PATH_TOKEN = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|mjs|js|sh|ya?ml))`")


def tracked_data_files() -> tuple[set[str], set[str]]:
    """(generated artifacts, every tracked path) relative to `data/`.

    `lessons.json` and `okf/lessons.jsonl` are different files, so paths — not basenames — are the key.
    The two sets differ by `NOT_ARTIFACTS`: a row is not *required* for `.gitkeep`/`README.md`, but a row
    for one of them is not a ghost either (the table documents the placeholder on purpose).
    """
    out = subprocess.run(["git", "ls-files", "data/"], cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    every = {line[len("data/"):] for line in out.stdout.split() if line.startswith("data/")}
    generated = {p for p in every if Path(p).name not in NOT_ARTIFACTS}
    return generated, every


def table_rows(doc_text: str) -> dict[str, str] | None:
    """The artifact table only: filename (relative to data/) -> its row. `None` when it is missing.

    Scoped to the table under `TABLE_HEADER`, because this file has a second table comparing the
    `main` tree with the `data` branch, whose first cells are prose.
    """
    lines = doc_text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == TABLE_HEADER)
    except StopIteration:
        return None
    rows: dict[str, str] = {}
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        match = re.match(r"\| `([^`]+)` \|", line)
        if match:
            rows[match.group(1)] = line
    return rows


def inventory_problems(doc_text: str, present: set[str], repo: Path = REPO,
                      allowed: set[str] | None = None) -> list[str]:
    allowed = present if allowed is None else allowed
    rows = table_rows(doc_text)
    if rows is None:
        return [f"data/README.md has no table under {TABLE_HEADER!r}"]
    problems = []
    for name in sorted(present - set(rows)):
        problems.append(f"data/{name} exists but data/README.md has no row for it")
    for name in sorted(set(rows) - allowed):
        problems.append(f"data/README.md has a row for data/{name}, which does not exist")
    for name in sorted(set(rows) & present):
        cells = rows[name].split("|")
        generator = cells[2] if len(cells) > 2 else ""
        if any(marker in generator for marker in HONEST_GENERATOR_MARKERS):
            continue
        tokens = PATH_TOKEN.findall(generator)
        if not tokens:
            problems.append(
                f"data/{name}: the generator cell names no file and carries no honest marker "
                f"({'/'.join(HONEST_GENERATOR_MARKERS)}) — {generator.strip()!r}")
            continue
        for token in tokens:
            if not (repo / token).exists():
                problems.append(
                    f"data/{name}: the generator cell names {token}, which does not exist in this "
                    f"repository (this is the shape of the old `batch_lesson_upgrade.py` row)")
    return problems


def test_the_data_inventory_cannot_lie_about_what_exists():
    generated, every = tracked_data_files()
    problems = inventory_problems(README.read_text(encoding="utf-8"), generated, allowed=every)
    assert not problems, "\n  ".join(problems)


def test_a_missing_row_is_caught(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_text("", encoding="utf-8")
    doc = "| 文件 | 生成者 | 消费者 | 频率 |\n|---|---|---|---|\n| `a.json` | `scripts/x.py` | y | z |\n"
    assert inventory_problems(doc, {"a.json"}, repo=tmp_path) == []
    assert inventory_problems("", {"a.json"}) == [
        "data/README.md has no table under "
        "'| 文件 | 生成者 | 消费者 | 频率 |'"]
    body_only = "| 文件 | 生成者 | 消费者 | 频率 |\n|---|---|---|---|\n"
    assert inventory_problems(body_only, {"a.json"}) == [
        "data/a.json exists but data/README.md has no row for it"]


def test_a_ghost_row_is_caught():
    """The rule is defensive: the old table never had a ghost, but nothing stopped one."""
    doc = "| 文件 | 生成者 | 消费者 | 频率 |\n|---|---|---|---|\n| `gone.json` | 手写输入 | x | y |\n"
    assert inventory_problems(doc, set()) == [
        "data/README.md has a row for data/gone.json, which does not exist"]


def test_a_generator_that_is_not_in_the_tree_is_caught(tmp_path):
    """The defect that was really there: `batch_lesson_upgrade.py` is not in this repository."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "update_lessons_json.py").write_text("", encoding="utf-8")
    head = "| 文件 | 生成者 | 消费者 | 频率 |\n|---|---|---|---|\n"
    problems = inventory_problems(
        head + "| `a.json` | `scripts/batch_lesson_upgrade.py` (CI) | x | y |\n",
        {"a.json"}, repo=tmp_path)
    assert problems and "does not exist in this repository" in problems[0], problems
    # A real path passes; so does an honest marker; so does a workflow file.
    assert inventory_problems(
        head + "| `a.json` | `scripts/update_lessons_json.py` | x | y |\n",
        {"a.json"}, repo=tmp_path) == []
    assert inventory_problems(
        head + "| `a.json` | 无现存生成者（脚本已删）| x | y |\n", {"a.json"}, repo=tmp_path) == []
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "w.yml").write_text("", encoding="utf-8")
    assert inventory_problems(
        head + "| `a.json` | `.github/workflows/w.yml` | x | y |\n", {"a.json"}, repo=tmp_path) == []


def test_a_row_without_any_generator_is_caught():
    head = "| 文件 | 生成者 | 消费者 | 频率 |\n|---|---|---|---|\n"
    problems = inventory_problems(head + "| `a.json` | CI 自动生成 | x | y |\n", {"a.json"})
    assert problems and "names no file" in problems[0], problems


def test_the_files_this_issue_was_about_are_all_described():
    """Each of these is a different lesson; all three were absent or wrong before #1985."""
    rows = table_rows(README.read_text(encoding="utf-8"))
    for name in ("lessons.json", "counter.json", "leaderboard.json", "quality_scores.json",
                 "okf/lessons.jsonl"):
        assert name in rows, f"{name} lost its row"
        assert rows[name].count("|") >= 5, f"{name}'s row lost its columns: {rows[name]!r}"


@pytest.mark.parametrize("name", ["lessons.json", "counter.json", "leaderboard.json"])
def test_the_consumer_column_is_not_empty(name):
    row = table_rows(README.read_text(encoding="utf-8"))[name]
    consumer = row.split("|")[3]
    assert consumer.strip(), f"{name} has an empty consumer cell — that is the field that failed before"
