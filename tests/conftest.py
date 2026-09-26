"""Shared test configuration.

Two of this repository's data files are *logs about the repository itself*, and a test that drives the
real handlers used to append to them:

* `data/search_gaps.jsonl` — the queries that returned nothing, which is how "which lessons are missing"
  is decided locally (`scripts/demand_board.py`). It had reached 278 rows whose largest entries were test
  traffic: `quantum computing error correction` ×105, `draft test lesson` ×49.
* `data/contribution_queue.jsonl` — contributions awaiting a decision. It had reached 522 rows, 520 of
  them fixtures (`source: contract-test` 381, `mcp-agent` 134), every one still `pending`.

Both are gitignored, so nothing leaked into the repository's history — which is exactly why this went
unnoticed for as long as it did, and why the fix belongs here rather than in the two tests that happened
to be the writers. Redirecting them **for the whole session** means a test written next month cannot
reintroduce it either: the failure was never "a test forgot to patch a constant", it was "nothing made
writing into the checkout impossible".

`tests/test_no_test_writes_repo_data.py` asserts this redirection is live and that a real write through
each handler leaves the repository's copies untouched.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Fix Windows console encoding for emoji output
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Set at *import* time, before any test module imports the handlers: both modules resolve their path into
# a module-level constant when they are imported, so an env var set by a fixture would be too late.
# `setdefault` keeps an explicit override from the environment (a debugging run, or a test that wants a
# path of its own) working.
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="misakanet-test-data-"))
os.environ.setdefault("MISAKANET_GAP_LOG", str(TEST_DATA_DIR / "search_gaps.jsonl"))
os.environ.setdefault("MISAKANET_CONTRIBUTION_QUEUE", str(TEST_DATA_DIR / "contribution_queue.jsonl"))
# Third instance of the same defect, and the most expensive one (2026-09-26). The writers above are
# logs; this one is the *published index*: `tests/test_frontmatter_writers_agree.py` stubs `git push`
# to report success, and the success branch of `queue_lesson.write_lesson` rebuilds `data/lessons.json`
# from `lessons/`. So a suite run rewrote the checkout's index and every managed count surface
# (README, ARCHITECTURE, the site's meta tags, the issue templates, docs/_lessons_count.txt) — and
# `test_lesson_page_generator` then failed against the rewritten file, on PRs that merely added a
# lesson. Redirected at *import* time, before any test module can import the generator.
os.environ.setdefault("MISAKANET_LESSONS_INDEX", str(TEST_DATA_DIR / "lessons.json"))

# ── the checkout is not a fixture ───────────────────────────────────────────────────────────────
# The redirection above is a fix; this is the *gate* that keeps it a fix. A future test that reaches a
# real writer gets named here, in one line, instead of surfacing as drift in whatever test happens to
# read the same file later. Only cheap stat stamps are taken (26 paths, no reads), and a path counts as
# changed only if it moved *during this session*, so a dirty working tree is not reported.
def _published_surface_stamps() -> dict[str, tuple[int, int] | None]:
    """Size and mtime of every published surface a test must never rewrite."""
    from scripts.sync_lesson_count import COUNT_FILE, DOMAIN_SITES, NODE_SITES, SITES

    repo = Path(__file__).resolve().parents[1]
    paths = {s.path for s in (*SITES, *NODE_SITES, *DOMAIN_SITES)}
    paths.add(str(COUNT_FILE))
    paths.add("data/lessons.json")
    stamps: dict[str, tuple[int, int] | None] = {}
    for rel in sorted(paths):
        try:
            stat = (repo / rel).stat()
        except OSError:
            stamps[rel] = None
        else:
            stamps[rel] = (stat.st_size, stat.st_mtime_ns)
    return stamps


@pytest.fixture(autouse=True)
def _the_checkout_is_not_a_test_fixture(request):
    before = _published_surface_stamps()
    yield
    after = _published_surface_stamps()
    changed = sorted(rel for rel in before if before[rel] != after.get(rel))
    assert not changed, (
        f"{request.node.nodeid} rewrote published files in the checkout: {changed}.\n"
        "A test that edits the repository is not isolated: the damage lands in whichever test reads "
        "that file next, which is how a lesson-adding PR came to fail with 'generated pages drifted "
        "from data/lessons.json'. Give the writer a redirected path (env override, tmp_path) or stub "
        "the call — do not snapshot-and-restore, which hides the write."
    )
