"""Tests for the Lesson Quality Gate (issue #889).

Structural validation for new lesson contributions:
  - required frontmatter fields: title, domain, tags, status, evidence_level
  - minimum content length: 100 chars (excluding frontmatter)
  - no duplicate titles
  - domain in allowed list
  - tags from valid format (1-10 unique strings, min 2 chars)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.lesson_gate import (  # noqa: E402
    allowed_domains,
    find_duplicate_title,
    frontmatter_diagnostic,
    parse_frontmatter,
    validate_content_len,
    validate_evidence,
    validate_file,
    validate_required,
    validate_sections,
    validate_status,
    validate_tags,
    validate_title,
)

LESSON_DIR = REPO / "lessons"


def make_lesson(tmp_path: Path, fm: dict, content: str, name: str = "lesson.md") -> Path:
    """Create a lesson file with JSON frontmatter."""
    path = tmp_path / name
    path.write_text(f"---\n{json.dumps(fm, ensure_ascii=False, indent=2)}\n---\n\n{content}", encoding="utf-8")
    return path


def valid_fm() -> dict:
    return {
        "title": "Valid Lesson Title For Gate Testing",
        "domain": "mcp",
        "tags": ["mcp", "debugging"],
        "status": "published",
        "evidence_level": "E1",
    }


def long_content() -> str:
    """A minimal body that clears every *new-lesson* rule (sections + 400 chars).

    Kept deliberately generic: tests that exercise one field shouldn't fail on
    structure. Use STUB_LESSON below when the structure is what's under test.
    """
    return (
        "## Problem\n\n"
        "A CI job that runs database migrations exits non-zero while the identical command\n"
        "succeeds on a developer machine, and the log stops at the exit code.\n\n"
        "## Root Cause\n\n"
        "The recorded migration revision and the migration directory disagreed, so the tool\n"
        "refused to pick a head. Nothing in the traceback names that state mismatch.\n\n"
        "## Solution\n\n"
        "Compare what the database believes with what the directory offers, then reconcile with\n"
        "a merge revision rather than editing an already-applied migration.\n\n"
        "## Verification\n\n"
        "Run the migration from a database restored from the previous release; it must finish\n"
        "without manual steps and report a single head afterwards.\n"
    )


# ── parse_frontmatter ────────────────────────────────────────────────
class TestParseFrontmatter:
    def test_valid_json_frontmatter(self, tmp_path):
        p = make_lesson(tmp_path, valid_fm(), long_content())
        fm, content = parse_frontmatter(p.read_text(encoding="utf-8"))
        assert fm["title"] == valid_fm()["title"]
        assert "## Root Cause" in content  # body kept, frontmatter stripped

    def test_missing_frontmatter(self, tmp_path):
        p = tmp_path / "no-fm.md"
        p.write_text("# Just content", encoding="utf-8")
        fm, content = parse_frontmatter(p.read_text(encoding="utf-8"))
        assert fm == {}
        assert content.startswith("# Just content")

    def test_invalid_json_frontmatter(self, tmp_path):
        p = tmp_path / "bad-fm.md"
        p.write_text("---\n{not valid json\n---\nbody", encoding="utf-8")
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        assert fm == {}


# ── validate_required ────────────────────────────────────────────────
class TestRequiredFields:
    @pytest.mark.parametrize("missing", ["title", "domain", "tags", "status", "evidence_level"])
    def test_missing_field_fails(self, tmp_path, missing):
        fm = valid_fm()
        del fm[missing]
        errors = validate_required(fm)
        assert any(missing in e for e in errors), errors

    def test_all_fields_present_passes(self):
        assert validate_required(valid_fm()) == []


# ── validate_title ───────────────────────────────────────────────────
class TestTitle:
    def test_short_title_fails(self):
        assert validate_title("abc")  # < 4 chars

    def test_long_title_fails(self):
        assert validate_title("t" * 121)

    def test_valid_title_passes(self):
        assert not validate_title("A Proper Lesson Title")


# ── validate_tags ───────────────────────────────────────────────────
class TestTags:
    def test_not_list_fails(self):
        assert validate_tags("mcp")

    def test_empty_list_fails(self):
        assert validate_tags([])

    def test_short_tag_fails(self):
        assert validate_tags(["a"])

    def test_duplicate_tags_fail(self):
        assert validate_tags(["mcp", "mcp"])

    def test_too_many_tags_fail(self):
        assert validate_tags([f"tag{i}" for i in range(11)])

    def test_valid_tags_pass(self):
        assert not validate_tags(["mcp", "debugging"])


# ── validate_status / validate_evidence ─────────────────────────────
class TestStatusAndEvidence:
    @pytest.mark.parametrize("bad", ["live", "PUBLISHED", "", 42])
    def test_invalid_status_fails(self, bad):
        assert validate_status(bad)

    def test_valid_status_passes(self):
        assert not validate_status("draft")

    @pytest.mark.parametrize("bad", ["E9", "", "high", 3])
    def test_invalid_evidence_fails(self, bad):
        assert validate_evidence(bad)

    def test_valid_evidence_passes(self):
        assert not validate_evidence("E0")


# ── content length ──────────────────────────────────────────────────
class TestContentLength:
    def test_short_content_fails(self):
        assert not validate_content_len("# Problem\n\nshort")

    def test_100_chars_passes(self):
        assert validate_content_len("# Problem\n\n" + ("x" * 89))  # 11 + 89 = 100

    def test_99_chars_fails(self):
        assert not validate_content_len("# Problem\n\n" + ("x" * 88))  # 11 + 88 = 99


# ── allowed_domains / duplicates ────────────────────────────────────
class TestRepoChecks:
    def test_allowed_domains_includes_docs_and_lessons(self):
        domains = allowed_domains(REPO)
        assert "mcp" in domains  # lessons/core uses mcp
        assert "network" in domains  # docs/domains has network.md

    def test_duplicate_title_detected(self, tmp_path):
        p = make_lesson(tmp_path, valid_fm(), long_content())
        existing = "DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation"
        assert find_duplicate_title(existing, REPO, exclude_file=p)

    def test_unique_title_not_detected(self, tmp_path):
        p = make_lesson(tmp_path, valid_fm(), long_content())
        unique = "zz_never_seen_title_for_gate_test_8842"
        assert not find_duplicate_title(unique, REPO, exclude_file=p)


# ── validate_file (integration) ─────────────────────────────────────
class TestValidateFile:
    def test_valid_lesson_passes(self, tmp_path):
        p = make_lesson(tmp_path, valid_fm(), long_content())
        errors = validate_file(p, REPO)
        assert errors == []

    def test_missing_fields_errors(self, tmp_path):
        fm = valid_fm()
        del fm["tags"]
        del fm["evidence_level"]
        p = make_lesson(tmp_path, fm, long_content())
        errors = validate_file(p, REPO)
        assert any("tags" in e for e in errors)
        assert any("evidence_level" in e for e in errors)

    def test_disallowed_domain_fails(self, tmp_path):
        fm = valid_fm()
        fm["domain"] = "not-a-real-domain-xyz"
        p = make_lesson(tmp_path, fm, long_content())
        errors = validate_file(p, REPO)
        assert any("domain" in e for e in errors)

    def test_duplicate_title_fails(self, tmp_path):
        fm = valid_fm()
        fm["title"] = "DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation"
        p = make_lesson(tmp_path, fm, long_content())
        errors = validate_file(p, REPO)
        assert any("duplicate" in e.lower() for e in errors)


# ── CLI ─────────────────────────────────────────────────────────────
class TestCli:
    def test_exit_zero_on_valid(self, tmp_path):
        p = make_lesson(tmp_path, valid_fm(), long_content())
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "lesson_gate.py"), str(p)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr

    def test_exit_one_on_invalid(self, tmp_path):
        p = tmp_path / "bad.md"
        p.write_text("---\n{title: 'x'}\n---\nshort", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "lesson_gate.py"), str(p)],
            capture_output=True, text=True,
        )
        assert r.returncode == 1


# ── Near-duplicate & fake-verification detection (2026-08-30) ───────
def make_lesson_tree(tmp_path: Path, files: dict[str, tuple[dict, str]]) -> Path:
    """Create tmp_path/lessons/<sub>/<name>.md for each entry and return
    the tmp_path root so tests can pass `dirs=('contrib',)`."""
    root = tmp_path / "lessons"
    for name, (fm, content) in files.items():
        d = root / "contrib"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(
            f"---\n{json.dumps(fm, ensure_ascii=False, indent=2)}\n---\n\n{content}",
            encoding="utf-8",
        )
    return tmp_path


class TestNearDuplicateDetection:
    def test_identical_body_reported(self, tmp_path):
        """Copy-pasted lesson body (same language) is flagged."""
        content = (
            "## Problem\n\npip install fails behind corporate proxy with "
            "ReadTimeoutError when the index is unreachable.\n\n"
            "## Solution\n\nUse a proxy-aware index and retry with backoff.\n\n"
            "## Verification\n\npip install succeeds on a clean venv.\n"
        )
        fm_b = valid_fm(); fm_b["title"] = "Different Title Same Body"
        root = make_lesson_tree(tmp_path, {
            "a.md": (valid_fm(), content),
            "b.md": (fm_b, content),
        })
        p = root / "lessons" / "contrib" / "a.md"
        errors = validate_file(p, root, dirs=("contrib",))
        assert any("near-duplicate" in e for e in errors)

    def test_translation_pair_not_reported(self, tmp_path):
        """Two files that explicitly declare different languages are skipped."""
        content = (
            "## Problem\n\npip install fails behind corporate proxy with "
            "ReadTimeoutError when the index is unreachable.\n\n"
            "## Solution\n\nUse a proxy-aware index and retry with backoff.\n\n"
            "## Verification\n\npip install succeeds on a clean venv.\n"
        )
        fm_en = valid_fm(); fm_en["language"] = "en"
        fm_zh = valid_fm(); fm_zh["language"] = "zh"; fm_zh["title"] = "中文标题"
        root = make_lesson_tree(tmp_path, {
            "a.md": (fm_en, content),
            "b.md": (fm_zh, content),
        })
        p = root / "lessons" / "contrib" / "a.md"
        errors = validate_file(p, root, dirs=("contrib",))
        assert not any("near-duplicate" in e for e in errors)

    def test_different_topics_not_reported(self, tmp_path):
        """Unrelated lessons must not be flagged."""
        fm_b = valid_fm(); fm_b["title"] = "Unrelated Feishu Topic"
        root = make_lesson_tree(tmp_path, {
            "a.md": (valid_fm(),
                     "## Problem\n\ndocker container crashes on startup\n\n"
                     "## Solution\n\ncheck logs\n"),
            "b.md": (fm_b,
                     "## Problem\n\nfeishu webhook not delivering\n\n"
                     "## Solution\n\nreconfigure\n"),
        })
        p = root / "lessons" / "contrib" / "a.md"
        errors = validate_file(p, root, dirs=("contrib",))
        assert not any("near-duplicate" in e for e in errors)


class TestFakeVerification:
    def test_placeholder_verification_flagged(self, tmp_path):
        """grep | wc -l placeholder is detected as a warning."""
        content = (
            "## Problem\n\nsomething breaks\n\n"
            "## Solution\n\nfix it\n\n"
            "## Verification\n\n```bash\ngrep -i feishu lessons/*.md | wc -l\n"
            "echo Feishu verified\n```\n"
        )
        p = make_lesson(tmp_path, valid_fm(), content)
        errors = validate_file(p, REPO)
        assert any("[warn]" in e and "placeholder" in e.lower() for e in errors)

    def test_real_verification_not_flagged(self, tmp_path):
        """A verification that actually tests the fix passes clean."""
        content = (
            "## Problem\n\nsomething breaks\n\n"
            "## Solution\n\nfix it\n\n"
            "## Verification\n\n```bash\npytest tests/test_fix.py -q && "
            "python -c 'import fix; assert fix.works()'\n```\n"
        )
        p = make_lesson(tmp_path, valid_fm(), content)
        errors = validate_file(p, REPO)
        assert not any("placeholder" in e.lower() for e in errors)


# ── Existing-file advisory mode + mirror dedupe (#1506) ─────────────
class TestExistingMode:
    def test_existing_mode_demotes_legacy_gaps_to_warnings(self, tmp_path):
        """A legacy file (missing evidence_level/tags, short body) fails the
        strict gate but only warns in --existing mode."""
        fm = valid_fm()
        del fm["evidence_level"]
        del fm["tags"]
        content = "tiny body"
        p = make_lesson(tmp_path, fm, content)
        strict = validate_file(p, REPO)
        assert any("evidence_level" in e for e in strict)
        assert any("tags" in e for e in strict)
        assert not all(e.startswith("[warn]") for e in strict)
        relaxed = validate_file(p, REPO, existing=True)
        assert relaxed, "findings still surface for review"
        assert all(e.startswith("[warn]") for e in relaxed)
        assert not [e for e in relaxed if "evidence_level" in e and not e.startswith("[warn]")]

    def test_cli_existing_mode_exits_zero(self, tmp_path):
        fm = valid_fm()
        del fm["evidence_level"]
        p = make_lesson(tmp_path, fm, long_content())
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "lesson_gate.py"), "--existing", str(p)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "legacy" in r.stdout or "WARN" in r.stdout

    def test_cli_strict_mode_still_exits_one(self, tmp_path):
        fm = valid_fm()
        del fm["evidence_level"]
        p = make_lesson(tmp_path, fm, long_content())
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "lesson_gate.py"), str(p)],
            capture_output=True, text=True,
        )
        assert r.returncode == 1, r.stdout + r.stderr


class TestMirrorDuplicateTitles:
    DCO_TITLE = "DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation"
    DCO_STEM = "dco-auto-fix-workflow"  # core/ + en/ mirror pair on main

    def test_same_stem_mirror_not_duplicate(self):
        """core/dco-auto-fix-workflow.md vs en/dco-auto-fix-workflow.md is an
        i18n mirror pair (same stem) — canonical dedupe handles it."""
        core = REPO / "lessons" / "core" / f"{self.DCO_STEM}.md"
        assert core.exists()
        assert not find_duplicate_title(self.DCO_TITLE, REPO, exclude_file=core)

    def test_different_stem_same_title_cross_dir_still_duplicate(self):
        """A NEW lesson with the DCO title but a different stem must still be
        flagged as a duplicate even if it lives in a different subdir."""
        other = REPO / "lessons" / "contrib" / "zzz-unrelated-stem-gate-test.md"
        assert find_duplicate_title(self.DCO_TITLE, REPO, exclude_file=other)

# ── Required sections + minimum body (2026-09-13, PR #1656) ──────────
# A file that stopped after "## Problem" passed the old gate (100-char floor
# only) and reached review as a lesson. New lessons now need the four corpus
# sections and a 400-char body; pre-existing files stay advisory.

STUB_LESSON = """## Problem

在 CI 流水线里运行 Python 数据库迁移命令时触发 subprocess.CalledProcessError 异常，
本地同样命令成功，日志里只有一句非零退出码，没有更具体的失败位置，需要人工排查到底
是环境差异还是迁移脚本本身的问题，这一行只是为了把正文撑过一百字符的下限。
"""


def test_stub_lesson_is_rejected_and_names_what_is_missing(tmp_path):
    p = make_lesson(tmp_path, valid_fm(), STUB_LESSON)
    errors = validate_file(p, REPO)
    joined = " ".join(errors)
    assert "missing required section(s)" in joined, errors
    for label in ("Root Cause", "Solution", "Verification"):
        assert label in joined, errors
    assert any("too short" in e for e in errors), errors


def test_complete_lesson_passes_the_strict_rules(tmp_path):
    p = make_lesson(tmp_path, valid_fm(), long_content())
    errors = validate_file(p, REPO)
    assert not [e for e in errors if "missing required section" in e], errors
    assert not [e for e in errors if "too short" in e], errors


def test_legacy_file_gets_a_warning_not_a_failure(tmp_path):
    """Pre-existing files are touched by metadata PRs; legacy gaps are advisory."""
    p = make_lesson(tmp_path, valid_fm(), STUB_LESSON)
    issues = validate_file(p, REPO, existing=True)
    hard = [e for e in issues if not e.startswith("[warn]")]
    assert not hard, hard
    assert any(e.startswith("[warn]") and "section" in e for e in issues), issues


def test_section_aliases_cover_chinese_headings():
    """Half the corpus writes 问题/根因/修复/验证 — aliases must match those."""
    zh = "## 问题\n\n## 根因\n\n## 修复\n\n## 验证\n"
    assert validate_sections(zh) == []
    assert validate_sections("## Problem\n\n## Notes\n") == ["Root Cause", "Solution", "Verification"]


# ── an unparseable block must not read as "no block" (2026-09-26) ────────────────────────────────

BROKEN_YAML_LESSON = '''---
title: "Chrome headless PDF supervision on macOS"
domain: "automation"
tags:
  - "chrome"
status: "published"
evidence_level: "E2"
fixes: [#2255, #2259]
---

## Problem

body

## Root Cause

r

## Solution

s

## Verification

v
'''


def test_a_broken_frontmatter_block_says_so_instead_of_naming_its_fields(tmp_path):
    """`fixes: [#2255, #2259]` is invalid YAML (`#` starts a comment) — the fields are all there.

    Measured on PR #2293, a bounty submission: the gate reported
    `missing required field: title` for a file whose third line is `title: ...`, because
    `parse_frontmatter` swallows the loader error and returns `{}`. That is the same shape as "no
    frontmatter at all", and only one of the two is fixed by editing fields. The contributor's only
    signal sent them to correct values that were already correct.
    """
    text = BROKEN_YAML_LESSON
    assert parse_frontmatter(text)[0] == {}, "the premise: this block does not load"
    diagnostic = frontmatter_diagnostic(text)
    assert diagnostic and "not valid YAML" in diagnostic, diagnostic
    # And the gate prints it *before* the field list, so it is the first thing read.
    p = tmp_path / "broken.md"
    p.write_text(text, encoding="utf-8")
    issues = validate_file(p, REPO)
    assert issues[0] == diagnostic, issues
    assert any("missing required field: title" in e for e in issues), (
        "the downstream field errors must still be reported — the diagnostic explains them"
    )


def test_quoting_the_value_removes_the_diagnostic(tmp_path):
    """The control: the same file with `fixes: ["#2255"]` parses, so the diagnostic is not a blanket
    "your frontmatter is odd" warning that fires on every lesson."""
    fixed = BROKEN_YAML_LESSON.replace('fixes: [#2255, #2259]', 'fixes: ["#2255", "#2259"]')
    assert frontmatter_diagnostic(fixed) is None
    assert frontmatter_diagnostic("---\ntitle: x\n---\nbody") is None, "a normal block stays quiet"
    assert frontmatter_diagnostic("# no frontmatter at all") is None, (
        "an absent block is not a parse error — the field errors are the right report for it"
    )


def test_the_no_lesson_annotation_says_the_check_verified_nothing():
    """The workflow's green tick must not read as certification of a deliverable.

    `lesson-gate.yml` runs on every PR so it can be a required check, and reports success when no
    `lessons/**/*.md` matches (#1920). On 2026-09-26 two PRs claiming a *question-bounty* issue — whose
    task is a lesson under `lessons/` — carried that check green while adding no lesson at all: one
    patched `scripts/check_provenance.py`, the other added `solutions/issue_2283_solution.ts`. Nothing
    can make the job fail there without breaking the required-check property, so what has to be true is
    that the run *says* it verified nothing, in the annotation a reviewer sees.
    """
    text = (REPO / ".github" / "workflows" / "lesson-gate.yml").read_text(encoding="utf-8")
    assert "::warning title=Lesson Quality Gate verified nothing::" in text, (
        "the no-lesson branch no longer annotates the run"
    )
    assert "says nothing about a lesson" in text, "the annotation no longer states what it does not mean"
    assert "still reports success on purpose" in text, (
        "the reason the job cannot simply fail (a required check must report) must stay written down"
    )
