"""The OKF export must carry each lesson's provenance (#3004).

`extract_frontmatter` walked the frontmatter lines doing `line.partition(":")` after
`line.strip()`. That destroyed indentation, so a nested `provenance:` block collapsed onto the top
level and its `source` overwrote the lesson's own `source`; block sequences parsed to nothing; and
escapes were mangled. Measured on the corpus before this fix: 48 lessons declared
`provenance.issue` and **zero** exported records carried one.

The last test is the one that matters — it is the defect as an invariant over the whole corpus, so
a future re-introduction of a hand-rolled parser fails here rather than quietly in production.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import export_okf  # noqa: E402

EXPORT = REPO / "data" / "okf" / "lessons.jsonl"


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "lesson.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_a_nested_provenance_block_stays_nested(tmp_path):
    fm = export_okf.extract_frontmatter(write(tmp_path, (
        "---\n"
        'title: "t"\n'
        "provenance:\n"
        '  issue: "#2804"\n'
        '  source: "MCP intake"\n'
        "---\nbody\n"
    )))
    assert fm["provenance"] == {"issue": "#2804", "source": "MCP intake"}


def test_provenance_source_does_not_overwrite_the_lessons_own_source(tmp_path):
    """The overwrite is the part that silently corrupted data, not just a lost field."""
    fm = export_okf.extract_frontmatter(write(tmp_path, (
        "---\n"
        'title: "t"\n'
        'source: "uncledad96-glitch"\n'
        "provenance:\n"
        '  source: "external"\n'
        "---\nbody\n"
    )))
    assert fm["source"] == "uncledad96-glitch"
    assert fm["provenance"]["source"] == "external"


def test_block_sequence_tags_are_read_as_a_list(tmp_path):
    fm = export_okf.extract_frontmatter(write(tmp_path, (
        "---\n"
        "tags:\n"
        "  - alpha\n"
        "  - beta\n"
        "---\nbody\n"
    )))
    assert fm["tags"] == ["alpha", "beta"]


def test_escapes_inside_a_quoted_value_survive(tmp_path):
    fm = export_okf.extract_frontmatter(write(tmp_path, (
        "---\n"
        'verify: "grep -q \\"Errno 98\\" out"\n'
        "---\nbody\n"
    )))
    assert '"Errno 98"' in fm["verify"]


def test_a_json_block_followed_by_yaml_is_not_dropped(tmp_path):
    """32 lessons have this shape (081e64d5). `yaml.safe_load` alone rejects the whole block."""
    fm = export_okf.extract_frontmatter(write(tmp_path, (
        "---\n"
        '{"title": "t", "domain": "devops", "source": "someone"}\n'
        "provenance:\n"
        '  source: "external"\n'
        "---\nbody\n"
    )))
    assert fm["title"] == "t"
    assert fm["source"] == "someone"
    assert fm["provenance"] == {"source": "external"}


def test_a_date_value_is_stringified_so_json_can_serialise_it(tmp_path):
    fm = export_okf.extract_frontmatter(write(tmp_path, "---\ncreated: 2026-10-01\n---\nbody\n"))
    assert fm["created"] == "2026-10-01"
    json.dumps(fm)  # would raise on a date object


@pytest.fixture(scope="module")
def exported() -> list[dict]:
    return [json.loads(line) for line in EXPORT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _declaring_issue_paths(lesson_files) -> set:
    """Lessons that declare `provenance.issue`, located two independent ways (#3004).

    The two detectors disagree about what counts as a valid spelling, so the guard takes
    the union. The regex covers the `  issue: "#1234"` YAML shape even when the parser is
    the component that broke; the parser covers every other shape — JSON frontmatter, a
    bare `issue: 2804` — even though the regex was never taught those. Either detector
    alone would make the invariant only as broad as the heuristic behind it, and the
    failure is silent: the lesson is simply exempt from the check.
    """
    found = set()
    for md in lesson_files:
        if md.name == "README.md":
            continue
        head = md.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^---\s*\n(.*?)\n---", head, re.DOTALL)
        if m and re.search(r"^\s+issue:\s*[\"']?#\d+", m.group(1), re.M):
            found.add(md)
            continue
        fm = export_okf.extract_frontmatter(md)
        if isinstance(fm, dict):
            prov = fm.get("provenance")
            if isinstance(prov, dict) and prov.get("issue") not in (None, ""):
                found.add(md)
    return found


def test_the_guard_sees_an_issue_spelling_the_regex_never_learned(tmp_path):
    """Proves the parser arm of the union is load-bearing, rather than asserting it."""
    md = write(tmp_path, "---\ntitle: t\nprovenance:\n  issue: 2804\n---\nbody\n")
    assert _declaring_issue_paths([md]) == {md}


def test_every_lesson_that_declares_an_issue_exports_it(exported):
    """The defect as a corpus invariant — this is the test that would have caught #3004."""
    by_path = {r["path"]: r for r in exported}
    declaring = sorted(p.relative_to(REPO).as_posix()
                       for p in _declaring_issue_paths((REPO / "lessons").rglob("*.md")))
    assert len(declaring) >= 40, f"only {len(declaring)} lessons declare provenance.issue — corpus changed?"
    missing = [p for p in declaring if not (by_path.get(p, {}).get("provenance") or {}).get("issue")]
    assert not missing, (
        f"{len(missing)} lessons declare provenance.issue and the export dropped it, e.g. {missing[:3]}"
    )


def test_the_export_is_reproducible_from_the_tracked_sources(exported):
    """A one-line parser change that alters the corpus must be visible as a diff, not a surprise."""
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "export_okf.py"), "--check"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, f"export --check failed: {r.stdout[-400:]}{r.stderr[-400:]}"