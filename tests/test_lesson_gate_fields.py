#!/usr/bin/env python3
"""Structured lesson fields in the gate: `summary_plain` + `trigger` + `verify` (#1783).

Three optional fields, required of a lesson that *enters* the corpus:

* ``summary_plain`` — one plain-language sentence for a non-technical reader (≤120 chars)
* ``trigger``       — the short, matchable condition that should make an agent search
* ``verify``        — a checkable pass/fail criterion

The tiering is #1506's (strict for added files, advisory for files that already
exist); what these tests pin down is that the split holds, that the messages name the
field and point at the template, and that nothing else about the gate moved — the
existing suite (``tests/test_lesson_gate.py``) is the regression net for that.

Run: python3 -m pytest tests/test_lesson_gate_fields.py -q
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.lesson_gate import (  # noqa: E402
    STRUCTURED_FIELDS,
    exists_on_base_branch,
    is_corpus_path,
    missing_structured_fields,
    structured_field_tier,
    validate_file,
    validate_structured_fields,
)

# A real lesson that has been in the corpus for months — used to prove the advisory
# tier on an *existing* file (the tier a maintainer meets when running the CLI by
# hand, and the one CI's `--existing` list uses).
EXISTING_LESSON = REPO / "lessons" / "contrib" / "model-switch-script-pattern.md"

BODY = (
    "## Problem\n\n"
    "`pip install` fails on every package behind the corporate proxy: the resolver\n"
    "hangs for the full default timeout and then exits with ReadTimeoutError even\n"
    "though the same command works on a machine outside the network. The log names\n"
    "only the index URL, so the failure looks like a package problem.\n\n"
    "## Root Cause\n\n"
    "The public index is unreachable from inside the proxy and pip has no route to\n"
    "it. Nothing is wrong with the package or the version pin.\n\n"
    "## Solution\n\n"
    "Point pip at the internal mirror and give the resolver a bound:\n\n"
    "```bash\n"
    "pip install -i https://mirror.example.com/pypi/simple --default-timeout=60 httpie\n"
    "```\n\n"
    "## Verification\n\n"
    "`pip install -v httpie` finishes with exit code 0 and the log shows the mirror\n"
    "URL, not pypi.org.\n"
)


def lesson_frontmatter(**overrides) -> dict:
    """Frontmatter that clears every rule, structured fields included."""
    fm = {
        "title": "pip install timeout behind the corporate proxy",
        "domain": "python",
        "tags": ["pip", "proxy"],
        "status": "published",
        "evidence_level": "E2",
        "summary_plain": "公司网络里装不上 Python 包，是因为下载源要先换成公司内部的镜像。",
        "trigger": "pip install timeout behind proxy",
        "verify": "pip install -v httpie 的退出码为 0",
    }
    fm.update(overrides)
    return fm


def write_lesson(root: Path, fm: dict, content: str = BODY, name: str = "lesson.md") -> Path:
    """Create `<root>/lessons/contrib/<name>` — a corpus path, which is what the
    new-lesson rules apply to (a fixture tree under /tmp cannot be classified by
    git, so a corpus path is strict by construction)."""
    directory = root / "lessons" / "contrib"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        f"---\n{json.dumps(fm, ensure_ascii=False, indent=2)}\n---\n\n{content}",
        encoding="utf-8",
    )
    return path


def findings(path: Path, root: Path, **kwargs) -> list[str]:
    return validate_file(path, root, dirs=("contrib",), **kwargs)


# ── The three tiers ─────────────────────────────────────────────────
def test_new_lesson_missing_trigger_fails(tmp_path):
    """A newly added lesson without `trigger` must not pass the gate."""
    fm = lesson_frontmatter()
    del fm["trigger"]
    path = write_lesson(tmp_path, fm)

    issues = findings(path, tmp_path)
    hard = [e for e in issues if not e.startswith("[warn]")]
    assert hard, f"a new lesson without `trigger` passed the gate: {issues}"
    assert any("missing structured field: trigger" in e for e in hard), issues
    assert any("lessons/TEMPLATE.md" in e for e in hard), issues


def test_new_lesson_missing_all_three_fields_names_each_one(tmp_path):
    fm = lesson_frontmatter()
    for field in STRUCTURED_FIELDS:
        del fm[field]
    path = write_lesson(tmp_path, fm)

    joined = " ".join(findings(path, tmp_path))
    for field in STRUCTURED_FIELDS:
        assert f"missing structured field: {field}" in joined, joined
    assert "lessons/TEMPLATE.md" in joined, joined


def test_complete_new_lesson_passes(tmp_path):
    """A lesson with the four sections *and* the three fields is clean."""
    path = write_lesson(tmp_path, lesson_frontmatter())
    assert findings(path, tmp_path) == []


def test_the_same_lesson_modified_only_warns(tmp_path):
    """The #1506 split: a file that already exists and is touched (--existing) gets
    advisory findings, never a hard error — legacy gaps are not this PR's debt."""
    fm = lesson_frontmatter()
    for field in STRUCTURED_FIELDS:
        del fm[field]
    path = write_lesson(tmp_path, fm)

    issues = findings(path, tmp_path, existing=True)
    assert issues, "the gap must still surface for the reviewer"
    assert all(e.startswith("[warn]") for e in issues), issues
    joined = " ".join(issues)
    for field in STRUCTURED_FIELDS:
        assert field in joined, joined
    assert "backfill is optional" in joined, joined


# ── Length / shape limits ───────────────────────────────────────────
def test_summary_plain_over_the_limit_fails(tmp_path):
    """`summary_plain` is one sentence for a non-technical reader: a wall of text is
    not a plain-language summary, so the 120-char limit is enforced."""
    too_long = "这是一句被拉得很长的大白话，长到已经不能算一句大白话了。" * 5
    assert len(too_long) > 120
    path = write_lesson(tmp_path, lesson_frontmatter(summary_plain=too_long))

    hard = [e for e in findings(path, tmp_path) if not e.startswith("[warn]")]
    assert any("summary_plain too long" in e and "120" in e for e in hard), hard


def test_verify_over_the_limit_fails(tmp_path):
    """`verify` is a criterion ("exit code 0"), not a test plan."""
    too_long = "运行集成测试并观察以下所有检查项是否全部通过：" + "检查项" * 70
    assert len(too_long) > 200
    path = write_lesson(tmp_path, lesson_frontmatter(verify=too_long))

    hard = [e for e in findings(path, tmp_path) if not e.startswith("[warn]")]
    assert any("verify too long" in e and "200" in e for e in hard), hard


def test_trigger_must_be_short_and_single_line(tmp_path):
    """A `trigger` is a matchable fragment, not a paragraph or a multi-line list."""
    path = write_lesson(tmp_path, lesson_frontmatter(trigger="pip install timeout\nbehind proxy\nretry"))
    hard = [e for e in findings(path, tmp_path) if not e.startswith("[warn]")]
    assert any("trigger must be a single line" in e for e in hard), hard

    wide = write_lesson(tmp_path, lesson_frontmatter(trigger="pip timeout " * 20), name="wide.md")
    hard = [e for e in findings(wide, tmp_path) if not e.startswith("[warn]")]
    assert any("trigger too long" in e for e in hard), hard


def test_non_string_structured_field_fails(tmp_path):
    """A nested object is not a sentence, a trigger or a criterion."""
    path = write_lesson(tmp_path, lesson_frontmatter(trigger=["pip", "timeout"]))
    hard = [e for e in findings(path, tmp_path) if not e.startswith("[warn]")]
    assert any("missing structured field: trigger" in e for e in hard), hard


def test_validate_structured_fields_reports_clean_frontmatter_as_empty():
    assert validate_structured_fields(lesson_frontmatter()) == []
    assert missing_structured_fields(lesson_frontmatter()) == []


# ── Classification (which tier a path gets) ─────────────────────────
def test_a_file_outside_a_lesson_tree_is_not_covered(tmp_path):
    """`validate_file` is also used on ad-hoc paths; a markdown file that is not part
    of a lesson tree is not a lesson entering the corpus, and the new-lesson field
    rule does not apply to it. (This is why the pre-existing gate suite is untouched
    by #1783: its fixtures live in a flat temp directory.)"""
    path = tmp_path / "lesson.md"
    path.write_text(
        f"---\n{json.dumps(lesson_frontmatter(), ensure_ascii=False)}\n---\n\n{BODY}",
        encoding="utf-8",
    )
    assert is_corpus_path(path) is False
    assert structured_field_tier(path, tmp_path) == "skip"
    assert not [e for e in validate_file(path, REPO) if "structured field" in e]


def test_an_existing_corpus_lesson_is_advisory_not_failing():
    """The command a maintainer actually runs — the bare CLI on a lesson that has been
    in the corpus for months — must not start failing because of #1783.

    Skipped where git cannot place the file on a base branch (the classification then
    falls back to the corpus-path rule, which is strict by design).
    """
    if not EXISTING_LESSON.exists():
        pytest.skip(f"{EXISTING_LESSON} is not in this checkout")
    if exists_on_base_branch(EXISTING_LESSON, REPO) is not True:
        pytest.skip("git cannot resolve a base branch here")

    assert structured_field_tier(EXISTING_LESSON, REPO) == "advisory"
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "lesson_gate.py"), str(EXISTING_LESSON)],
        cwd=REPO, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "WARN" in proc.stdout, proc.stdout
    for field in STRUCTURED_FIELDS:
        assert field in proc.stdout, proc.stdout


def test_existing_true_overrides_classification(tmp_path):
    """`--existing` is the caller's verdict and always wins (CI's modified list)."""
    path = write_lesson(tmp_path, lesson_frontmatter())
    assert structured_field_tier(path, tmp_path) == "strict"
    assert structured_field_tier(path, tmp_path, existing=True) == "advisory"
