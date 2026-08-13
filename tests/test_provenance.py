import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lint_requires_published_provenance():
    lint = _load(ROOT / "scripts/lesson_lint.py", "lesson_lint_provenance")
    content = '{"title":"Example Lesson","domain":"python","status":"published"}\n# Example\n\n' + ('body\n' * 12)
    rules = {item["rule"] for item in lint.check_provenance(content, Path("example.md"))}
    assert {"invalid_provenance_source", "missing_author", "missing_edited_at", "missing_merged_by"} <= rules


def test_backfill_preserves_existing_values(tmp_path):
    backfill = _load(ROOT / "scripts/backfill_provenance.py", "backfill_provenance")
    path = tmp_path / "lesson.md"
    path.write_text('{"title":"Example","source":"pr","author":"Ada","pr":7,"edited_at":"2026-01-01","merged_by":"Maintainer"}\n# Example\n\nBody\n', encoding="utf-8")
    result = backfill.update_file(path, write=False)
    assert result["status"] == "ok"
    assert result["fields"] == {}


def test_backfill_dry_run_reports_missing_fields(tmp_path):
    backfill = _load(ROOT / "scripts/backfill_provenance.py", "backfill_provenance_dry")
    path = tmp_path / "lesson.md"
    path.write_text('{"title":"Example","source":"unknown"}\n# Example\n\nBody\n', encoding="utf-8")
    backfill.REPO = tmp_path
    result = backfill.update_file(path, write=False)
    assert result["status"] == "changed"
    assert {"author", "source", "edited_at", "merged_by"} <= set(result["fields"])


def test_backfill_write_preserves_fenced_frontmatter(tmp_path):
    backfill = _load(ROOT / "scripts/backfill_provenance.py", "backfill_provenance_fenced")
    path = tmp_path / "lesson.md"
    path.write_text(
        '---\n{"title":"Example","source":"unknown"}\n---\n\n# Example\n\nBody\n',
        encoding="utf-8",
    )
    backfill.REPO = tmp_path
    result = backfill.update_file(path, write=True)
    written = path.read_text(encoding="utf-8")
    assert result["status"] == "changed"
    assert written.startswith("---\n")
    assert "\n---\n\n# Example" in written
    assert '"source": "manual"' in written


def test_sag_index_round_trips_provenance(tmp_path):
    sag = _load(ROOT / "scripts/build_sag_index.py", "build_sag_index_provenance")
    okf_dir = tmp_path / "okf"
    okf_dir.mkdir()
    (okf_dir / "lessons.jsonl").write_text(
        json.dumps({
            "title": "Timeout recovery",
            "description": "Recover a network timeout safely",
            "tags": ["network"],
            "domain": "devops",
            "source": "pr",
            "status": "published",
            "path": "lessons/core/timeout.md",
            "author": "Ada",
            "pr": 42,
            "edited_at": "2026-01-01T00:00:00Z",
            "merged_by": "Maintainer",
        }) + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "sag.db"
    assert sag.build_index(okf_dir, db_path) == 1
    result = sag.search(db_path, "timeout", top=1)[0]
    assert result["author"] == "Ada"
    assert result["pr"] == "42"
    assert result["source"] == "pr"
