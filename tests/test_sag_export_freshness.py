#!/usr/bin/env python3
"""Building the local search index must not quietly produce a worse one (issue #2185).

`data/sag.db` is gitignored, so every fresh clone builds it — from `data/okf/lessons.jsonl`, a *tracked*
file with **no writer in CI**. Measured 2026-09-25: it was last written 2026-07-07 and covered 179 of
458 lessons, while `misakanet/server/handlers/search.py` prefers SAG over the complete BM25 path. So a
new contributor who followed the server's own hint got an index covering 39% of the corpus, preferred
over the one that covers all of it — the documented remedy made recall worse than doing nothing, and
nothing said so.

Two halves, both pinned here:

* `build_sag_index.py` now *measures* the export against the corpus and says so when the two disagree;
* the hint names both steps, in order, because the second one reads what the first one writes.
"""
from __future__ import annotations

import json

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import scripts.build_sag_index as sag  # noqa: E402
from scripts.build_sag_index import (  # noqa: E402
    COVERAGE_FLOOR,
    corpus_lesson_files,
    export_coverage,
    warn_if_export_is_stale,
)

sys.path.insert(0, str(REPO / "misakanet"))
from misakanet.server.handlers import search as search_mod  # noqa: E402


def _records_for(paths) -> list[dict]:
    return [{"path": p} for p in paths]


# ── the measurement itself ──────────────────────────────────────────────────────────
def test_the_corpus_denominator_excludes_readmes():
    """A fresh export skips READMEs and templates; counting them would make every export look stale."""
    corpus = corpus_lesson_files()
    assert len(corpus) > 100, f"only {len(corpus)} lesson files found — is lessons/ readable?"
    assert not any(p.endswith("/README.md") for p in corpus), sorted(corpus)[:3]


def test_a_complete_export_does_not_warn():
    corpus = corpus_lesson_files()
    records = _records_for(corpus)
    assert export_coverage(records) == (len(corpus), len(corpus))
    assert warn_if_export_is_stale(records) is False


def test_the_committed_export_of_2026_07_07_would_have_been_flagged():
    """The real shape of the defect, as a fixture: 194 rows naming 179 corpus files (39%).

    Deliberately synthetic — asserting on the *committed* file would make this test go red the day
    somebody fixes it, which is the wrong way round.
    """
    corpus = sorted(corpus_lesson_files())
    stale = _records_for(corpus[: int(len(corpus) * 0.39)])
    covered, total = export_coverage(stale)
    assert covered == int(total * 0.39)
    assert warn_if_export_is_stale(stale) is True


def test_the_threshold_sits_between_the_two_measured_populations():
    """Measured 2026-09-25: a fresh export covers 91% of the corpus, the committed one covered 39%.

    Pinned loosely on purpose — the exact ratios move as lessons are added — but a floor outside this
    range is either useless (catches nothing) or a false alarm on a healthy checkout.
    """
    assert 0.5 <= COVERAGE_FLOOR <= 0.95, (
        f"COVERAGE_FLOOR={COVERAGE_FLOOR} is outside the measured gap (0.39 stale vs 0.91 fresh)"
    )


@pytest.mark.parametrize("ratio,expected", [(0.79, True), (0.81, False), (1.0, False)])
def test_the_boundary_behaves(ratio, expected):
    corpus = sorted(corpus_lesson_files())
    records = _records_for(corpus[: int(len(corpus) * ratio)])
    assert warn_if_export_is_stale(records) is expected


def test_an_unknown_corpus_does_not_warn(capsys, monkeypatch, tmp_path):
    """Outside a checkout (a bare `data/okf/` bundle, say) there is nothing to compare against, and a
    warning that cannot be acted on is noise."""
    monkeypatch.setattr(sag, "LESSONS_DIR", tmp_path / "no-such-corpus")
    assert sag.corpus_lesson_files() == set()
    assert export_coverage([{"path": "lessons/x.md"}]) == (0, 0)
    assert warn_if_export_is_stale([{"path": "lessons/x.md"}]) is False
    assert capsys.readouterr().out == ""


def test_the_warning_names_the_cause_and_the_command(capsys):
    corpus = sorted(corpus_lesson_files())
    warn_if_export_is_stale(_records_for(corpus[:10]))
    out = capsys.readouterr().out
    assert "export_okf.py" in out, out
    assert "#2185" in out, out
    assert f"{len(corpus)} lessons" in out or "of" in out, out


# ── the wiring: `build_index` is what a person actually runs ───────────────────────
def _write_export(directory: Path, paths: list[str]) -> Path:
    okf = directory / "okf"
    okf.mkdir(parents=True, exist_ok=True)
    (okf / "lessons.jsonl").write_text(
        "\n".join(json.dumps({"path": p, "title": p, "status": "published"}) for p in paths) + "\n",
        encoding="utf-8",
    )
    return okf


def test_building_from_a_stale_export_warns_at_the_point_of_use(tmp_path, capsys):
    """Every other test here calls `warn_if_export_is_stale` directly, so deleting the call from
    `build_index` left the suite green — the function was tested, the wiring was not."""
    corpus = sorted(corpus_lesson_files())
    okf = _write_export(tmp_path, corpus[:10])
    built = sag.build_index(okf, tmp_path / "sag.db")
    out = capsys.readouterr().out
    assert built == 10, out
    assert "looks stale" in out, out
    assert "export_okf.py" in out, out


def test_building_from_a_complete_export_stays_quiet(tmp_path, capsys):
    """The positive control: a healthy checkout must not print a warning, or the warning is noise.

    `build_index` is silent on success — the "index built" line belongs to `main()` — so this asserts
    the absence of the warning plus the record count it returns.
    """
    corpus = sorted(corpus_lesson_files())
    okf = _write_export(tmp_path, corpus)
    built = sag.build_index(okf, tmp_path / "sag.db")
    out = capsys.readouterr().out
    assert built == len(corpus), out
    assert out == "", out


# ── the hint the server gives when no index exists ──────────────────────────────────
def _no_index_hint(monkeypatch) -> dict:
    """Drive the real `handle_search` down its no-engine path.

    Behavioural rather than a search for the string: the first version of a test like this in this
    repository matched its own explanatory comment.
    """
    monkeypatch.setattr(search_mod, "_fallback_search", lambda *a, **k: None)
    state = (False, None, False, None)      # HAS_SAG, SAG_DB, HAS_BM25, sag_search
    response = search_mod.handle_search({"query": "anything", "top": 3}, search_state=state)
    assert response.get("error", "").startswith("Search engine unavailable"), response
    return response


def test_the_hint_tells_the_user_to_refresh_the_export_first(monkeypatch):
    action = _no_index_hint(monkeypatch)["action"]
    assert "export_okf.py" in action, (
        "the hint names only build_sag_index.py, which reads a tracked export that nothing in CI "
        f"regenerates — following it builds a partial index (#2185): {action!r}"
    )
    assert "build_sag_index.py" in action, action
    assert action.index("export_okf.py") < action.index("build_sag_index.py"), (
        "the order matters: the second command reads what the first one writes"
    )
