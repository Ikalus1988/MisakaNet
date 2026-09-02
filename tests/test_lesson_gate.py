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
    parse_frontmatter,
    validate_content_len,
    validate_evidence,
    validate_file,
    validate_required,
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
    return "# Problem\n\n" + ("x" * 200)


# ── parse_frontmatter ────────────────────────────────────────────────
class TestParseFrontmatter:
    def test_valid_json_frontmatter(self, tmp_path):
        p = make_lesson(tmp_path, valid_fm(), long_content())
        fm, content = parse_frontmatter(p.read_text(encoding="utf-8"))
        assert fm["title"] == valid_fm()["title"]
        assert "x" * 200 in content

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
