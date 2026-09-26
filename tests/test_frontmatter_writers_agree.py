#!/usr/bin/env python3
"""Two writers of the same thing must agree, and a parser must read what it claims to.

Both defects below were found on 2026-09-21 while converging the backlog (#1922, #1775), and both
have the same shape: a function that *looks* like it works, and no test that could have noticed.

* `scripts/queue_lesson.py` had **two** builders for a lesson's frontmatter block. `_render_lesson`
  emitted `---` at column 0; `write_lesson`'s own copy emitted `" ---"` with a leading space, which no
  frontmatter parser accepts. The tool therefore *created* lessons whose frontmatter could not be read,
  and the gate reported `missing required field: title/domain/tags` for fields that were right there.
  That is the identical failure signature that blocked five lesson PRs the same day — so the tool and
  the contributors were producing the same broken shape, and only the contributors were being told off
  for it.
* `misakanet/freshness.py::_extract_frontmatter`'s YAML fallback matched indented `- key: value` with
  its "nested object" rule, so a list of mappings came back as `{"- type": ...}` — a dict. Every
  `isinstance(value, list)` check downstream was dead, which is how `freshness_boosts` became a silent
  no-op. The same ordering bug also wrote an empty list over a freshly parsed nested map.

The tests are deliberately written against *behaviour* (what a caller receives), not against the
regexes, so they keep their meaning if the parser is ever replaced by PyYAML.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from misakanet.freshness import _extract_frontmatter  # noqa: E402



def _no_git(*args, **kwargs):
    """Stand in for `git add/commit/push`: report success without touching a repository.

    "Report success" is the whole problem: `write_lesson`'s success branch rebuilds the public index
    (`from update_lessons_json import main`), so a stub that returns `returncode = 0` sends the code
    down the *production* path with the repository as its output directory. Pair this with
    `_no_index_rebuild` — never with the real rebuild.
    """
    import subprocess

    class _Done:
        returncode = 0
        stdout = ""
        stderr = ""

    return _Done()


def _no_index_rebuild(monkeypatch):
    """Stop `write_lesson` from rebuilding `data/lessons.json` after its (stubbed) successful push.

    Measured 2026-09-26: without this, running the suite rewrote the checkout's own index from
    `lessons/` (411 → 415 entries as soon as a pull request added a lesson) **and** every published
    count surface, because `update_lessons_json.main()` finishes by refreshing them. The next test to
    read the index then failed — `test_lesson_page_generator::test_repo_pages_match_the_index`, on a
    branch that had touched no page at all.

    `tests/conftest.py` redirects `MISAKANET_LESSONS_INDEX` so the write cannot reach the repository
    even if this stub is removed; this keeps the test from doing pointless work and from depending on
    that redirection to be honest about what it covers.
    """
    import types

    monkeypatch.setitem(sys.modules, "update_lessons_json",
                        types.SimpleNamespace(main=lambda *a, **k: None))


# ── #1922: the lesson writer's frontmatter must be readable ────────────────────────────────────────

def _parse_block(text: str) -> dict:
    """Read a written lesson's frontmatter the way the gate does: `---` on both fences, column 0.

    Both fences are checked, and by the same shape the repository's own parsers use. An earlier
    version of this helper split on the *opening* fence, which passed even when the *closing* one
    was written as ` ---` — the exact defect being tested, so the gate would not have bitten.
    """
    import re

    import yaml

    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    assert match, (
        "the frontmatter must be delimited by `---` at column 0 on both fences; a leading space on "
        "either one makes the whole block invisible to every parser, including the lesson gate\n"
        + text[:160]
    )
    data = yaml.safe_load(match.group(1))
    assert isinstance(data, dict), f"frontmatter did not parse as a mapping: {match.group(1)[:120]!r}"
    return data


def test_write_lesson_writes_frontmatter_that_parses(tmp_path, monkeypatch):
    """The file `write_lesson` produces must carry readable title/domain/tags (#1922).

    This is the half of the defect that actually hurt: the tool wrote lessons that the repository's
    own gate rejected, and the report blamed fields that were present in the file.
    """
    import scripts.queue_lesson as q

    monkeypatch.setattr(q, "LESSONS_DIR", tmp_path)
    monkeypatch.setattr(q, "_update_index", lambda *a, **k: None)
    monkeypatch.setattr(q, "_print_suggested_git", lambda *a, **k: None)
    # `write_lesson` finishes by committing and pushing for real. Stub the *process* rather than
    # the callers: a test that can reach the network is a test that behaves differently in CI.
    monkeypatch.setattr(q.subprocess, "run", _no_git)
    _no_index_rebuild(monkeypatch)

    ok = q.write_lesson(
        "Frontmatter fence probe",
        "devops",
        ["probe"],
        "## Problem\n\nx\n\n## Root Cause\n\ny\n\n## Solution\n\nz\n\n## Verification\n\nw\n",
        source="test",
    )
    assert ok, "write_lesson reported failure"

    written = list(tmp_path.glob("*.md"))
    assert len(written) == 1, f"expected one lesson file, got {written}"
    data = _parse_block(written[0].read_text(encoding="utf-8"))
    for field in ("title", "domain", "tags", "status", "evidence_level"):
        assert data.get(field), f"{field!r} is empty after a round-trip through write_lesson"


def test_both_frontmatter_builders_agree(tmp_path, monkeypatch):
    """`_render_lesson` and `write_lesson` must not drift apart — that drift *was* the bug.

    Two builders of one artefact is how one of them ended up wrong for as long as nobody compared
    them. This compares them.
    """
    import scripts.queue_lesson as q

    monkeypatch.setattr(q, "LESSONS_DIR", tmp_path)
    monkeypatch.setattr(q, "_update_index", lambda *a, **k: None)
    monkeypatch.setattr(q, "_print_suggested_git", lambda *a, **k: None)
    monkeypatch.setattr(q.subprocess, "run", _no_git)
    _no_index_rebuild(monkeypatch)

    content = "## Problem\n\nx\n\n## Root Cause\n\ny\n\n## Solution\n\nz\n\n## Verification\n\nw\n"
    args = ("Both builders", "devops", ["t"], content)
    _, _, rendered, _, _ = q._render_lesson(*args, source="test")
    q.write_lesson(*args, source="test")
    written = next(iter(tmp_path.glob("*.md"))).read_text(encoding="utf-8")

    def block(text: str) -> str:
        return text.split("---\n", 2)[1]

    render_keys = set(_parse_block(rendered))
    write_keys = set(_parse_block(written))
    assert render_keys == write_keys, (
        f"the two builders disagree on which fields they write: "
        f"only in _render_lesson={render_keys - write_keys}, only in write_lesson={write_keys - render_keys}"
    )


# ── #1775: the fallback parser must read the shapes lessons actually use ───────────────────────────

def test_a_list_of_mappings_parses_as_a_list_of_dicts():
    """`freshness_boosts` is a list of mappings; the parser returned a dict, so it was a no-op."""
    parsed = _extract_frontmatter(
        "---\ntitle: probe\nfreshness_boosts:\n"
        '  - type: "release"\n    date: "2026-09-01"\n'
        '  - type: "incident"\n---\n\nbody\n'
    )
    boosts = parsed.get("freshness_boosts")
    assert isinstance(boosts, list), f"expected a list, got {type(boosts).__name__}: {boosts!r}"
    assert boosts[0] == {"type": "release", "date": "2026-09-01"}
    assert boosts[1] == {"type": "incident"}


def test_a_nested_map_is_not_clobbered_by_an_empty_list():
    """The nested-object branch stored the map and then the list flush wrote `[]` over it."""
    parsed = _extract_frontmatter(
        '---\ntitle: probe\nprovenance:\n  issue: "#1"\n  source: "x"\nstatus: published\n---\n\nbody\n'
    )
    assert parsed["provenance"] == {"issue": "#1", "source": "x"}, (
        f"a nested map must survive the flush, got {parsed['provenance']!r}"
    )
    assert parsed["status"] == "published", "parsing one field must not swallow the next"


@pytest.mark.parametrize("field,expected", [
    ("tags", ["a", "b"]),
    ("tags_inline", ["a", "b"]),
])
def test_plain_lists_still_parse(field, expected):
    """No regression in the shapes that already worked."""
    src = (f"---\ntitle: probe\ntags:\n  - a\n  - b\n---\n\nbody\n" if field == "tags"
           else "---\ntitle: probe\ntags_inline: [a, b]\n---\n\nbody\n")
    text = src.replace("tags_inline:", "tags:") if field == "tags_inline" else src
    assert _extract_frontmatter(text)["tags"] == expected
