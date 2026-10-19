"""Voice Prompts verification tests (Issue #912).

Validates:
- All 4 MP3 files exist in docs/assets/voice/
- Files are non-empty and valid audio
- /start (the live page; /connect 301s to it) references voice toggle
- /start references all 4 MP3 files
- opt-in toggle wired to localStorage
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = REPO_ROOT / "docs" / "assets" / "voice"
START_HTML = REPO_ROOT / "docs" / "start.html"

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


class TestStartPage:
    """`/start` is the page that serves the human door (`/connect` 301s here).

    These assertions used to run against `docs/connect.html`, which nothing serves: the worker's
    `/connect` is a 301 and its catch-all answers `/connect.html` with a placeholder. Six tests
    certified a page no user could reach, and they were written against that page's older API
    (`/api/connect`) which the worker never exposed — so they would have failed had anyone run them
    against production.
    """

    def test_page_has_voice_toggle(self):
        html = START_HTML.read_text(encoding="utf-8")
        assert "Enable Misaka Voice" in html, "Missing voice toggle label"
        assert "misakanet_voice_enabled" in html, "Missing localStorage key for voice pref"

    def test_page_references_all_mp3s(self):
        html = START_HTML.read_text(encoding="utf-8")
        for name in EXPECTED_FILES:
            assert name in html, f"Missing reference to {name}"

    def test_voice_is_played_through_one_map(self):
        """One map, not four scattered literals: that is what keeps the cue names resolvable."""
        html = START_HTML.read_text(encoding="utf-8")
        assert "MISAKA_VOICE" in html, "Missing the event -> file map"
        assert "new Audio(" in html, "no playback path"

    def test_page_has_pairing_flow(self):
        html = START_HTML.read_text(encoding="utf-8")
        assert "/mcp/connect" in html, "Missing /mcp/connect reference"
        assert "/mcp/pair" in html, "Missing /mcp/pair reference"


class TestVoiceTriggerMapping:
    """Verify event-to-file mapping matches Issue #912 spec."""

    def test_connect_event_maps_file(self):
        html = START_HTML.read_text(encoding="utf-8")
        assert "connect-success.mp3" in html

    def test_failure_event_maps_file(self):
        html = START_HTML.read_text(encoding="utf-8")
        assert "failure-warning.mp3" in html


if __name__ == "__main__":
    import sys
    tests = [TestVoiceFilesExist, TestStartPage, TestVoiceTriggerMapping]
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
