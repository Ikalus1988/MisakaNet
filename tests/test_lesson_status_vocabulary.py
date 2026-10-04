#!/usr/bin/env python3
"""The `status` vocabulary is declared in several places, and they have drifted.

`scripts/lesson_gate.py` is the enforcer: `VALID_STATUS` is the set of values a lesson
may carry. Everything else — the writer's `--status` choices, the gate's own docstring,
`docs/trust-semantics.md`, `lessons/TEMPLATE.md` — is supposed to *restate* that set for
a human reader or a shell user. Restatements are exactly what rots, and it rotted here:

    $ python3 scripts/queue_lesson.py --status deprecated ...
    $ python3 scripts/lesson_gate.py <the file it just wrote>
    FAIL  - status must be one of ['active', 'archived', 'draft', 'published',
           'stale', 'superseded'], got 'deprecated'

The writer exited 0 and the gate exited 1. `deprecated` was only ever in the writer's
`choices=[...]` list; it has never been in `VALID_STATUS`, and no lesson in the corpus
carries it. A contributor who used the CLI exactly as its own `--help` described got a
file the repo's quality gate rejected.

The writer now derives its choices from `VALID_STATUS`, so that half cannot drift. These
tests pin the remaining three restatements, and — more importantly — assert the *direction*
that matters: anything the writer accepts, the gate accepts.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from lesson_gate import VALID_STATUS  # noqa: E402

QUEUE_LESSON = REPO / "scripts" / "queue_lesson.py"
GATE = REPO / "scripts" / "lesson_gate.py"
TRUST_SEMANTICS = REPO / "docs" / "trust-semantics.md"
TEMPLATE = REPO / "lessons" / "TEMPLATE.md"

# The value the writer used to advertise and the gate never accepted. Named explicitly so
# that removing it from the writer produces a test that says *why*, not just a set diff.
RETIRED_WRITER_CHOICE = "deprecated"


def _argparse_choices() -> set[str]:
    """The `--status` values the writer's real CLI accepts, probed through argparse.

    argparse validates `choices` while parsing, which happens before the writer looks at
    `--title` or reads stdin. So an *invalid* value exits 2 with "invalid choice", while a
    *valid* one falls through to the writer's own "--title or --file" complaint and exits
    1. That message also enumerates the accepted set, which is the cheapest way to read
    the real interface instead of re-parsing the source for a literal list.
    """
    probe = subprocess.run(
        [sys.executable, str(QUEUE_LESSON), "--status", "__definitely_not_a_status__"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=REPO,
    )
    assert probe.returncode == 2, (
        "expected argparse to reject an unknown --status value; "
        f"got exit {probe.returncode} with stderr:\n{probe.stderr}"
    )
    match = re.search(r"invalid choice:.*?choose from (.*)$", probe.stderr, re.MULTILINE)
    assert match, f"could not read the accepted set out of argparse's message:\n{probe.stderr}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_the_writer_offers_exactly_the_statuses_the_gate_accepts() -> None:
    """The invariant that was violated: writer choices == gate VALID_STATUS."""
    assert _argparse_choices() == VALID_STATUS


def test_the_writer_no_longer_advertises_a_status_the_gate_rejects() -> None:
    """Named regression: `--status deprecated` must not parse, and the gate agrees."""
    probe = subprocess.run(
        [sys.executable, str(QUEUE_LESSON), "--status", RETIRED_WRITER_CHOICE],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=REPO,
    )
    assert probe.returncode == 2, (
        f"--status {RETIRED_WRITER_CHOICE} parsed successfully (exit {probe.returncode}). "
        f"The writer would then emit a lesson that lesson_gate.py rejects. stderr:\n{probe.stderr}"
    )
    assert RETIRED_WRITER_CHOICE not in VALID_STATUS, (
        f"{RETIRED_WRITER_CHOICE} is now in VALID_STATUS, so this test's premise is stale: "
        "either update the writer's expectation here or drop this test."
    )


def test_the_gate_rejects_what_the_writers_own_help_text_used_to_promise() -> None:
    """The other half of the round trip, asserted on the gate rather than on argparse.

    Directly re-derives the failure from the report, so if the writer is ever made to
    accept a value again, the failure mode is named in a test instead of in a bug report.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import lesson_gate  # noqa: PLC0415

    verdict = lesson_gate.validate_status(RETIRED_WRITER_CHOICE)
    assert verdict, f"the gate would accept {RETIRED_WRITER_CHOICE!r}: {verdict or 'accepted'}"


def test_the_gate_docstring_lists_the_accepted_statuses() -> None:
    """`lesson_gate.py`'s own docstring contradicted `VALID_STATUS` 26 lines below it."""
    docstring = GATE.read_text(encoding="utf-8").split('"""', 2)[1]
    line = next(ln for ln in docstring.splitlines() if "status ∈" in ln)
    listed = set(re.findall(r"\{([^}]*)\}", line)[0].replace(" ", "").split(","))
    assert listed == VALID_STATUS, (
        f"the gate's docstring says {sorted(listed)} but VALID_STATUS is {sorted(VALID_STATUS)}. "
        "Update the docstring and VALID_STATUS together — tests/test_lesson_status_vocabulary.py "
        "fails if only one moves."
    )


def test_trust_semantics_documents_the_statuses_the_gate_enforces() -> None:
    """`docs/trust-semantics.md` advertised `deprecated`, which the gate rejects outright."""
    line = next(
        ln for ln in TRUST_SEMANTICS.read_text(encoding="utf-8").splitlines()
        if ln.startswith("- **Lesson frontmatter**")
    )
    head = line.split(". ", 1)[0]
    listed = set(re.findall(r"`([^`]+)`", head)) - {"status"}
    assert listed == VALID_STATUS, (
        f"docs/trust-semantics.md tells contributors to use {sorted(listed)} but the gate "
        f"enforces {sorted(VALID_STATUS)}. A contributor following the doc writes a lesson "
        "the quality gate refuses."
    )


def test_the_contributor_template_lists_the_statuses_the_gate_enforces() -> None:
    """`lessons/TEMPLATE.md` is what a new contributor copies; it must not over-promise."""
    line = next(
        ln for ln in TEMPLATE.read_text(encoding="utf-8").splitlines()
        if ln.startswith("status:") and "REQUIRED" in ln
    )
    listed = {part.strip() for part in line.split("REQUIRED", 1)[1].lstrip(" —").split("|")}
    assert listed == VALID_STATUS, (
        f"lessons/TEMPLATE.md offers {sorted(listed)} but the gate enforces {sorted(VALID_STATUS)}."
    )
