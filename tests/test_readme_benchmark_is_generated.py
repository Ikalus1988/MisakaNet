#!/usr/bin/env python3
"""The README benchmark table is generated, not hand-copied — and the generator actually computes.

Found in the wild (2026-10-06)
------------------------------
`README.md` carried a hand-copied table of weekly `lesson_hit_rate` numbers, last updated
2026-09-21, with no automation. It disagreed with `docs/benchmarks/latest.json` while sitting
three lines below a paragraph explaining exactly what the metric is and is not.

Making it generated could not be done immediately, and the reason is the part worth recording:
**`latest.json` had no timestamp on any run.** `scripts/benchmark_workers_ai.py` now stamps `run_at`
at write time, and `scripts/update_readme_benchmark.py` aggregates on that. Before the stamp, the
only record of which week a run belonged to was the *filename* of the weekly snapshot it was copied
into — a set #2893 prunes to four. So the "weekly" grouping was never in the data; it was in the
filesystem.

All 1155 shipped runs are unstamped, so on a clean checkout the generator computes **zero** rows.
That is the honest state and the script says so rather than inventing history — but it also means
the aggregation code path runs on nothing by default, which is how a broken generator ships green.

What this checks
----------------
1. **The README block is current.** `--check` exits 0. This is the half that stops the second
   source of truth from coming back.
2. **The gate can actually go red.** A hand-typed block that the generator did not produce must make
   `--check` exit 1, without writing. A staleness check that cannot fail is a comment — and
   this file started with exactly that defect: its idempotency test ran the real command, which
   rewrote the README and then passed `--check` on what it had just written, so it could not fail
   and it dirtied the checkout on every pytest run.
3. **The generator computes when data allows it.** Synthetic runs with `run_at`, in a temp copy —
   because with the shipped corpus this path never executes, and an unexecuted path is not evidence.
   The temp copy is what `--readme` / `--benchmarks` are for; without them, testing `main()` means
   writing to the checkout.
4. **Unstamped runs are counted, never guessed.**
5. **A week with only one arm is not a row.** Averaging `with_lesson` against an empty `plain` would
   make the two columns mean different things.
6. **The `run_at` stamp is written.** Asserted against the source of the benchmark script, because
   the whole generator depends on a field that is trivially lost in a refactor — and its absence is
   silent: runs still land, just undated forever.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "scripts" / "update_readme_benchmark.py"
BENCH_SCRIPT = REPO_ROOT / "scripts" / "benchmark_workers_ai.py"
README = REPO_ROOT / "README.md"

BEGIN = "<!-- BEGIN generated: benchmark-trend -->"
END = "<!-- END generated: benchmark-trend -->"


def _load_generator():
    spec = importlib.util.spec_from_file_location("update_readme_benchmark", GENERATOR)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot load {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(*args: str, readme: Path | None = None,
         benchmarks: Path | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(GENERATOR), *args]
    if readme is not None:
        argv += ["--readme", str(readme)]
    if benchmarks is not None:
        argv += ["--benchmarks", str(benchmarks)]
    return subprocess.run(argv, capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)


def _fixture(tmp_path: Path, runs: list[dict], readme_body: str | None = None) -> tuple[Path, Path]:
    """A temp (corpus, README) pair. Nothing here touches the checkout — see below."""
    corpus = tmp_path / "latest.json"
    corpus.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    readme = tmp_path / "README.md"
    body = readme_body if readme_body is not None else (
        f"# Title\n\nsome prose\n\n{BEGIN}\n\n| hand-typed |\n|---|\n| stale |\n\n{END}\n\nafter\n"
    )
    readme.write_text(body, encoding="utf-8")
    return corpus, readme


def _run_rec(when: str, condition: str, rate: float) -> dict:
    return {
        "model": "@cf/meta/llama-3.2-3b-instruct",
        "scenario": "s",
        "condition": condition,
        "status": 200,
        "content": "",
        "metrics": {"lesson_hit_rate": rate, "actionable": True},
        "error": None,
        "run_at": when,
    }


# ── the shipped state ───────────────────────────────────────────────────────

def test_readme_block_is_current():
    """The half that keeps the second source of truth from returning."""
    result = _run("--check")
    assert result.returncode == 0, (
        "README.md benchmark table is stale — run `python3 scripts/update_readme_benchmark.py`. "
        f"stdout: {result.stdout.strip()} stderr: {result.stderr.strip()}"
    )


def test_readme_has_exactly_one_generated_block():
    text = README.read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1, f"{BEGIN} appears {text.count(BEGIN)} times"
    assert text.count(END) == 1, f"{END} appears {text.count(END)} times"
    assert BEGIN in text and text.index(BEGIN) < text.index(END)


def test_generator_is_idempotent(tmp_path):
    """Write twice on a temp copy; the second write must be a byte-for-byte no-op.

    The earlier version of this test ran the real command against the checkout. That version could
    not fail: the generator rewrote the README, returned 0, and `--check` then passed on what it had
    just written. It also meant every pytest run silently mutated the working tree. A test that can
    only pass is worse than no test, because it reads like coverage.
    """
    corpus, readme = _fixture(tmp_path, [_run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.5),
                                        _run_rec("2026-10-05T09:00:01+00:00", "plain", 0.3)])
    first = _run(readme=readme, benchmarks=corpus)
    assert first.returncode == 0, first.stderr
    after_first = readme.read_bytes()
    second = _run(readme=readme, benchmarks=corpus)
    assert second.returncode == 0, second.stderr
    assert readme.read_bytes() == after_first, "the generator is not idempotent"


def test_generator_does_not_touch_the_real_readme(tmp_path):
    """The point of `--readme`: exercising the command must not rewrite the checkout."""
    before = README.read_bytes()
    corpus, readme = _fixture(tmp_path, [_run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.9)])
    result = _run(readme=readme, benchmarks=corpus)
    assert result.returncode == 0, result.stderr
    assert readme.read_bytes() != before, "the temp copy was not rewritten — the run proved nothing"
    assert README.read_bytes() == before, "the generator wrote to the real README.md"


def test_main_computes_rows_end_to_end(tmp_path):
    """`main()` merges seed + computed and writes the file. Neither is reached by the corpus."""
    corpus, readme = _fixture(tmp_path, [
        _run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.50),
        _run_rec("2026-10-05T09:00:01+00:00", "with_lesson", 0.60),
        _run_rec("2026-10-05T09:00:02+00:00", "plain", 0.30),
        _run_rec("2026-10-05T09:00:03+00:00", "plain", 0.40),
        _run_rec("2026-10-12T09:00:00+00:00", "with_lesson", 0.70),
        _run_rec("2026-10-12T09:00:01+00:00", "plain", 0.20),
    ])
    assert _run(readme=readme, benchmarks=corpus).returncode == 0
    text = readme.read_text(encoding="utf-8")
    assert "| 2026-10-05 | 55.0% | 35.0% | 4 |" in text, text
    assert "| 2026-10-12 | 70.0% | 20.0% | 2 |" in text, text
    # Seed rows predate the computed ones and are kept — they are history, not output.
    assert "| 2026-09-21 | 46.1% | 23.3% | 512 |" in text, text
    assert "hand-typed" not in text, "the hand-typed placeholder survived"
    assert text.rstrip().endswith("after"), "content after the END anchor was dropped"


def test_check_exits_1_when_the_block_is_stale(tmp_path):
    """The gate has to be able to go red. A staleness check that cannot fail is a comment.

    This is the mutation check, automated: hand-type a table that the generator did not produce,
    point the generator at a corpus it would never match, and `--check` must exit non-zero.
    """
    corpus, readme = _fixture(tmp_path, [_run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.5),
                                        _run_rec("2026-10-05T09:00:01+00:00", "plain", 0.3)])
    assert _run("--check", readme=readme, benchmarks=corpus).returncode == 1, (
        "--check passed on a README whose block does not match the corpus"
    )
    # And the failing run must not have written anything on the way out.
    assert "| hand-typed |" in readme.read_text(encoding="utf-8"), "--check rewrote the README"


def test_missing_anchor_is_a_hard_error(tmp_path):
    """Silently appending a table outside the markers would orphan it from the prose."""
    corpus, readme = _fixture(tmp_path, [], readme_body="# Title\n\nno anchors here\n")
    result = _run(readme=readme, benchmarks=corpus)
    assert result.returncode == 1
    assert "anchor" in result.stderr, result.stderr


# ── the code path the shipped corpus never reaches ──────────────────────────

def test_aggregation_computes_weekly_rows(tmp_path):
    gen = _load_generator()
    runs = [
        _run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.50),
        _run_rec("2026-10-05T09:00:01+00:00", "with_lesson", 0.60),
        _run_rec("2026-10-05T09:00:02+00:00", "plain", 0.30),
        _run_rec("2026-10-05T09:00:03+00:00", "plain", 0.40),
        _run_rec("2026-10-12T09:00:00+00:00", "with_lesson", 0.70),
        _run_rec("2026-10-12T09:00:00+00:00", "plain", 0.20),
    ]
    rows, unstamped = gen.weekly_rows(runs)
    assert unstamped == 0
    assert rows == [
        ("2026-10-05", 0.55, 0.35, 4),
        ("2026-10-12", 0.70, 0.20, 2),
    ], rows


def test_unstamped_runs_are_counted_not_guessed():
    gen = _load_generator()
    runs = [
        {"condition": "with_lesson", "metrics": {"lesson_hit_rate": 0.5}},   # no run_at
        {"condition": "plain", "metrics": {"lesson_hit_rate": 0.3}},          # no run_at
        _run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.5),
        _run_rec("2026-10-05T09:00:01+00:00", "plain", 0.3),
    ]
    rows, unstamped = gen.weekly_rows(runs)
    assert unstamped == 2, unstamped
    assert rows == [("2026-10-05", 0.5, 0.3, 2)], rows


def test_unparseable_run_at_counts_as_unstamped():
    """A malformed timestamp must not silently become a row dated somewhere arbitrary."""
    gen = _load_generator()
    bad = _run_rec("not-a-date", "with_lesson", 0.5)
    rows, unstamped = gen.weekly_rows([bad])
    assert unstamped == 1
    assert rows == []


def test_a_week_with_only_one_arm_is_not_a_row():
    """Averaging `with_lesson` against an absent `plain` makes the columns incomparable."""
    gen = _load_generator()
    rows, _ = gen.weekly_rows([
        _run_rec("2026-10-05T09:00:00+00:00", "with_lesson", 0.5),
        _run_rec("2026-10-05T09:00:01+00:00", "with_lesson", 0.7),
    ])
    assert rows == [], rows


def test_render_reports_the_unstamped_count():
    """The output has to say what it skipped, or an empty table reads as 'no runs ever happened'."""
    gen = _load_generator()
    block = gen.render_table([], unstamped=1155)
    assert "1155" in block
    assert BEGIN in block and END in block


def test_chart_renders_a_glyph_for_the_lowest_row():
    """A blank cell in the chart reads as a missing measurement, not as the lowest value."""
    gen = _load_generator()
    block = gen.render_table(
        [("2026-10-05", 0.10, 0.05, 2), ("2026-10-12", 0.90, 0.05, 2)], unstamped=0,
    )
    assert "▁" in block, block
    for line in block.splitlines():
        if line.startswith("10.0%") or line.startswith("90.0%"):
            assert line.rstrip().endswith(("▁", "▂", "▃", "▄", "▅", "▆", "▇", "█")), line


# ── the field the whole thing depends on ────────────────────────────────────

def test_benchmark_script_stamps_every_run_with_run_at():
    """The generator's input is a field that a refactor can drop without any test noticing.

    Runs would keep landing, just undated forever — and the README table would keep saying
    "no dated runs yet" while the corpus grew. So the stamp is asserted here, at its source.
    """
    src = BENCH_SCRIPT.read_text(encoding="utf-8")
    assert '"run_at"' in src, (
        "scripts/benchmark_workers_ai.py no longer stamps run_at — the README table has nothing "
        "to aggregate on and will report 'no dated runs yet' forever"
    )
    stamp_line = next((ln for ln in src.splitlines() if '"run_at"' in ln), "")
    assert "datetime.now(timezone.utc)" in stamp_line, (
        f"run_at is not a UTC timestamp at write time: {stamp_line.strip()!r}"
    )
    # And the run dict it belongs to must actually be appended to the artifact.
    assert 'data["runs"].append(run)' in src, "the stamped run is no longer what gets persisted"
