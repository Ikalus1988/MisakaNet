"""Query-intent routing must not swallow ordinary error text (#3001).

`EVIDENCE_INTENT_RE` used to carry a bare `usage` alternative. Any query containing the word
matched it — and the word is everywhere in CLI error text (`npm usage error`,
`Usage: pip install <pkg>`). An evidence-intent query then runs
`filterByKind(results, "evidence")`, and an FAQ row (what `matchAnsweredQuestions` returns) has no
`evidence_level` and no `evidence_refs`, so `isEvidenceResult` is false for it and **every**
answered-question hit was filtered out. A question containing "usage" lost its FAQ entirely.

These tests evaluate the constant **as it is written in the worker**, not a copy of it: the regex
literal is extracted from the source and handed to node. A copy in this file would keep passing
after someone edits the worker.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"

# Queries that are about *how often something was used* — the intent `usage` was there for.
SHOULD_BE_EVIDENCE = [
    "usage count",
    "usage of this lesson",
    "引用次数",
    "被用过",
    "多少人用过",
    "evidence please",
    "verification",
]

# Queries where "usage" is part of the error text and nothing else. These must NOT route to
# evidence — this is the regression #3001 is about.
SHOULD_NOT_BE_EVIDENCE = [
    "npm usage error",
    "docker usage: invalid reference",
    "Usage: pip install <pkg>",
    "usage: missing required argument",
    "how do I fix this usage error",
]


def _evidence_regex() -> str:
    src = WORKER.read_text(encoding="utf-8")
    m = re.search(r"const EVIDENCE_INTENT_RE = /(.*?)/i;", src, re.S)
    assert m, "EVIDENCE_INTENT_RE is not declared in the expected form"
    return m.group(1)


@pytest.fixture(scope="module")
def routes_to_evidence() -> dict[str, bool]:
    """Ask node to run the shipped regex, so JS semantics are the ones under test."""
    pattern = _evidence_regex()
    script = (
        f"const re = new RegExp({json.dumps(pattern)}, 'i');"
        "const qs = JSON.parse(process.argv[1]);"
        "console.log(JSON.stringify(qs.map(q => re.test(q))));"
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(SHOULD_BE_EVIDENCE + SHOULD_NOT_BE_EVIDENCE)],
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
    flags = json.loads(out.stdout)
    queries = SHOULD_BE_EVIDENCE + SHOULD_NOT_BE_EVIDENCE
    return dict(zip(queries, flags))


@pytest.mark.parametrize("query", SHOULD_BE_EVIDENCE)
def test_usage_intent_still_routes_to_evidence(routes_to_evidence, query):
    assert routes_to_evidence[query] is True, (
        f"{query!r} asks how often something was used — anchoring `usage` must not lose it"
    )


@pytest.mark.parametrize("query", SHOULD_NOT_BE_EVIDENCE)
def test_error_text_containing_usage_does_not_route_to_evidence(routes_to_evidence, query):
    """The regression: this routed to evidence, which then filtered the whole FAQ corpus away."""
    assert routes_to_evidence[query] is False, (
        f"{query!r} is ordinary error text; routing it to evidence zeroes the FAQ results"
    )


def test_an_faq_row_has_no_evidence_metadata_so_this_actually_matters():
    """Pin the second half of the chain, so the test above cannot pass for the wrong reason."""
    src = WORKER.read_text(encoding="utf-8")
    block = re.search(
        r"return scored\.slice\(0, top\)\.map\(\(\{ row, score, desc, answerShown \}\) => \(\{(.*?)\n  \}\)\);",
        src, re.S,
    )
    assert block, "could not locate the FAQ result shape in matchAnsweredQuestions"
    fields = set(re.findall(r"^\s{4}(\w+):", block.group(1), re.M))
    assert "evidence_level" not in fields, (
        "FAQ rows now carry evidence_level; if that was deliberate, revisit the routing test"
    )
    assert "evidence_refs" not in fields, (
        "FAQ rows now carry evidence_refs; if that was deliberate, revisit the routing test"
    )