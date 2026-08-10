"""Voice hooks tests — validates voice field in MCP responses and hook script.

Tests:
- MCP server responses include voice field for all tools
- Hook script exists and is executable
- Voice file mapping is correct
"""

import json
import os
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = REPO_ROOT / "docs" / "assets" / "voice"
HOOK_SCRIPT = REPO_ROOT / "scripts" / "misakanet_voice_hook.sh"
MCP_SERVER = REPO_ROOT / "scripts" / "mcp_server.py"
MCP_HTTP_SERVER = REPO_ROOT / "scripts" / "mcp_http_server.py"

EXPECTED_VOICE_FILES = [
    "connect-success.mp3",
    "pair-success.mp3",
    "lesson-found.mp3",
    "failure-warning.mp3",
]

# Voice field should appear in all tool responses
VOICE_PRESENT_TOOLS = [
    "handle_search",
    "handle_get_lesson",
    "handle_submit_usage",
]


class TestHookScript:
    """Hook script must exist and be executable."""

    def test_hook_exists(self):
        assert HOOK_SCRIPT.is_file(), f"Missing: {HOOK_SCRIPT}"

    def test_hook_executable(self):
        mode = HOOK_SCRIPT.stat().st_mode
        assert mode & stat.S_IXUSR, "Hook script not executable"

    def test_hook_has_voice_dir(self):
        content = HOOK_SCRIPT.read_text()
        assert "docs/assets/voice" in content or "VOICE_DIR" in content

    def test_hook_handles_all_voice_types(self):
        content = HOOK_SCRIPT.read_text()
        for voice in ["connect-success", "pair-success", "lesson-found", "failure-warning"]:
            assert voice in content, f"Hook missing case for: {voice}"


class TestMCPServerVoiceField:
    """MCP server responses must include voice field."""

    def test_search_has_voice(self):
        content = MCP_SERVER.read_text()
        # Find handle_search function and check for voice field
        assert '"voice"' in content, "MCP server missing voice field"
        assert "lesson-found" in content, "MCP server missing lesson-found voice"
        assert "failure-warning" in content, "MCP server missing failure-warning voice"

    def test_get_lesson_has_voice(self):
        content = MCP_SERVER.read_text()
        assert "connect-success" in content, "MCP server missing connect-success voice"

    def test_submit_usage_has_voice(self):
        content = MCP_SERVER.read_text()
        assert "pair-success" in content, "MCP server missing pair-success voice"


class TestVoiceFileMapping:
    """Voice files must exist and match hook mapping."""

    def test_all_voice_files_exist(self):
        missing = [f for f in EXPECTED_VOICE_FILES if not (VOICE_DIR / f).is_file()]
        assert not missing, f"Missing voice files: {missing}"

    def test_voice_files_nonzero(self):
        for name in EXPECTED_VOICE_FILES:
            path = VOICE_DIR / name
            if path.is_file():
                assert path.stat().st_size > 0, f"Empty file: {name}"


class TestDocumentation:
    """Voice hooks documentation must exist."""

    def test_doc_exists(self):
        doc = REPO_ROOT / "docs" / "integrations" / "mcp-voice-hooks.md"
        assert doc.is_file(), f"Missing: {doc}"

    def test_doc_has_setup(self):
        doc = REPO_ROOT / "docs" / "integrations" / "mcp-voice-hooks.md"
        content = doc.read_text()
        assert "PostToolUse" in content, "Doc missing PostToolUse hook config"
        assert "settings.json" in content, "Doc missing settings.json reference"


if __name__ == "__main__":
    import sys
    tests = [
        TestHookScript,
        TestMCPServerVoiceField,
        TestVoiceFileMapping,
        TestDocumentation,
    ]
    total, passed, failed = 0, 0, 0
    for cls in tests:
        inst = cls()
        for method in dir(inst):
            if not method.startswith("test_"):
                continue
            total += 1
            try:
                getattr(inst, method)()
                passed += 1
            except AssertionError as e:
                print(f"FAIL {cls.__name__}.{method}: {e}")
                failed += 1
    print(f"\n{passed}/{total} passed, {failed} failed")
    sys.exit(1 if failed else 0)
