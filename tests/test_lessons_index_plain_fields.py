#!/usr/bin/env python3
"""The index must carry the optional structured fields (#1783) — and only where a lesson has them.

The defect this file exists for was invisible by construction. `misakanet_search` reads the three
plain fields off the *record*, and there are two sources for that record:

* the **D1 path**, where the row's `frontmatter` column is lifted onto it (#3987/#4013); and
* the **GitHub/KV fallback** (`loadLessons` → `fetchFromGitHub("lessons.json", "data")`), which
  applies **no lift at all** — so the only thing the projection can see is a top-level key on the
  index entry.

`scripts/update_lessons_json.py` picked its fields by hand and never emitted one, so every lesson
lost the three fields on that path. What made it look fine is that `evidence_level` works there
*purely because the generator does emit it* — and the fallback code sitting right beside the plain
fields (`frontmatterField(lesson.frontmatter, …)`) is dead on this path, because no index entry has
a `frontmatter` key at all (measured 0/411). Two neighbouring lines, one working for a reason nobody
had written down, the other inert for the same reason.

These tests are written against the **corpus**, not against a fixture: the expected value is read
back out of the lesson markdown, so a generator that stops emitting the fields, emits the wrong
value, or invents a key for a lesson that has none, all fail. `_PAIRINGS` is counted and the count
asserted, so a broken probe fails loudly instead of passing vacuously.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.lesson_index import canonical_lessons  # noqa: E402
from scripts.update_lessons_json import (  # noqa: E402
    PLAIN_FIELD_KEYS,
    parse_frontmatter,
    plain_fields,
)

LESSONS_DIR = REPO / "lessons"
INDEX = REPO / "data" / "lessons.json"
WORKER = REPO / "workers" / "register-proxy-sw.js"

# The probe must find at least this many lessons actually carrying the fields; below it the
# derivation is not proving anything and the honest outcome is a failure, not a green run.
# (Live corpus 2026-09-25: 15.)
_MIN_CARRIERS = 5


def _index_entries() -> list[dict]:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def _by_id() -> dict[str, dict]:
    return {e["id"]: e for e in _index_entries()}


def _corpus_fields() -> dict[str, dict]:
    """`{lesson id: {field: value}}` for every indexed lesson, read from the markdown.

    Uses the generator's own `parse_frontmatter` on purpose: the contract under test is
    "the index carries what the frontmatter says", and both sides of that sentence must
    agree about what the frontmatter says. `parse_frontmatter` has its own coverage elsewhere.
    """
    out = {}
    for path in canonical_lessons(LESSONS_DIR):
        meta = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        out[path.stem] = plain_fields(meta if isinstance(meta, dict) else {})
    return out


def _worker_field_keys() -> tuple[str, ...]:
    """`PLAIN_FIELD_KEYS` as the worker declares it — parsed, not grepped."""
    src = WORKER.read_text(encoding="utf-8")
    m = re.search(r"const\s+PLAIN_FIELD_KEYS\s*=\s*\[([^\]]*)\]", src)
    assert m, "workers/register-proxy-sw.js no longer declares PLAIN_FIELD_KEYS"
    return tuple(re.findall(r'"([^"]+)"', m.group(1)))


def test_the_two_field_tables_are_the_same_three_fields():
    """The generator and the worker must name the same fields, in the same order.

    This is the wiring, and wiring is the part that has no test until it has this one: every
    assertion about "the field is populated" is satisfied by a generator that emits a key the
    worker never reads (or the reverse) — the value is present in the file and absent from the
    response, and both sides look correct in isolation.
    """
    assert PLAIN_FIELD_KEYS == _worker_field_keys()


def test_no_lesson_without_the_fields_gains_a_key():
    """Additivity: a lesson with no structured fields must gain no key, not an empty one.

    `plainField()` in the worker turns "" / null / a nested object into "absent", so an empty
    string here would not change a response — but it *would* make the index claim a field the
    lesson does not have, and it is the difference between "the generator copied a value" and
    "the generator wrote a placeholder". The index is a public artifact; a placeholder reads as
    content to anything that is not the worker.
    """
    entries, corpus = _by_id(), _corpus_fields()
    offenders = []
    for lesson_id, fields in corpus.items():
        if fields:
            continue
        entry = entries.get(lesson_id)
        if entry is None:
            continue
        present = sorted(k for k in PLAIN_FIELD_KEYS if k in entry)
        if present:
            offenders.append(f"{lesson_id}: {present}")
    assert not offenders, (
        "these index entries carry a structured-field key for a lesson whose frontmatter has "
        f"no usable value: {offenders}"
    )


def test_every_lesson_that_carries_the_fields_carries_them_in_the_index():
    """The real gate: the value in the corpus must survive into `data/lessons.json` verbatim.

    A failure here means the GitHub/KV fallback path answers without the fields for a lesson
    that has them — which is the published state of the corpus, not a hypothetical.
    """
    entries, corpus = _by_id(), _corpus_fields()
    carriers = {k: v for k, v in corpus.items() if v}
    assert len(carriers) >= _MIN_CARRIERS, (
        f"the probe found only {len(carriers)} lessons carrying the structured fields "
        f"(expected >= {_MIN_CARRIERS}); the corpus read is broken, so a green result here "
        "would not mean anything"
    )

    missing, wrong = [], []
    for lesson_id, fields in sorted(carriers.items()):
        entry = entries.get(lesson_id)
        assert entry is not None, f"{lesson_id} carries structured fields but is not in the index"
        for key, value in sorted(fields.items()):
            if key not in entry:
                missing.append(f"{lesson_id}.{key}")
            elif entry[key] != value:
                wrong.append(f"{lesson_id}.{key}: index={entry[key]!r} frontmatter={value!r}")
    assert not missing, (
        "the index dropped structured fields the lesson's frontmatter carries, so the "
        f"GitHub/KV fallback cannot serve them: {missing}"
    )
    assert not wrong, f"the index changed a structured value on the way in: {wrong}"


def test_the_index_entry_keys_are_exactly_what_a_field_less_lesson_should_have():
    """No fourth field sneaks in under the same "optional" umbrella.

    `plain_fields` is a whitelist over `PLAIN_FIELD_KEYS`, so this asserts the whitelist is
    actually applied: an entry must not carry a structured-field-looking key the worker does
    not read. `triggers` (plural, the older structured-intent object) is a different field and
    is expected — this pins that the two are not conflated.
    """
    forbidden = {"verified_against", "re_verify_after", "freshness_boosts"}
    for entry in _index_entries():
        clash = forbidden & set(entry)
        assert not clash, f"{entry['id']} carries {sorted(clash)} — not part of the contract"
    assert "triggers" in _index_entries()[0], (
        "the plural `triggers` field disappeared from the index — it is a different field from "
        "the singular `trigger`, and this test exists to keep them distinct"
    )


@pytest.mark.parametrize("key", sorted(PLAIN_FIELD_KEYS))
def test_the_generator_only_emits_a_non_empty_string(key):
    """The usable-value rule, stated once per field and checked against the whole corpus."""
    for entry in _index_entries():
        if key not in entry:
            continue
        value = entry[key]
        assert isinstance(value, str) and value.strip(), (
            f"{entry['id']}.{key} is {value!r}; the worker treats that as absent, so the index "
            "is carrying a placeholder instead of a value"
        )


def test_the_generator_itself_emits_the_fields(tmp_path, monkeypatch):
    """Run the real generator and check its output — the committed file is not the subject.

    Every assertion above compares `data/lessons.json` against the corpus, and all of them stay
    green if the emission line is deleted from the generator and the stale file is left in place.
    That is the same shape as the #1822 `--kv-only` early return and the #2183 swallowed exit code:
    the *function* is covered, the *wiring into the artifact* is not. So this one drives the real
    `main()` over the real corpus and reads what it wrote.

    It doubles as a staleness gate: the committed index must equal a fresh generation from the
    current corpus, which is what `.github/workflows/update-lessons.yml` produces daily.
    """
    import scripts.update_lessons_json as gen

    out = tmp_path / "lessons.json"
    monkeypatch.setattr(gen, "OUTPUT", out)
    monkeypatch.setattr(gen, "refresh_lesson_count_markers", lambda _count: None)
    gen.main()

    fresh = {e["id"]: e for e in json.loads(out.read_text(encoding="utf-8"))}
    carriers = {k: v for k, v in _corpus_fields().items() if v}
    assert len(carriers) >= _MIN_CARRIERS, "probe broken — see the comment on _MIN_CARRIERS"

    missing = [
        f"{lesson_id}.{key}"
        for lesson_id, fields in sorted(carriers.items())
        for key in sorted(fields)
        if key not in fresh.get(lesson_id, {})
    ]
    assert not missing, (
        "a fresh run of scripts/update_lessons_json.py does not emit the structured fields, so "
        f"the index in the repository is the only reason the other tests pass: {missing}"
    )

    committed = _by_id()
    assert fresh == committed, (
        "data/lessons.json is not what the generator produces from the current corpus — "
        "run `python3 scripts/update_lessons_json.py`"
    )
