#!/usr/bin/env python3
"""Test misaka capture CLI — redacted failure report submission."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def temp_files(tmp_path):
    """Use temporary files."""
    queue_file = tmp_path / "contribution_queue.jsonl"
    with patch("scripts.contribution_queue.QUEUE_FILE", queue_file):
        yield queue_file


def test_capture_basic(tmp_path):
    """Basic capture with summary only."""
    from scripts.misaka_capture import main

    ctx = tmp_path / "error.log"
    ctx.write_text("ERROR: pip install timeout behind proxy")

    with patch("sys.argv", ["misaka-capture", "--summary", "pip timeout", "--context", str(ctx)]):
        main()


def test_capture_with_context(tmp_path):
    """Capture with context file containing secrets."""
    from scripts.contribution_queue import list_contributions
    from scripts.misaka_capture import main

    ctx = tmp_path / "error.log"
    ctx.write_text("ERROR: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij12 auth failed")

    with patch("sys.argv", ["misaka-capture", "--summary", "GitHub auth failed", "--context", str(ctx)]):
        main()

    items = list_contributions()
    assert len(items) == 1
    assert "ghp_" not in items[0]["message"]  # redacted


def test_capture_context_not_found():
    """Capture with missing context file."""
    from scripts.misaka_capture import main

    with patch("sys.argv", ["misaka-capture", "--summary", "test", "--context", "/nonexistent"]):
        with pytest.raises(SystemExit):
            main()


def test_capture_source_tracking(tmp_path):
    """Capture tracks source."""
    from scripts.contribution_queue import list_contributions
    from scripts.misaka_capture import main

    with patch("sys.argv", ["misaka-capture", "--summary", "CI failed", "--source", "ci"]):
        main()

    items = list_contributions()
    assert items[0]["source"] == "ci"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
