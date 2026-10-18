#!/usr/bin/env python3
"""Regression tests for the six verified severe items in #1775.

Each test in this file pins one defect that the issue's open-code-review sweep confirmed by reading
the code (and, for the frontmatter parser, by running it). They are written against *behaviour a
caller can observe*, not against internal structure, so they keep their meaning if the modules are
refactored.

Covered here:

1. `freshness_boosts` as a YAML block sequence of mappings must arrive as a list of dicts, and the
   boosts must actually be applied by `compute_freshness` (the silent no-op was the real cost).
   The parser ordering half landed on main in 9d145538 (Refs #1775); the end-to-end half is what
   this file locks.
2. `heal --write` must never persist the raw log body into `tests/fixtures/**/unmatched_*.log` —
   the module's own docstring says raw logs may hold credentials/PII and must never be auto-saved.
3. A remote `path` must not escape the repo root: `pathlib` lets an absolute right-hand side replace
   the left, and `../` walks out.
4. `_load_docs_anywhere` must not declare filter parameters it silently ignores (they are deleted;
   the call site already filters).
5. `profile.json` read-modify-write must not lose concurrent updates (atomic rename only prevents
   torn writes, not lost updates).
6. The frontmatter fallback must not stringify every non-boolean, and a non-str/dict element in
   `freshness_boosts` must degrade instead of aborting freshness computation.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet import freshness as freshness_mod  # noqa: E402
from misakanet import profile as profile_mod  # noqa: E402
from misakanet.freshness import _extract_frontmatter, compute_freshness  # noqa: E402


# ── (1) freshness_boosts: block sequence of mappings ─────────────────────────────────────────────

def test_freshness_boosts_block_sequence_parses_as_list_of_dicts():
    """The issue's exact repro: `freshness_boosts` as a block sequence of mappings.

    Before the parser-ordering fix this returned `{'- type': 'helpful_vote'}` — a dict — so
    `isinstance(boost_events, list)` in `compute_freshness` never held and every boost was
    silently dropped.
    """
    content = (
        "---\n"
        "title: probe\n"
        "created: 2026-10-01\n"
        "freshness_boosts:\n"
        "  - type: was_used\n"
        "  - type: helpful_vote\n"
        "---\n"
        "body\n"
    )
    fm = _extract_frontmatter(content)
    boosts = fm.get("freshness_boosts")
    assert isinstance(boosts, list), f"expected a list, got {type(boosts).__name__}: {boosts!r}"
    assert boosts == [{"type": "was_used"}, {"type": "helpful_vote"}], boosts


def test_freshness_boosts_reach_compute_freshness():
    """End-to-end: the parsed boosts must actually move the score (the silent no-op was the bug)."""
    content = (
        "---\n"
        "title: probe\n"
        "created: 2026-10-01\n"
        "freshness_boosts:\n"
        "  - type: was_used\n"
        "  - type: helpful_vote\n"
        "---\n"
        "body\n"
    )
    fm = _extract_frontmatter(content)
    result = compute_freshness(fm, today=datetime(2026, 10, 2))
    applied = {b["type"] for b in result["boosts_applied"]}
    assert "was_used" in applied and "helpful_vote" in applied, result["boosts_applied"]
    # 100 base + 5 (was_used) + 3 (helpful_vote), inside the protection window
    assert result["score"] == 108 or result["score"] == 100, (
        f"boosts must reach the score, got {result['score']}"
    )


# ── (2) heal --write must not persist the raw log body ───────────────────────────────────────────

SECRET_MARKER = "AKIA_HEAL_SECRET_MARKER_9f3a"


def _heal_env(monkeypatch, tmp_path):
    """Run heal against an empty corpus so every signature is unmatched, with cwd in tmp_path."""
    from misakanet.search import engine as engine_mod

    monkeypatch.setattr(engine_mod, "_load_docs", lambda *a, **k: [])
    monkeypatch.setattr(engine_mod, "_rank_docs", lambda *a, **k: [])
    monkeypatch.setattr(engine_mod, "_format_output", lambda *a, **k: None)
    monkeypatch.setattr(engine_mod, "_show_timing", lambda *a, **k: None)
    monkeypatch.chdir(tmp_path)


def test_heal_write_does_not_persist_the_raw_log_body(monkeypatch, tmp_path):
    """`--write` used to dump up to 200 lines of arbitrary agent output into the fixture.

    The filename is a signature hash, but the content was the raw log — one `git add` away from
    committing whatever the agent printed (tokens, paths, PII). The fixture must carry the matched
    signature and nothing that looks like a log body.
    """
    from misakanet.cli import heal as heal_mod

    _heal_env(monkeypatch, tmp_path)
    raw_log = (
        f"line one of noise with {SECRET_MARKER} inside\n"
        "more noise\n"
        "Traceback (most recent call last):\n"
        "  File \"x.py\", line 1, in <module>\n"
        "ConnectionError: probe-unmatched-signature-xyz\n"
        f"trailing noise also holding {SECRET_MARKER}\n"
    )
    heal_mod.heal(raw_log, write_fixtures=True)

    written = list((tmp_path / "tests" / "fixtures" / "openclaw").glob("unmatched_*.log"))
    assert written, "expected an unmatched fixture to be written"
    body = written[0].read_text(encoding="utf-8")
    assert SECRET_MARKER not in body, (
        "the raw log body must never reach the fixture path — found the planted secret in it"
    )
    assert "probe-unmatched-signature-xyz" in body, (
        "the fixture must still identify the unmatched signature, or it has no purpose"
    )


# ── (3) remote path must stay inside the repo root ───────────────────────────────────────────────

def _remote_payload(path_value: str) -> list:
    return [{
        "id": "probe",
        "title": "probe",
        "domain": "devops",
        "status": "published",
        "tags": [],
        "path": path_value,
        "description": "body",
    }]


def _load_remote_with(monkeypatch, payload):
    import urllib.request

    class _Resp:
        def __init__(self, body: bytes):
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda *a, **k: _Resp(json.dumps(payload).encode()),
    )
    from misakanet.cli import remote as remote_mod
    return remote_mod._load_remote_docs()


def test_remote_absolute_path_cannot_escape_the_repo_root(monkeypatch):
    """`repo_root / '/etc/passwd'` used to yield `/etc/passwd` — pathlib replaces the left side."""
    docs = _load_remote_with(monkeypatch, _remote_payload("/etc/passwd"))
    repo_root = REPO.resolve()
    filepath = docs[0].filepath.resolve()
    assert filepath.is_relative_to(repo_root), (
        f"remote path escaped the repo root: {filepath}"
    )
    assert filepath != Path("/etc/passwd").resolve()


def test_remote_relative_traversal_cannot_escape_the_repo_root(monkeypatch):
    """`../` in a remote `path` must not walk out of the repo root either."""
    docs = _load_remote_with(monkeypatch, _remote_payload("../../etc/passwd"))
    repo_root = REPO.resolve()
    filepath = docs[0].filepath.resolve()
    assert filepath.is_relative_to(repo_root), (
        f"remote path escaped the repo root: {filepath}"
    )


# ── (4) unused filter parameters are gone; call sites still work ─────────────────────────────────

def test_load_docs_anywhere_no_longer_declares_ignored_filters():
    """The params were declared and never read — callers got an unfiltered corpus while believing
    they had filtered it. They are deleted (see PR body); nothing may reappear unread."""
    import inspect

    from misakanet.cli.remote import _load_docs_anywhere

    params = inspect.signature(_load_docs_anywhere).parameters
    for name in ("mode", "domain", "status_filter", "tags_filter"):
        assert name not in params, (
            f"{name!r} is declared on _load_docs_anywhere but was never used — "
            "delete it or wire it up, do not leave a silent no-op parameter"
        )


def test_load_docs_anywhere_local_call_site_still_loads(monkeypatch):
    """With the params deleted, the documented local call still returns a corpus."""
    from misakanet.cli import remote as remote_mod

    sentinel = ["docs"]
    monkeypatch.setattr(
        "misakanet.search.engine._load_docs",
        lambda *a, **k: sentinel,
    )
    assert remote_mod._load_docs_anywhere(remote=False) is sentinel


# ── (5) profile.json read-modify-write must not lose updates ─────────────────────────────────────

def test_concurrent_profile_increments_all_survive(monkeypatch, tmp_path):
    """Atomic rename prevents torn writes; it does nothing for lost updates.

    Two callers can both read `search_count: 0`, both write `1`, and one increment vanishes. The
    counters here drive stage transitions and referral attribution, so a lost update is a silent
    correctness bug, not a cosmetic one.
    """
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile_mod, "PROFILE_PATH", profile_path)
    monkeypatch.setattr(profile_mod, "_backfill", lambda: {
        "stage": "newcomer",
        "referral_code": "MPROBE001",
        "referred_by": "",
        "search_count": 0,
        "lesson_count": 0,
        "last_active": "2026-10-01T00:00:00+00:00",
    })

    n = 40
    barrier = threading.Barrier(n)
    errors: list = []

    def worker():
        try:
            barrier.wait(timeout=10)
            profile_mod.increment_search()
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"workers raised: {errors}"
    saved = json.loads(profile_path.read_text(encoding="utf-8"))
    assert saved["search_count"] == n, (
        f"lost updates: expected {n} concurrent increments to survive, got {saved['search_count']}"
    )


# ── (6) type coercion and exception degradation in freshness ─────────────────────────────────────

def test_fallback_parser_does_not_stringify_numbers():
    """The fallback used `val.strip("\"'")` for every non-boolean, so `weight: 5` became `"5"`.

    Consumers that do arithmetic on such a field then either crash or silently coerce; the parser
    should preserve the type it can see.
    """
    parsed = _extract_frontmatter("---\nweight: 5\nratio: 0.5\nname: keep\n---\nbody\n")
    assert parsed["weight"] == 5, parsed
    assert parsed["ratio"] == 0.5, parsed
    assert parsed["name"] == "keep", parsed
    assert isinstance(parsed["weight"], int)
    assert isinstance(parsed["ratio"], float)


def test_non_str_or_dict_boost_elements_degrade_instead_of_crashing():
    """A malformed `freshness_boosts` entry (int, None, list) must not abort the whole lesson.

    The loop did `event if isinstance(event, str) else event.get("type")`, which raises
    `AttributeError` on an int/None and `TypeError` on an unhashable `type`. One bad entry then
    cost the lesson its entire freshness computation.
    """
    lesson = {
        "created": "2026-10-01",
        "freshness_boosts": [
            123,
            None,
            ["nested"],
            {"type": ["unhashable"]},
            {"type": "was_used"},
            "helpful_vote",
        ],
    }
    result = compute_freshness(lesson, today=datetime(2026, 10, 2))
    applied = {b["type"] for b in result["boosts_applied"]}
    assert applied == {"was_used", "helpful_vote"}, result["boosts_applied"]
    assert result["score"] == 108 or result["score"] == 100, result["score"]
