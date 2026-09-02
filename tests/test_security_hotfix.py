"""Tests for security hotfix: path traversal, XSS, secret redaction."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from mcp_server import handle_get_lesson


def test_path_traversal_blocked():
    """Path traversal attempts should be blocked."""
    result = handle_get_lesson({"path": "../../etc/passwd"})
    assert "error" in result


def test_git_config_blocked():
    """Access to .git/config should be blocked."""
    result = handle_get_lesson({"path": ".git/config"})
    assert "error" in result


def test_non_md_blocked():
    """Non-.md files should be blocked."""
    result = handle_get_lesson({"path": "package.json"})
    assert "error" in result


def test_valid_lesson_allowed():
    """Valid lesson paths should be allowed."""
    result = handle_get_lesson({"path": "lessons/core/dco-auto-fix-workflow.md"})
    assert "content" in result


def test_lesson_id_allowed():
    """Lesson ID lookup should work."""
    result = handle_get_lesson({"id": "dco-auto-fix-workflow"})
    assert "content" in result
