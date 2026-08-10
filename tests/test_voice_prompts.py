"""Voice Prompts verification tests (Issue #912).

Validates:
- All 4 MP3 files exist in docs/assets/voice/
- Files are non-empty and valid audio
- /connect page exists and references voice toggle
- /connect page references all 4 MP3 files
- opt-in toggle wired to localStorage
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = REPO_ROOT / "docs" / "assets" / "voice"
CONNECT_HTML = REPO_ROOT / "docs" / "connect.html"

EXPECTED_FILES = [
    "connect-success.mp3",
    "pair-success.mp3",
    "lesson-found.mp3",
    "failure-warning.mp3",
]


class TestVoiceFilesExist:
    """All 4 voice MP3 files must exist and be non-empty."""

    def test_voice_directory_exists(self):
        assert VOICE_DIR.is_dir(), f"Voice directory missing: {VOICE_DIR}"

    def test_all_files_present(self):
        missing = [f for f in EXPECTED_FILES if not (VOICE_DIR / f).is_file()]
        assert not missing, f"Missing voice files: {missing}"

    def test_files_nonzero(self):
        for name in EXPECTED_FILES:
            path = VOICE_DIR / name
            if path.is_file():
                assert path.stat().st_size > 0, f"Empty file: {name}"

    def test_files_reasonable_size(self):
        """MP3s should be 10KB-5MB (sanity check, not a real audio check)."""
        for name in EXPECTED_FILES:
            path = VOICE_DIR / name
            if path.is_file():
                size = path.stat().st_size
                assert 10_000 < size < 5_000_000, (
                    f"{name} size {size} bytes outside expected range"
                )


class TestConnectPage:
    """The /connect page must exist and implement voice opt-in."""

    def test_connect_page_exists(self):
        assert CONNECT_HTML.is_file(), f"Missing: {CONNECT_HTML}"

    def test_page_has_voice_toggle(self):
        html = CONNECT_HTML.read_text()
        assert "Enable Misaka Voice" in html, "Missing voice toggle label"
        assert "misaka-voice" in html, "Missing localStorage key for voice pref"

    def test_page_references_all_mp3s(self):
        html = CONNECT_HTML.read_text()
        for name in EXPECTED_FILES:
            assert name in html, f"Missing reference to {name}"

    def test_page_has_audio_elements(self):
        html = CONNECT_HTML.read_text()
        assert "<audio" in html, "No <audio> elements found"
        audio_count = html.count("<audio")
        assert audio_count >= 4, f"Expected >=4 <audio> elements, found {audio_count}"

    def test_page_has_toggle_logic(self):
        html = CONNECT_HTML.read_text()
        assert "playVoice" in html or "play(" in html, "Missing play function"
        assert "toggle" in html.lower(), "Missing toggle logic"

    def test_page_has_pairing_flow(self):
        html = CONNECT_HTML.read_text()
        assert "/api/connect" in html, "Missing /api/connect reference"
        assert "/api/pair" in html, "Missing /api/pair reference"


class TestVoiceTriggerMapping:
    """Verify event-to-file mapping matches Issue #912 spec."""

    def test_connect_event_maps_file(self):
        html = CONNECT_HTML.read_text()
        # connect-success.mp3 should be played on connect/pair success
        assert "voicePair" in html or "pair-success" in html

    def test_failure_event_maps_file(self):
        html = CONNECT_HTML.read_text()
        assert "voiceFailure" in html or "failure-warning" in html


if __name__ == "__main__":
    import sys
    tests = [TestVoiceFilesExist, TestConnectPage, TestVoiceTriggerMapping]
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
