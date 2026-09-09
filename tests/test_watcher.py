"""Tests for misakanet.watcher — Issue #1166."""
import json
import tempfile
from pathlib import Path

from misakanet.watcher import (
    content_filter,
    detect_failures,
    extract_lesson_draft,
    process_file,
    watch_directory,
)


class TestContentFilter:
    def test_too_short(self):
        result = content_filter("short text")
        assert result["pass"] is False
        assert "too short" in result["reason"]

    def test_no_failure_signals(self):
        text = "word " * 100  # 500 chars, no failure patterns
        result = content_filter(text)
        assert result["pass"] is False
        assert "no failure signals" in result["reason"]

    def test_passes_with_failure_signal(self):
        text = "word " * 50 + "an error occurred during execution " + "word " * 50
        result = content_filter(text)
        assert result["pass"] is True
        assert result["failure_signals"] >= 1

    def test_custom_min_length(self):
        text = "error happened"
        result = content_filter(text, min_length=10)
        assert result["pass"] is True

    def test_noise_detection(self):
        lines = ["# memory template"] * 50 + ["error occurred"]
        text = "\n".join(lines)
        result = content_filter(text)
        assert result["pass"] is False
        assert "noisy" in result["reason"]


class TestDetectFailures:
    def test_finds_error(self):
        text = "line1\nline2\nan exception was thrown\nline4"
        failures = detect_failures(text)
        assert len(failures) >= 1
        assert any("exception" in f["line"].lower() for f in failures)

    def test_finds_timeout(self):
        text = "processing...\nconnection timed out\nretrying"
        failures = detect_failures(text)
        assert len(failures) >= 1
        assert any("timed" in f["pattern"] or "timeout" in f["pattern"] for f in failures)

    def test_finds_http_error(self):
        text = "request sent\nserver returned 500\nfallback"
        failures = detect_failures(text)
        assert len(failures) >= 1

    def test_empty_text(self):
        failures = detect_failures("")
        assert failures == []

    def test_no_failures(self):
        text = "everything is fine\nno problems here\nall good"
        failures = detect_failures(text)
        assert failures == []

    def test_context_lines(self):
        text = "line1\nline2\nerror happened\nline4\nline5"
        failures = detect_failures(text)
        assert len(failures) >= 1
        assert "context" in failures[0]
        assert len(failures[0]["context"]) >= 2  # At least 2 context lines


class TestExtractLessonDraft:
    def test_generates_draft(self):
        failures = [{"line_no": 3, "line": "error occurred", "context": ["l1", "error occurred", "l3"], "pattern": "error"}]
        draft = extract_lesson_draft("/tmp/test-log.md", "content", failures)
        assert "title" in draft
        assert "Problem" in draft
        assert "Root Cause" in draft
        assert "Solution" in draft
        assert "test-log.md" in draft

    def test_frontmatter_json(self):
        failures = [{"line_no": 1, "line": "error", "context": ["error"], "pattern": "error"}]
        draft = extract_lesson_draft("/tmp/foo.md", "content", failures)
        # Extract JSON between --- markers
        parts = draft.split("---")
        assert len(parts) >= 3
        meta = json.loads(parts[1])
        assert "title" in meta
        assert meta["status"] == "draft"
        assert meta["source"] == "memory-dump-watcher"


class TestProcessFile:
    def test_nonexistent_file(self):
        result = process_file("/nonexistent/file.md")
        assert result["status"] == "error"
        assert "not found" in result["reason"]

    def test_skips_short_file(self, tmp_path):
        f = tmp_path / "short.md"
        f.write_text("too short\n")
        result = process_file(str(f))
        assert result["status"] == "skipped"
        assert "too short" in result["reason"]

    def test_skips_no_failure(self, tmp_path):
        f = tmp_path / "clean.md"
        f.write_text("word " * 100)  # 500 chars, no failure patterns
        result = process_file(str(f))
        assert result["status"] == "skipped"

    def test_extracts_from_failure(self, tmp_path):
        f = tmp_path / "error-log.md"
        content = "word " * 50 + "\nan exception was thrown during build\n" + "word " * 50
        f.write_text(content)
        result = process_file(str(f))
        assert result["status"] == "extracted"
        assert result["draft"] is not None
        assert len(result["failures"]) >= 1


class TestWatchDirectory:
    def test_nonexistent_dir(self):
        results = watch_directory("/nonexistent/dir")
        assert len(results) == 1
        assert results[0]["status"] == "error"

    def test_watches_files(self, tmp_path):
        # Create test files
        (tmp_path / "good.md").write_text("word " * 50 + "\nerror happened\n" + "word " * 50)
        (tmp_path / "skip.md").write_text("too short")
        (tmp_path / "ignore.txt").write_text("word " * 50 + "\nerror happened\n" + "word " * 50)

        results = watch_directory(str(tmp_path), pattern="*.md")
        files = {r["file"]: r["status"] for r in results}
        assert any("good.md" in f and s == "extracted" for f, s in files.items())
        assert any("skip.md" in f and s == "skipped" for f, s in files.items())
        # .txt files should be excluded by *.md pattern
        assert not any("ignore.txt" in f for f in files)

    def test_custom_pattern(self, tmp_path):
        (tmp_path / "log.txt").write_text("word " * 50 + "\nerror occurred\n" + "word " * 50)
        results = watch_directory(str(tmp_path), pattern="*.txt")
        assert any(r["status"] == "extracted" for r in results)