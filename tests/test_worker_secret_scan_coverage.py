#!/usr/bin/env python3
"""The worker credential gate has to *reach* the worker code, not merely run (#2684).

`scripts/check_worker_secrets.py` is a blocking required check, and for its whole life it globbed
`workers/**/*.js` — while `workers/` holds 69 `.mjs` files against 5 `.js` ones. It was scanning six
percent of the tree and reporting a clean bill of health, which is worse than not running: the check
run said "covered".

The existing tests in `test_published_secrets_scan.py` cover the *prose* gate's patterns and its CI
wiring. Neither could have caught this, and neither is where it belongs: the defect is in which files
this scanner collects, so the test has to assert on collection. The real tree cannot answer that
question — it is clean under both globs — so these tests use a temp directory.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.check_worker_secrets import (  # noqa: E402
    SCAN_SUFFIXES,
    scan_credential_patterns,
    worker_source_files,
)

# A GitHub PAT shape, spelled out rather than copied from a real leak. `check_worker_secrets.py`
# reports file/line/kind and never the matched text, so a literal here would be inert either way —
# but keeping it obviously synthetic means it can never be mistaken for a credential that needs
# rotating.
FAKE_PAT = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _probe(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_text(f'const key = "{FAKE_PAT}";\n', encoding="utf-8")
    return path


def _in_repo_tree():
    """A scratch directory inside the repository.

    `scan_credential_patterns` labels its findings with `filepath.relative_to(REPO)` and raises
    outside it, so a probe under `tmp_path` cannot be scanned. The directory is not under `workers/`,
    which keeps the real-tree test below from seeing it, and the context manager removes it even if
    an assertion fails.
    """
    return tempfile.TemporaryDirectory(dir=REPO, prefix=".secret-scan-probe-")


def test_the_scan_reaches_dot_mjs():
    """The regression itself: a credential in a `.mjs` file is found end to end."""
    with _in_repo_tree() as scratch:
        workers = Path(scratch) / "workers"
        workers.mkdir()
        probe = _probe(workers, "handler.mjs")

        found = {p.name for p in worker_source_files(workers)}
        assert "handler.mjs" in found, f"`.mjs` is not collected at all: {found}"

        hits = [
            hit
            for path in worker_source_files(workers)
            for hit in scan_credential_patterns(path)
        ]
        assert hits, f"a credential in {probe.name} was collected but not flagged"
        assert any(probe.name in str(hit.get("file", "")) for hit in hits), hits


def test_dot_js_is_still_reached(tmp_path):
    """Both extensions, so a future edit cannot trade one for the other."""
    workers = tmp_path / "workers"
    workers.mkdir()
    _probe(workers, "legacy.js")

    found = {path.name for path in worker_source_files(workers)}
    assert found == {"legacy.js"}, found


def test_the_suffixes_match_the_worker_tree(tmp_path):
    """`workers/` is overwhelmingly `.mjs`; if a new language lands, the tuple is the one place to
    add it, and this is what makes the tuple mean something."""
    workers = tmp_path / "workers"
    (workers / "nested" / "deeper").mkdir(parents=True)
    names = ["a.js", "b.mjs", "nested/c.mjs", "nested/deeper/d.mjs", "notes.md", "data.json"]
    for name in names:
        (workers / name).write_text("// nothing here\n", encoding="utf-8")

    found = {p.relative_to(workers).as_posix() for p in worker_source_files(workers)}

    assert found == {
        "a.js", "b.mjs", "nested/c.mjs", "nested/deeper/d.mjs",
    }, f"unexpected discovery set: {sorted(found)}"
    assert ".mjs" in SCAN_SUFFIXES and ".js" in SCAN_SUFFIXES, SCAN_SUFFIXES


def test_the_real_worker_tree_is_clean(tmp_path):
    """The widened glob must not turn the gate permanently red, or it gets muted and the original
    defect returns with company. 70 `.mjs` files is a lot of newly-read text; this is the check
    that they are all clean."""
    workers = REPO / "workers"
    if not workers.exists():  # pragma: no cover - only in a stripped checkout
        return

    hits = [
        hit
        for path in worker_source_files(workers)
        for hit in scan_credential_patterns(path)
    ]

    assert hits == [], (
        "the widened scan reads files it did not read before, and something in there is flagged: "
        + "; ".join(f"{h.get('file')}:{h.get('line')} {h.get('type')}" for h in hits)
    )
