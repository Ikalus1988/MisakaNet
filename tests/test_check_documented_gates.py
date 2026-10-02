#!/usr/bin/env python3
"""The documented gate set must match the ruleset that enforces it — and be checkable offline.

The live half needs a token, so it is exercised against a saved response rather than the network.
That is deliberate: a test that calls GitHub is a test that goes red when GitHub is unreachable,
and this repository has already spent three rounds learning that a gate people cannot satisfy
gets deleted rather than fixed.

What is pinned here, and why each one is worth a test:

* **The Hard Gates table is the only thing read.** The document also lists advisory checks that
  deliberately do not block a merge, several of them in tables that look identical. A parser
  that wandered past the heading would count those too and invert the document's own point.
* **Table decoration is not part of a context name.** A cell written `**gate**` and a cell
  written `` `gate` `` are the same requirement; a mismatch here would report a divergence that
  does not exist, and the workflow would open an issue every week.
* **The separator row is not a context.** `|---|---|` parses as a cell too.
* **A missing section is a failure, not an empty set.** An empty documented set compared against
  a live one is a divergence — but silently parsing to nothing would make a renamed heading look
  like "the document lists no gates", which is a different and much more confusing message.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_documented_gates", REPO / "scripts" / "check_documented_gates.py"
)
assert _spec and _spec.loader
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

DOC = REPO / "docs" / "ci-gates.md"

RULESET_RESPONSE = {
    "id": 23826057,
    "name": "main: the deterministic gates",
    "enforcement": "active",
    "bypass_actors": [],
    "rules": [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "DCO / Signed-off-by"},
                    {"context": "test (ubuntu-latest, 3.11)"},
                    {"context": "gate"},
                    {"context": "audit"},
                ]
            },
        }
    ],
}


def test_the_real_document_and_the_live_ruleset_agree() -> None:
    """The point of the script, run against the repository as it stands."""
    documented = checker.parse_documented(DOC)
    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    assert sorted(documented) == sorted(live), (
        f"docs/ci-gates.md lists {documented}, ruleset 23826057 requires {live}"
    )


def test_the_document_carries_no_count_of_its_own_gates() -> None:
    """The count must be a property of the table, not a sentence that can drift.

    This is the whole reason the prose was de-numbered. It is one line, it is unambiguous, and
    it fails the moment somebody helpfully writes "the four required checks" above the table —
    which is exactly what happened in this file before the ratchet existed.
    """
    text = DOC.read_text(encoding="utf-8")
    start = text.index(checker.SECTION)
    end = text.find("\n## ", start)
    section = text[start:end if end > 0 else len(text)]
    for line in section.splitlines():
        if line.startswith("|"):
            continue  # the table's own rows are the count, and are allowed to be rows
        for word in ("four", "three", "five", "four ", "三条", "四条"):
            assert word not in line, f"the Hard Gates section states a count: {line.strip()!r}"


def test_advisory_tables_below_the_heading_are_not_counted() -> None:
    """A check that reports but cannot block is not one of the gates."""
    documented = checker.parse_documented(DOC)
    assert "PR Quality Gate" not in documented
    assert "coverage" not in documented
    for context in documented:
        assert "Hard Gates" not in context


def test_a_renamed_or_missing_section_fails_loudly() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "ci-gates.md"
        broken.write_text("# something else\n\nno section here\n", encoding="utf-8")
        try:
            checker.parse_documented(broken)
        except SystemExit as error:
            assert checker.SECTION in str(error)
        else:  # pragma: no cover - only reached if the guard is removed
            raise AssertionError("a missing section must fail, not parse to an empty set")


def test_divergence_is_reported_as_a_difference_not_a_count() -> None:
    """A drift must name what is missing and what is invented, so the fix is obvious."""
    import io

    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    documented = [context for context in live if context != "audit"]
    documented.append("quality-labels")

    stream = io.StringIO()
    code = checker.report(documented, live, stream)
    output = stream.getvalue()
    assert code == 1
    assert "+ audit" in output
    assert "- quality-labels" in output
    # and it must not tell the reader what the count is — they can count the table
    assert "4" not in output.split("Read the ruleset")[0]


def test_agreement_reports_nothing_and_exits_zero() -> None:
    import io

    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    stream = io.StringIO()
    assert checker.report(list(live), live, stream) == 0
    assert stream.getvalue() == ""


def test_the_cli_works_from_a_saved_response_without_a_token() -> None:
    """The offline path is the one the test suite depends on; it must not require credentials."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        saved = Path(tmp) / "ruleset.json"
        saved.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        assert checker.main(["--from-file", str(saved), "--doc", str(DOC), "--quiet"]) == 0

        # ...and a document that has fallen behind exits non-zero
        stale = Path(tmp) / "stale.md"
        text = DOC.read_text(encoding="utf-8")
        stale.write_text(
            text.replace("| **audit** |", "| **removed-gate** |"), encoding="utf-8"
        )
        assert checker.main(["--from-file", str(saved), "--doc", str(stale)]) == 1


def test_a_missing_token_is_an_explicit_error_not_a_pass() -> None:
    """A ratchet that cannot reach GitHub must not report success."""
    for name in ("SHELDON_PAT", "GITHUB_TOKEN"):
        if name in sys.modules:  # pragma: no cover - defensive
            del sys.modules[name]
    saved = {name: None for name in ("SHELDON_PAT", "GITHUB_TOKEN") if name in __import__("os").environ}
    try:
        for name in saved:
            __import__("os").environ.pop(name, None)
        assert checker.main(["--doc", str(DOC)]) == 2
    finally:
        __import__("os").environ.update(saved)
