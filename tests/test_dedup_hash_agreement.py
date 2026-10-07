#!/usr/bin/env python3
"""The dedup hash must be the *same function* on both sides of the boundary.

`misakanet_submit_intake` promises the reporter this: re-call it with the same problem text and the
maintainer's answer comes back. That promise is carried by exactly one value — `dedup_hash` — which
the worker computes when the report arrives and `scripts/sync_answered_questions.py` recomputes from
the issue body afterwards. If the two disagree even slightly, the answer is in D1 and unreachable.

It happened twice, independently, and neither was visible from the log line:

1. **Length.** `parse_kind_and_problem` returned `problem[:2000]`, `error[:1000]` while the worker
   hashed the whole submission. Any intake over the cap stored a hash nothing could reproduce.
2. **Astral characters.** The Python loop walked code points; the worker's `charCodeAt` walks UTF-16
   code units. A single `👇` (U+1F447) is one step in Python and two in JS.

Measured across all 86 question-kind intakes on 2026-10-07, six had an unreachable hash: #2818,
#2821, #2833, #2834, #2844 and #2981 (#2983).

This gate runs the worker's *own* `hashString`, extracted from its source, rather than restating it
in Python — a second implementation here would be a second set of answers to the same question, and
would agree with whichever one it was copied from.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from sync_answered_questions import fnv1a_hex, parse_kind_and_problem  # noqa: E402

WORKER = REPO / "workers" / "register-proxy-sw.js"

# A test that only used short ASCII would have passed while both defects were live, which is how
# they survived. Each fixture below crosses one of the two boundaries on purpose.
LONG_PROBLEM = "the misakanet dsh mcp intake sidebar fragment is alive " * 400   # > 2000 chars
ASTRAL = "see the reproduction below 👇 and retry ✨"          # U+1F447, U+2728
CJK_EXT_B = "扩展字 𠀀"                               # above U+FFFF

FIXTURES = {
    "ascii": "pip install timeout behind corporate proxy",
    "cjk in the BMP": "企业代理下 pip 安装超时",
    "longer than the old cap": LONG_PROBLEM,
    "the character that broke it": ASTRAL,
    "cjk extension B": CJK_EXT_B,
    "empty error field": "",
}


def _worker_hash(text: str) -> str:
    """Ask the worker's own `hashString`, lifted out of the worker source."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node unavailable; the JS half cannot be evaluated here")
    program = """
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const fn = src.match(/function hashString\\(str\\) \\{[\\s\\S]*?\\n\\}/);
if (!fn) { throw new Error('hashString not found in the worker source'); }
eval(fn[0]);
process.stdout.write(hashString(JSON.parse(process.argv[2])));
"""
    done = subprocess.run(
        [node, "-e", program, str(WORKER), json.dumps(text)],
        capture_output=True, text=True,
    )
    assert done.returncode == 0, f"could not run the worker's hashString: {done.stderr}"
    return done.stdout.strip()


@pytest.mark.parametrize("label", sorted(FIXTURES))
def test_both_implementations_agree(label):
    text = FIXTURES[label]
    assert fnv1a_hex(text) == _worker_hash(text), (
        "the sync script and the worker disagree on the dedup hash for this input, so a "
        "re-submission can never find the row holding the answer"
    )


def test_the_worker_source_still_contains_the_function_being_mirrored():
    # A rename or an inline refactor would leave the comparison above silently testing a stale
    # regex match. This fails loudly instead.
    assert re.search(r"function hashString\(str\) \{", WORKER.read_text(encoding="utf-8")), (
        "workers/register-proxy-sw.js no longer defines hashString(str); the gate is mirroring a "
        "function that no longer exists"
    )


# ── the whole path, from an issue body to the hash the worker would compute ──

def _worker_dedup_hash(kind: str, problem: str, error: str) -> str:
    # Exactly the expression at workers/register-proxy-sw.js:4156.
    return _worker_hash(f"{kind}:{problem.strip()}:{error.strip()}")


def test_an_overlong_intake_gets_a_hash_the_worker_can_reproduce():
    body = f"**Kind:** question\n\n## Problem\n{LONG_PROBLEM}\n\n## Error\n\n"
    kind, problem, error = parse_kind_and_problem(body)
    assert len(problem) > 2000, "fixture no longer crosses the old cap; it cannot catch the defect"
    assert fnv1a_hex(f"{kind}:{problem}:{error}".strip()) == _worker_dedup_hash(kind, problem, error)


def test_an_emoji_in_a_reported_problem_gets_a_hash_the_worker_can_reproduce():
    body = f"**Kind:** question\n\n## Problem\n{ASTRAL}\n\n---\n_Submitted via remote MCP._\n"
    kind, problem, error = parse_kind_and_problem(body)
    assert any(ord(c) > 0xFFFF for c in problem), "fixture lost its astral character"
    assert fnv1a_hex(f"{kind}:{problem}:{error}".strip()) == _worker_dedup_hash(kind, problem, error)


def test_the_real_reporter_text_round_trips():
    """The actual strings that produced unreachable hashes on 2026-10-07."""
    for text in (
        "see the reproduction below 👇 and retry ✨",
        LONG_PROBLEM,
        "扩展字 𠀀 mixed with ascii",
    ):
        assert fnv1a_hex(f"question:{text}:") == _worker_hash(f"question:{text}:"), (
            f"unreachable hash for a real intake shape: {text[:40]!r}…"
        )


# ── the error field, and the path with no `## Problem` section ──────────────
#
# Both were uncovered by the first version of this file. The mutation run said so: restoring
# `error[:1000]`, and restoring the `[:2000]` in the fallback branch, both left the gate green.
# Neither cap was load-bearing — `questions.problem` is a SQLite `TEXT` column — and a cap on a
# hash input has a second, worse consequence than an unreachable hash, which the two tests below
# pin.

def test_two_reports_sharing_a_long_prefix_do_not_collapse_to_one_hash():
    """Truncation does not merely hide a row — it makes two different reports *the same report*.

    With a `[:2000]` cap, two intakes that agree on their first 2,000 characters hash identically,
    so the second reporter is handed the first reporter's answer. That is worse than the
    unreachable-hash case: it answers the wrong person.
    """
    shared = "shared opening that runs past the old cap " * 100
    first, second = f"{shared}first reporter", f"{shared}second reporter"

    assert len(shared) > 2000, "fixture no longer crosses the old cap"
    assert fnv1a_hex(first) != fnv1a_hex(second), (
        "two distinct reports sharing a long prefix hash to the same value, so the dedup path "
        "would treat them as one intake"
    )


def test_a_long_error_is_hashed_in_full_and_stays_distinct():
    body_template = "**Kind:** question\n\n## Problem\nshort\n\n## Error\n{error}"
    first, second = body_template.format(error="E" * 2500 + "A"), body_template.format(error="E" * 2500 + "B")

    kind, problem, first_error = parse_kind_and_problem(first)
    _, _, second_error = parse_kind_and_problem(second)

    assert len(first_error) > 1000, "fixture no longer crosses the old 1,000-char cap"
    assert first_error != second_error, "the two error fields came back identical"
    assert fnv1a_hex(f"{kind}:{problem}:{first_error}".strip()) != \
           fnv1a_hex(f"{kind}:{problem}:{second_error}".strip())


def test_the_fallback_path_does_not_truncate_or_collide():
    """A body with no `## Problem` heading takes the fallback branch, which had its own `[:2000]`."""
    shared = "body without a Problem heading, past the cap " * 90
    first = f"**Kind:** question\n**Source:** github\n\n{shared}first"
    second = f"**Kind:** question\n**Source:** github\n\n{shared}second"

    _, first_problem, _ = parse_kind_and_problem(first)
    _, second_problem, _ = parse_kind_and_problem(second)

    assert "Source" not in first_problem, "fixture stopped taking the fallback branch"
    assert first_problem != second_problem, (
        "the fallback branch truncated both bodies to the same prefix, so two different reports "
        "become one dedup row"
    )