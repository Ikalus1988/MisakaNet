#!/usr/bin/env python3
"""The onboarding example question must be one the corpus actually answers — 2026-09-15.

Both installers end by telling a new user *which question to ask first*, because that is the
one thing they will judge the whole thing on. It used to be ``docker exit code 137``, and the
corpus answers that with three only loosely related lessons (top hit:
``kubernetes-crashloopbackoff-debugging``) — so the first question, the one we chose for them,
landed on a near-miss (found by the three-agent chain test; issue #1718).

Two properties keep that from happening again:

1. the example lives in **one constant per installer** (it used to be copy-pasted into eight
   places, which is how it drifted out of sync with the corpus), and
2. the corpus' answer to it is **pinned and checked offline** — the pin is deliberate: changing
   the example means re-running this test, and the "top hit must be about the query" rule is
   what refuses a pin that would repeat the near-miss.

Offline by construction: it searches the checked-in corpus through the same engine the local
CLI uses, so CI needs no network.
"""
import re
from pathlib import Path

from misakanet.search.engine import MisakaNetSearchEngine

REPO = Path(__file__).resolve().parent.parent
JS_INSTALLER = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
PY_INSTALLER = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"

# Re-calibrate deliberately: change this, run the test, and look at what the corpus answers.
EXPECTED_QUERY = "pip install timeout"


def _extract(path: Path, pattern: str) -> str:
    found = re.search(pattern, path.read_text(encoding="utf-8"), re.M)
    assert found, f"{path.name}: ONBOARDING_QUERY is not defined"
    return found.group(1)


def test_both_installers_define_the_same_onboarding_query():
    js = _extract(JS_INSTALLER, r"const ONBOARDING_QUERY = '([^']+)'")
    py = _extract(PY_INSTALLER, r'^ONBOARDING_QUERY = "([^"]+)"')
    assert js == py, f"the two installers disagree: {js!r} vs {py!r}"
    assert js == EXPECTED_QUERY, (
        f"the example changed to {js!r}: re-run this test, check that the corpus answers it with "
        "a lesson about that very failure, then update EXPECTED_QUERY here"
    )


def test_the_example_is_not_copied_back_into_the_messages():
    """Eight copies is how the example drifted; the constant has to stay the only place."""
    for path in (JS_INSTALLER, PY_INSTALLER):
        occurrences = path.read_text(encoding="utf-8").count(EXPECTED_QUERY)
        assert occurrences == 1, (
            f"{path.name}: {EXPECTED_QUERY!r} appears {occurrences}× — the messages must "
            "interpolate the ONBOARDING_QUERY constant instead of repeating the text"
        )


def test_the_corpus_answers_the_onboarding_example_with_a_lesson_about_it():
    hits = MisakaNetSearchEngine().search(EXPECTED_QUERY, top=3)
    assert hits, f"no lesson answers the onboarding example {EXPECTED_QUERY!r}"

    top = hits[0]
    haystack = f"{top.get('title', '')} {top.get('path', '')}".lower()
    tokens = [w for w in re.findall(r"[a-z0-9]+", EXPECTED_QUERY.lower()) if len(w) >= 4]
    assert tokens, f"{EXPECTED_QUERY!r} has no distinctive token to check"
    matched = [w for w in tokens if w in haystack]
    assert matched, (
        "the first lesson a new user sees is not about the question we told them to ask:\n"
        f"  query:    {EXPECTED_QUERY!r}\n"
        f"  top hit:  {top.get('path')} — {top.get('title')}\n"
        "Pick an example whose top hit is a lesson about that failure (issue #1718)."
    )
