#!/usr/bin/env python3
"""The onboarding examples must be questions the corpus actually answers — 2026-09-15/16.

Both installers end by telling a new user *which question to ask first*, because that is the one
thing they will judge the whole thing on. History, so the same mistake is not made a third time:

* it used to be ``docker exit code 137``, which the corpus answers with three only loosely related
  lessons (top hit: ``kubernetes-crashloopbackoff-debugging``) — the first question we chose for
  them landed on a near-miss (found by the three-agent chain test; issue #1718);
* then ``pip install timeout``, which answers well but made the corpus look one topic deep, and it
  aged into "the pip problem" rather than something a user would actually hit next.

It is now **three** examples, chosen to be different kinds of failure, and all three are
*distinctive fragments* rather than sentences — because asking in natural language ("如何切换识图模型")
returns nothing: the corpus is indexed by error text and keywords, which is exactly what the rules
block tells the agent to send. The examples therefore teach the usage while demonstrating the value.

Three properties keep this honest:

1. the examples live in **one constant per installer** (they used to be copy-pasted into eight
   places, which is how they drifted out of sync with the corpus);
2. the corpus' answer to *each* of them is **checked offline** — changing an example means
   re-running this test, and the "top hit must be about the query" rule is what refuses an example
   that would repeat the near-miss;
3. a query that only looks general is not enough: ``no space left on device`` reads perfectly
   general and answers well over the network, but its top hit's *title* is not about the query, so
   it fails rule 2 and is not used.

Offline by construction: it searches the checked-in corpus through the same engine the local CLI
uses, so CI needs no network.
"""
import json
import re
from pathlib import Path

from misakanet.search.engine import MisakaNetSearchEngine

REPO = Path(__file__).resolve().parent.parent
JS_INSTALLER = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
PY_INSTALLER = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"

# Re-calibrate deliberately: change these, run the test, and look at what the corpus answers.
EXPECTED_QUERIES = [
    "switch vision model",            # the topic the user asked for by name
    "context window exceeded",        # long sessions, the failure every agent user meets
    "tool call permission denied",    # tools/permissions, the other one they all meet
]


def _extract_list(path: Path, pattern: str) -> list[str]:
    found = re.search(pattern, path.read_text(encoding="utf-8"), re.M)
    assert found, f"{path.name}: ONBOARDING_QUERIES is not defined"
    return json.loads(found.group(1))


def test_both_installers_define_the_same_onboarding_examples():
    js = _extract_list(JS_INSTALLER, r"const ONBOARDING_QUERIES = (\[[^\]]+\]);")
    py = _extract_list(PY_INSTALLER, r"^ONBOARDING_QUERIES = (\[[^\]]+\])$")
    assert js == py, f"the two installers disagree: {js!r} vs {py!r}"
    assert js == EXPECTED_QUERIES, (
        f"the examples changed to {js!r}: re-run this test, check that the corpus answers each of "
        "them with a lesson about that very failure, then update EXPECTED_QUERIES here"
    )
    assert len(js) == 3, "three examples, so a new user does not judge the corpus on one topic"


def test_the_examples_are_not_copied_back_into_the_messages():
    """Eight copies is how the examples drifted; each constant has to stay the only place."""
    for path in (JS_INSTALLER, PY_INSTALLER):
        text = path.read_text(encoding="utf-8")
        for query in EXPECTED_QUERIES:
            occurrences = text.count(query)
            assert occurrences == 1, (
                f"{path.name}: {query!r} appears {occurrences}× — the messages must interpolate "
                "ONBOARDING_QUERIES instead of repeating the text"
            )


def test_the_corpus_answers_every_onboarding_example_with_a_lesson_about_it():
    engine = MisakaNetSearchEngine()
    for query in EXPECTED_QUERIES:
        hits = engine.search(query, top=3)
        assert hits, f"no lesson answers the onboarding example {query!r}"

        top = hits[0]
        haystack = f"{top.get('title', '')} {top.get('path', '')}".lower()
        tokens = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) >= 4]
        assert tokens, f"{query!r} has no distinctive token to check"
        matched = [w for w in tokens if w in haystack]
        assert matched, (
            "the first lesson a new user sees is not about the question we told them to ask:\n"
            f"  query:    {query!r}\n"
            f"  top hit:  {top.get('path')} — {top.get('title')}\n"
            "Pick an example whose top hit is a lesson about that failure (issue #1718)."
        )
