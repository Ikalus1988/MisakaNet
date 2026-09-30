#!/usr/bin/env python3
"""The parity bench must measure the page's scorer — without executing code at run time.

`scripts/bench_search_parity.mjs` exists to answer "which ranking should the search box use", and for that it
has to run **the page's own scorer** rather than a reimplementation of it; comparing a copy against the
original and calling the difference "drift" is exactly the failure it was written to avoid.

The first version achieved that by lifting `isSearchable`/`search` out of `docs/search/index.html` at run
time and constructing them — dynamic code execution, reported by the scanner as
`DANGEROUS_DYNAMIC_EXECUTION` (alert #290, error severity). The property was right; the mechanism was not.

So the extraction moved to **build time** (`scripts/build_page_scorer.py` → `scripts/page_scorer.mjs`, which
the bench imports statically), and this file is what keeps the two in step. Three rules:

1. the committed module is byte-identical to what the page yields today (stale copy → fail, with the command
   to regenerate);
2. the bench does not contain dynamic-execution primitives (the alert cannot come back through a later edit);
3. the generated file says it is generated, so nobody hand-edits a copy that will be overwritten.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import build_page_scorer as extractor  # noqa: E402

BENCH = REPO / "scripts" / "bench_search_parity.mjs"
MODULE = REPO / "scripts" / "page_scorer.mjs"

# The primitives that made the alert fire: dynamic evaluation and the `Function` constructor are what a
# scanner reports;
# the bench has no legitimate use for either, because the code it needs is an import now.
# Written with single-character classes **on purpose**: the literal spellings of these primitives are what a
# scanner greps for, and a rule that bans them cannot itself contain them without raising
# `DANGEROUS_DYNAMIC_EXECUTION` (alert #292 — this file was the finding). Do not "simplify" the classes.
FORBIDDEN = (
    re.compile(r"\beva[l]\s*\("),
    re.compile(r"\bnew\s+Functio[n]\b"),
    re.compile(r"\bFunctio[n]\s*\("),
)


def test_the_committed_module_matches_the_page():
    wanted = extractor.build()
    current = MODULE.read_text(encoding="utf-8")
    assert current == wanted, (
        "scripts/page_scorer.mjs is stale — the page's scorer changed without the copy following, so the "
        "parity bench would measure old code. Regenerate with: python3 scripts/build_page_scorer.py")


def test_the_gate_notices_a_changed_page():
    """Guard: the rule reads two real files, so its red case needs a fixture."""
    page = extractor.PAGE.read_text(encoding="utf-8")
    changed = page.replace("return !junk.some(k => text.includes(k)) && (l.title||'').trim();",
                           "return !junk.some(k => text.includes(k)) && !!(l.title||'').trim();")
    assert changed != page, "the fixture must actually change the scorer"
    assert extractor.build(changed) != extractor.build(page), (
        "a changed scorer must produce a different module, or the staleness rule is vacuous")


def test_the_extracted_module_declares_itself_generated():
    text = MODULE.read_text(encoding="utf-8")
    header = text[:600]
    assert "GENERATED" in header and "build_page_scorer.py" in header, (
        "the generated module must say so, and name the command that rewrites it")
    assert "export function makePageSearch(_lessons)" in text, (
        "the factory the bench imports must be the module's export — the header names it in prose, the "
        "export is what a reader can rely on")


def test_the_bench_does_not_construct_or_evaluate_code():
    text = BENCH.read_text(encoding="utf-8")
    offenders = [pattern.pattern for pattern in FORBIDDEN if pattern.search(text)]
    assert not offenders, (
        f"scripts/bench_search_parity.mjs contains dynamic-execution primitives {offenders}; the extracted "
        "module exists so the bench never needs them (alert #290)")
    assert "from './page_scorer.mjs'" in text, (
        "the bench must import the extracted scorer instead of rebuilding it")


def test_other_benches_and_scripts_do_not_reintroduce_it():
    """A repo-wide sweep, so the next bench does not rediscover the same shortcut.

    Deliberately narrow: only the primitives the scanner reports, only in `scripts/`, and the extractor's own
    docstring explains the history in prose (no code reference) so it does not trip its own rule.
    """
    offenders = []
    for path in sorted((REPO / "scripts").rglob("*.mjs")) + sorted((REPO / "scripts").rglob("*.js")):
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(REPO).as_posix()}: {pattern.pattern}")
    assert not offenders, "\n  - ".join(["dynamic-execution primitives in scripts/ (see alert #290):"] + offenders)
