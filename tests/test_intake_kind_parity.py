#!/usr/bin/env python3
"""The set of intake kinds is written down in five places; this holds them equal.

Why this file exists (2026-11-01)
---------------------------------
`proposal` had to be added everywhere at once (#4251), and the sweep that did it found the set had
*already* drifted: `misakanet/server/tools.py` enumerated three kinds where the worker, both scripts
and every doc page described four. `question` was missing from the stdio schema, so a client that
validates a tool's `inputSchema` before calling it could not ask a question through the local server
at all — and nothing in the suite could see it, because each site had its own idea of the list and
the only assertion (`tests/test_intake_kind.py`) covered one of them.

Five readers, one fact:

* `workers/lib/utils.js` — `INTAKE_KINDS`, the worker's allow-list;
* `scripts/intake_kind.py` — `INTAKE_KINDS`, the Python mirror the MCP HTTP server uses;
* `scripts/intake_pipeline.py` — `VALID_KINDS`, the CLI pipeline;
* `misakanet/server/tools.py` — the `kind` enum inside `misakanet_submit_intake`'s `inputSchema`,
  which is the one a *client* enforces;
* `docs/mcp-intake-guide.md` — the table a submitter reads.

This is a text gate over parsed structures, not a grep for a phrase: each reader's own syntax is
parsed (a JS array literal, a Python tuple/set, a schema dict, a markdown table) and the parsed
sets are compared. A comment naming a kind cannot satisfy it, which is the failure mode the
repository has paid for before (`audit_intake_kinds.py`'s grep, #3835).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: The kinds that exist today. Adding one means touching all five readers — that is the point of
#: the test, so the constant lives here and the five sites are *parsed*, never trusted.
EXPECTED = {"missing_lesson", "stale_lesson", "new_lesson_candidate", "question", "proposal"}


def _js_array(path: Path, name: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"const\s+{name}\s*=\s*\[(.*?)\]", text, re.S)
    assert match, f"{path.name} no longer declares `const {name} = [...]` — this gate reads that"
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def _python_literal(path: Path, name: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^{name}\s*=\s*[\(\[\{{](.*?)[\)\]\}}]", text, re.S | re.M)
    assert match, f"{path.name} no longer declares `{name} = (...)` at column 0 — this gate reads that"
    return set(re.findall(r'"([a-z_]+)"', match.group(1)))


def _stdio_schema_enum() -> set[str]:
    """The `kind` enum from the submit_intake tool, parsed — not imported.

    Importing would test the module, not the file the client receives, and the defect this guards
    against was exactly a mismatch between what the file said and what everything else said.
    """
    text = (REPO / "misakanet/server/tools.py").read_text(encoding="utf-8")
    start = text.index('"name": "misakanet_submit_intake"')
    block = text[start:]
    kind_at = block.index('"kind": {')
    enum_at = block.index('"enum": [', kind_at) + len('"enum": [')
    end = block.index("]", enum_at)
    return set(re.findall(r'"([a-z_]+)"', block[enum_at:end]))


def _guide_table() -> set[str]:
    text = (REPO / "docs/mcp-intake-guide.md").read_text(encoding="utf-8")
    start = text.index("## Kind Types")
    section = text[start:]
    end = section.index("\n## ", 3)
    return set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", section[:end], re.M))


def readers() -> dict[str, set[str]]:
    return {
        "workers/lib/utils.js:INTAKE_KINDS": _js_array(REPO / "workers/lib/utils.js", "INTAKE_KINDS"),
        "scripts/intake_kind.py:INTAKE_KINDS": _python_literal(REPO / "scripts/intake_kind.py", "INTAKE_KINDS"),
        "scripts/intake_pipeline.py:VALID_KINDS": _python_literal(REPO / "scripts/intake_pipeline.py", "VALID_KINDS"),
        "misakanet/server/tools.py:submit_intake.kind enum": _stdio_schema_enum(),
        "docs/mcp-intake-guide.md:Kind Types table": _guide_table(),
    }


def test_every_reader_declares_the_same_kinds() -> None:
    found = readers()
    problems = [
        f"{where}: {sorted(kinds)}"
        for where, kinds in found.items()
        if kinds != EXPECTED
    ]
    assert not problems, (
        "the intake kinds disagree with each other (expected "
        f"{sorted(EXPECTED)}):\n  " + "\n  ".join(problems) +
        "\nAdd the kind to every reader in the same change — the stdio enum is the one a client "
        "enforces, so leaving it behind is what made `question` uncallable from a validating client."
    )


def test_the_gate_reads_five_real_readers() -> None:
    """A guard on the guard: a parser that silently matched nothing would pass the check above."""
    found = readers()
    assert len(found) == 5, f"expected five readers, parsed {sorted(found)}"
    for where, kinds in found.items():
        assert kinds, f"{where} parsed as empty — the syntax moved and this gate stopped reading it"


def test_a_missing_kind_in_any_single_reader_is_caught() -> None:
    """The mutation the gate exists for: one reader loses `proposal`, the other four keep it."""
    text = (REPO / "workers/lib/utils.js").read_text(encoding="utf-8")
    arm = re.search(r"const\s+INTAKE_KINDS\s*=\s*\[(.*?)\]", text, re.S).group(1)
    mutated = arm.replace('"proposal", ', "").replace(', "proposal"', "")
    assert mutated != arm, "the mutation did not change the list — this control is not measuring anything"
    # Re-parse the mutated literal through the same regex the gate uses, and show it disagrees.
    parsed = set(re.findall(r'"([a-z_]+)"', mutated))
    assert parsed != EXPECTED, "a list without `proposal` passed the comparison — the gate proves nothing"
    assert EXPECTED - parsed == {"proposal"}


if __name__ == "__main__":  # pragma: no cover - manual run
    sys.exit(0 if all(readers()[k] == EXPECTED for k in readers()) else 1)
