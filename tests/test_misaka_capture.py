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


def test_capture_context_not_found(tmp_path, capsys):
    """A context path that does not exist is a hard error, not an empty context.

    The path is built under tmp_path instead of being spelled "/nonexistent": on Windows a
    POSIX-rooted path is *drive-relative*, so "/nonexistent" means "\\nonexistent" — the root of the
    current drive, not a sibling of anything in the repo. Measured on windows-latest, that path is
    not merely missing: it can exist (another test's `mkdir(parents=True)` reaches it there and only
    there), and then `read_text()` on it raises `PermissionError: [Errno 13] ... '\\nonexistent'`
    instead of taking the branch this test is about. A path that cannot exist on any platform keeps
    the property meaningful: the CLI exits non-zero and says what is missing.
    """
    from scripts.misaka_capture import main

    missing = tmp_path / "does-not-exist.log"
    with patch("sys.argv", ["misaka-capture", "--summary", "test", "--context", str(missing)]):
        with pytest.raises(SystemExit) as excinfo:
            main()

    assert excinfo.value.code == 1, "a missing context file must not be reported as success"
    err = capsys.readouterr().err
    assert "not found" in err, f"the message must say what is wrong: {err!r}"
    assert str(missing) in err, err


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
