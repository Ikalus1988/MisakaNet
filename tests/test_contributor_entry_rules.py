#!/usr/bin/env python3
r"""A rule the gate enforces but the contributor never reads is a rule eight people learn by failing.

Eight consecutive contributions from one author were blocked by the same line — `summary_plain`
over 120 chars (138 / 123 / 136 / 124 / 125 / 129 / 172 / 145), and each one was blocked by a
layer in front of it: the PR sat in a conflicted state, so CI never ran the gate, and "no failing
check" was read as "it passed". The limits were never wrong. They were **invisible**: nothing a
contributor reads before their first push said they existed.

What this holds in place

1. **The numbers in the contributor-facing docs are the numbers in the code.** `summary_plain` 120,
   `trigger` 160, `verify` 200, title 4–120 — every one read out of `scripts/lesson_gate.py`, not
   copied into this file. A limit that changes in the gate without the docs changing fails here.
2. **`lessons/TEMPLATE.md` states each limit** on the field it belongs to.
3. **The PR template carries them too**, since that is what a contributor reads before the gate
   ever runs. The eight failures were all at PR time.
4. **The gate's domain error names the file that is actually read** (`data/domains.json`). It used to
   say "docs/domains/ or existing lessons" — a list the gate stopped consulting, so it sent people to
   check a path that cannot answer the question.

This is a documentation-drift gate, so it is deliberately narrow: it does not judge whether the
prose is *good*, only that a contributor can find the constraint they will be held to.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "lesson_gate.py"
TEMPLATE = REPO / "lessons" / "TEMPLATE.md"
PR_TEMPLATE = REPO / ".github" / "PULL_REQUEST_TEMPLATE.md"
DOMAIN_VOCAB = REPO / "data" / "domains.json"


def _gate_source() -> str:
    return GATE.read_text(encoding="utf-8")


def _limits() -> dict[str, int]:
    """`STRUCTURED_FIELD_LIMITS`, read out of the gate the way the gate would parse it."""
    src = _gate_source()
    block = re.search(r"^STRUCTURED_FIELD_LIMITS\s*=\s*\{(.*?)\}", src, re.S | re.M)
    assert block, "STRUCTURED_FIELD_LIMITS is gone; this test needs to know where the limits moved"
    return {k: int(v) for k, v in re.findall(r'"(\w+)":\s*(\d+)', block.group(1))}


def _title_bounds() -> tuple[int, int]:
    src = _gate_source()
    lo = re.search(r"^MIN_TITLE_CHARS\s*=\s*(\d+)", src, re.M)
    hi = re.search(r"^MAX_TITLE_CHARS\s*=\s*(\d+)", src, re.M)
    assert lo and hi, "MIN_TITLE_CHARS / MAX_TITLE_CHARS are gone; update this test"
    return int(lo.group(1)), int(hi.group(1))


# ── 1. the documented numbers are the enforced numbers ──────────────────────────────

def test_pr_template_states_the_structured_field_limits():
    """The eight lessons that were rejected were rejected at PR time, before the gate ever ran."""
    text = PR_TEMPLATE.read_text(encoding="utf-8")
    missing = [
        f"`{field}` ≤ {limit}"
        for field, limit in _limits().items()
        if not re.search(rf"`{field}`\s*\|[^|\n]*?≤\s*\*?\*?{limit}\b", text)
    ]
    assert not missing, (
        f"the PR template does not state: {', '.join(missing)} — those are enforced by "
        "scripts/lesson_gate.py, and a contributor who cannot see them only finds out by failing"
    )


def test_pr_template_states_the_title_bounds():
    lo, hi = _title_bounds()
    text = PR_TEMPLATE.read_text(encoding="utf-8")
    assert re.search(rf"`title`\s*\|[^|\n]*?{lo}\s*[–—-]\s*{hi}\b", text), (
        f"the PR template must state the title range {lo}-{hi}, which lesson_gate.py enforces"
    )


def test_template_states_the_structured_field_limits():
    """`lessons/TEMPLATE.md` is the file a contributor copies, so the limit belongs on the field."""
    text = TEMPLATE.read_text(encoding="utf-8")
    missing = [
        f"{field} ≤ {limit}"
        for field, limit in _limits().items()
        if not re.search(rf"{field}[^\n]*?<=\s*{limit}\b", text)
    ]
    assert not missing, f"lessons/TEMPLATE.md does not state: {', '.join(missing)}"


def test_template_states_the_title_range():
    lo, hi = _title_bounds()
    text = TEMPLATE.read_text(encoding="utf-8")
    assert re.search(rf"`title`[^\n]*?{lo}-{hi}\b", text) or re.search(
        rf"{lo}-{hi}\s*chars", text
    ), f"lessons/TEMPLATE.md must state the title range {lo}-{hi}"


# ── 2. the domain rule points at the file that is actually read ─────────────────────

def test_the_domain_error_names_the_vocabulary_the_gate_reads():
    """The old text sent contributors to `docs/domains/`, which the gate stopped consulting."""
    src = _gate_source()
    # The message is an implicitly-concatenated f-string spanning several lines, so the whole
    # `errors.append(...)` statement is read — matching one line would only ever see the first
    # fragment and would fail for a reason that has nothing to do with the message.
    statement = re.search(r"errors\.append\(\s*f?\"domain \{domain!r\}.*?\n\s*\)", src, re.S)
    assert statement, "the domain error message is gone or renamed; update this test to find it"
    body = statement.group(0)

    assert "DOMAIN_VOCAB.relative_to(REPO)" in body, (
        "the domain error must name the vocabulary file by reading DOMAIN_VOCAB, so the message "
        "cannot go stale when that file moves — an error that points elsewhere is worse than none"
    )
    assert "docs/domains/ or existing lessons" not in body, (
        "the stale wording is back: the vocabulary is data/domains.json, not docs/domains/ and not "
        "whatever the existing lessons happen to use"
    )


def test_the_named_domain_file_is_the_one_the_gate_reads():
    """Guards the assertion above from becoming decorative: the path must really be the source."""
    src = _gate_source()
    assert f'DOMAIN_VOCAB = REPO / "data" / "domains.json"' in src, (
        "DOMAIN_VOCAB moved; the message and this test must be updated together"
    )
    vocab = json.loads(DOMAIN_VOCAB.read_text(encoding="utf-8"))
    assert vocab.get("canonical"), "data/domains.json no longer carries a canonical list"