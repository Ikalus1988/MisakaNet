#!/usr/bin/env python3
"""FR3 over the published surfaces *outside* the report corpus (#3011).

`check_field_reports.py` began with a corpus of exactly one directory while its FR3 rule is about
*published* text, and the gap was invisible in its own output: three handoffs under `docs/maintainer/`
had carried an unredacted home path since August, and no CI run could see them — both PRs and pushes
pass `--base`, and the whole-corpus mode ran only on a `workflow_dispatch` that had never been
triggered (measured: `total_count = 0`).

Both directions are pinned here. A rule that cannot go red and a rule that goes red on the corpus's
own redaction shorthand are the same bug from opposite ends, and this repository has shipped both: a
gate that could never fail (#2045) and, in the first draft of this one, 68 findings that were all
`/home/.git-credentials` or `C:\\Users\\YourUsername`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_field_reports.py"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_field_reports", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Registering it is not optional: `@dataclass` resolves annotations through `sys.modules`.
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


def _scan(tmp_path, monkeypatch, relative: str, text: str, changed=None, strict_all=True):
    """Run the published-surface pass over a one-file temp surface, hermetically."""
    root = tmp_path / "surface"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(CHECKER, "PUBLISHED_SURFACES", (root,))
    monkeypatch.setattr(CHECKER, "_GENERATED_UNDER_PUBLISHED", ())
    return CHECKER.collect_published_home_paths(
        REPO / "docs" / "field-reports", changed, strict_all=strict_all)


# The shapes that made the first run report 117 findings of which 68 were noise. Every one of these is
# already a redaction, and a gate that fires on them trains its reader to ignore it.
NOT_A_LEAK = [
    r"C:\Users\YourUsername\.config",
    "/home/.git-credentials",
    "/home/your_username/.ssh/id_rsa",
    r"C:\Users\REPLACE_ME\repo",
    "/mnt/c/Users/...",
    "/home/<user>/MisakaNet",
    "/Users/example/projects",
]

# Real accounts the corpus actually contained.
IS_A_LEAK = [
    "/home/hp/.local/bin/gh",
    r"C:\Users\hp\AppData\Local",
    "/Users/hp/Library/Caches",
    "/home/eric_jia/MisakaNet",
    "/mnt/c/Users/Eric Jia/AGENTS.md",
    r"C:\Users\shubh\automaton_zero\server.js",
]


@pytest.mark.parametrize("text", IS_A_LEAK)
def test_a_leak_outside_the_report_corpus_goes_red(tmp_path, monkeypatch, text):
    gating, legacy, scanned = _scan(tmp_path, monkeypatch,
                                    "maintainer/handoff-2026-10-05.md", f"machine: `{text}`\n")
    assert scanned == 1
    assert [f.rule for f in gating] == ["FR3-home-path"], f"{text} did not gate:\n{gating}"
    assert not legacy


@pytest.mark.parametrize("text", NOT_A_LEAK)
def test_a_redaction_is_not_a_leak(tmp_path, monkeypatch, text):
    gating, legacy, scanned = _scan(tmp_path, monkeypatch,
                                    "maintainer/handoff-2026-10-05.md", f"machine: `{text}`\n")
    assert scanned == 1
    assert not gating, f"{text} was reported as a leak:\n{gating}"
    assert not legacy


def test_an_untouched_file_reports_legacy_rather_than_gating(tmp_path, monkeypatch):
    """The #1976/#1920 principle, kept: pre-existing debt must not hold an unrelated pull request."""
    gating, legacy, scanned = _scan(tmp_path, monkeypatch, "maintainer/handoff-2026-10-05.md",
                                    "machine: `/home/hp/x`\n", changed=set(), strict_all=False)
    assert scanned == 1
    assert not gating
    assert [f.rule for f in legacy] == ["FR3-home-path"]


def test_the_report_corpus_is_not_reported_twice(tmp_path, monkeypatch):
    """One leak, one finding: `collect` already reads the corpus with the full rule set."""
    root = tmp_path / "surface"
    corpus = root / "field-reports"
    corpus.mkdir(parents=True)
    (corpus / "leaky.md").write_text("machine: `/home/hp/x`\n", encoding="utf-8")
    monkeypatch.setattr(CHECKER, "PUBLISHED_SURFACES", (root,))
    monkeypatch.setattr(CHECKER, "_GENERATED_UNDER_PUBLISHED", ())
    assert CHECKER.collect_published_home_paths(corpus, None, strict_all=True) == ([], [], 0)


def test_the_hardcoded_generated_globs_still_match_gitattributes():
    """The list is duplicated on purpose (the checker must not need `.gitattributes` at runtime), so
    the duplication is pinned: a `linguist-generated` path added under `docs/` without a matching
    entry here would be scanned as if a human had written it."""
    patterns = []
    for line in (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "linguist-generated" not in stripped:
            continue
        pattern = stripped.split()[0]
        if pattern.startswith("docs/"):
            patterns.append(pattern)
    assert patterns, "no generated docs patterns found — has .gitattributes moved?"
    for pattern in patterns:
        prefix = pattern.split("*")[0]
        assert any(prefix.startswith(g) or g.startswith(prefix)
                   for g in CHECKER._GENERATED_UNDER_PUBLISHED), (
            f"{pattern} is marked linguist-generated but no entry in _GENERATED_UNDER_PUBLISHED "
            f"covers it: {CHECKER._GENERATED_UNDER_PUBLISHED}")
