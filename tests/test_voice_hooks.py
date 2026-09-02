"""Voice hooks tests — validates voice field in MCP responses and hook scripts.

Tests:
- MCP server responses include voice field for all tools
- Hook scripts (sh, ps1, bat) exist and have correct paths and handlers
- Voice file mapping is correct
- Windows voice hooks run and handle edge cases gracefully
"""

import json
import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = REPO_ROOT / "docs" / "assets" / "voice"
HOOK_SCRIPT_SH = REPO_ROOT / "scripts" / "misakanet_voice_hook.sh"
HOOK_SCRIPT_PS1 = REPO_ROOT / "scripts" / "misakanet_voice_hook.ps1"
HOOK_SCRIPT_BAT = REPO_ROOT / "scripts" / "misakanet_voice_hook.bat"
HANDLERS_DIR = REPO_ROOT / "misakanet" / "server" / "handlers"
SEARCH_HANDLER = HANDLERS_DIR / "search.py"
GET_LESSON_HANDLER = HANDLERS_DIR / "get_lesson.py"
SUBMIT_HANDLER = HANDLERS_DIR / "submit.py"

EXPECTED_VOICE_FILES = [
    "connect-success.mp3",
    "pair-success.mp3",
    "lesson-found.mp3",
    "failure-warning.mp3",
]


class TestHookScript:
    """Hook scripts must exist, be well-formed, and handle all voice types."""

    def test_all_hooks_exist(self):
        assert HOOK_SCRIPT_SH.is_file(), f"Missing: {HOOK_SCRIPT_SH}"
        assert HOOK_SCRIPT_PS1.is_file(), f"Missing: {HOOK_SCRIPT_PS1}"
        assert HOOK_SCRIPT_BAT.is_file(), f"Missing: {HOOK_SCRIPT_BAT}"

    def test_hook_executable_on_posix(self):
        if os.name != "nt":
            mode = HOOK_SCRIPT_SH.stat().st_mode
            assert mode & stat.S_IXUSR, "Bash hook script not executable"

    def test_hooks_have_voice_dir(self):
        for script in [HOOK_SCRIPT_SH, HOOK_SCRIPT_PS1, HOOK_SCRIPT_BAT]:
            content = script.read_text(encoding="utf-8", errors="ignore")
            assert (
                "docs/assets/voice" in content
                or "docs\\assets\\voice" in content
                or "VOICE_DIR" in content
            ), f"Script {script.name} missing docs/assets/voice path"

    def test_hooks_handle_all_voice_types(self):
        for script in [HOOK_SCRIPT_SH, HOOK_SCRIPT_PS1, HOOK_SCRIPT_BAT]:
            content = script.read_text(encoding="utf-8", errors="ignore")
            for voice in ["connect-success", "pair-success", "lesson-found", "failure-warning"]:
                assert voice in content, f"{script.name} missing case for: {voice}"


class TestMCPServerVoiceField:
    """MCP server responses must include voice field."""

    def test_search_has_voice(self):
        content = SEARCH_HANDLER.read_text(encoding="utf-8", errors="ignore")
        assert '"voice"' in content, "Search handler missing voice field"
        assert "lesson-found" in content, "Search handler missing lesson-found voice"
        assert "failure-warning" in content, "Search handler missing failure-warning voice"

    def test_get_lesson_has_voice(self):
        content = GET_LESSON_HANDLER.read_text(encoding="utf-8", errors="ignore")
        assert '"voice"' in content, "Get lesson handler missing voice field"
        assert "connect-success" in content, "Get lesson handler missing connect-success voice"

    def test_submit_usage_has_voice(self):
        content = SUBMIT_HANDLER.read_text(encoding="utf-8", errors="ignore")
        assert '"voice"' in content, "Submit handler missing voice field"
        assert "pair-success" in content, "Submit handler missing pair-success voice"


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


class TestWindowsVoiceHookExecution:
    """Validate PowerShell and Batch hook execution on Windows platforms."""

    def test_ps1_valid_voice_execution(self):
        if os.name == "nt":
            res = subprocess.run(
                ["powershell", "-File", str(HOOK_SCRIPT_PS1)],
                input=json.dumps({"voice": "connect-success"}),
                text=True,
                capture_output=True,
                timeout=15,
            )
            assert res.returncode == 0, f"PS1 failed on valid voice: {res.stderr}"

    def test_ps1_invalid_voice_graceful(self):
        if os.name == "nt":
            res = subprocess.run(
                ["powershell", "-File", str(HOOK_SCRIPT_PS1)],
                input=json.dumps({"voice": "unknown-voice-type"}),
                text=True,
                capture_output=True,
                timeout=15,
            )
            assert res.returncode == 0, f"PS1 failed on invalid voice: {res.stderr}"

    def test_ps1_missing_voice_graceful(self):
        if os.name == "nt":
            res = subprocess.run(
                ["powershell", "-File", str(HOOK_SCRIPT_PS1)],
                input=json.dumps({"other": "field"}),
                text=True,
                capture_output=True,
                timeout=15,
            )
            assert res.returncode == 0, f"PS1 failed on missing voice: {res.stderr}"

    def test_bat_valid_voice_execution(self):
        if os.name == "nt":
            res = subprocess.run(
                [str(HOOK_SCRIPT_BAT)],
                input=json.dumps({"voice": "connect-success"}),
                text=True,
                capture_output=True,
                shell=True,
                timeout=15,
            )
            assert res.returncode == 0, f"BAT failed on valid voice: {res.stderr}"

    def test_bat_invalid_voice_graceful(self):
        if os.name == "nt":
            res = subprocess.run(
                [str(HOOK_SCRIPT_BAT)],
                input=json.dumps({"voice": "unknown-voice-type"}),
                text=True,
                capture_output=True,
                shell=True,
                timeout=15,
            )
            assert res.returncode == 0, f"BAT failed on invalid voice: {res.stderr}"


class TestDocumentation:
    """Voice hooks documentation must exist."""

    def test_doc_exists(self):
        doc = REPO_ROOT / "docs" / "integrations" / "mcp-voice-hooks.md"
        assert doc.is_file(), f"Missing: {doc}"

    def test_doc_has_setup(self):
        doc = REPO_ROOT / "docs" / "integrations" / "mcp-voice-hooks.md"
        content = doc.read_text(encoding="utf-8", errors="ignore")
        assert "PostToolUse" in content, "Doc missing PostToolUse hook config"
        assert "settings.json" in content, "Doc missing settings.json reference"


if __name__ == "__main__":
    import sys
    tests = [
        TestHookScript,
        TestMCPServerVoiceField,
        TestVoiceFileMapping,
        TestWindowsVoiceHookExecution,
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
            except Exception as e:
                print(f"ERROR {cls.__name__}.{method}: {e}")
                failed += 1
    print(f"\n{passed}/{total} passed, {failed} failed")
    sys.exit(1 if failed else 0)

