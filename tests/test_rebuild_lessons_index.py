#!/usr/bin/env python3
"""Tests for scripts/rebuild_lessons_index.py."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "rebuild_lessons_index.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO, capture_output=True, text=True,
    )


def test_check_passes_after_rebuild():
    """--check returns 0 right after a rebuild."""
    run()  # rebuild first
    r = run("--check")
    assert r.returncode == 0, f"expected 0, got {r.returncode}\n{r.stderr}"


def test_check_fails_on_stale_index():
    """--check returns 1 when the index drifts from the corpus."""
    index = REPO / "lessons" / "index.md"
    original = index.read_text()
    try:
        # Inject a fake entry
        index.write_text(original + "\n- [Fake](core/nonexistent.md) | test | | \n")
        r = run("--check")
        assert r.returncode == 1, f"expected 1, got {r.returncode}"
        assert "out of sync" in r.stderr
    finally:
        index.write_text(original)


def test_deterministic_output():
    """Two consecutive rebuilds produce byte-identical output."""
    run()
    md5_1 = (REPO / "lessons" / "index.md").read_bytes()
    run()
    md5_2 = (REPO / "lessons" / "index.md").read_bytes()
    assert md5_1 == md5_2, "output is not deterministic"


def test_all_corpus_files_covered():
    """Every .md lesson file (except skips) appears in the rebuilt index."""
    index_content = (REPO / "lessons" / "index.md").read_text()
    skip = {"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"}
    for subdir in ("core", "contrib", "en"):
        d = REPO / "lessons" / subdir
        if not d.is_dir():
            continue
        for md in sorted(d.glob("*.md")):
            if md.name in skip:
                continue
            rel = str(md.relative_to(REPO / "lessons"))
            assert rel in index_content, f"missing from index: {rel}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:
                print(f"FAIL: {e}")