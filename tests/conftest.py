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
