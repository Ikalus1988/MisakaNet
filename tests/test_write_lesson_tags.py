#!/usr/bin/env python3
"""`write_lesson` takes the tag form both surfaces have advertised (#4383).

The #4383 gate compares the two surfaces' schemas and reported a real divergence: the hosted tool
advertises `tags: {type: "string"}` ("Comma-separated tags"), while the stdio tool advertised an
array and did `", ".join(tags)`. An agent that read the hosted schema and passed `"pip, network"`
to the local server got `p, i, p, ,, ...` in the queued lesson.

The fix is the hosted definition: the schema says string, and the handler normalises. An array is
still accepted because this surface advertised one for months — refusing it would turn a contract
fix into a breaking change for existing callers.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from misakanet.server.handlers.write import _tag_text, handle_write_lesson


def test_a_comma_separated_string_is_kept_and_trimmed():
    assert _tag_text("pip, network , proxy") == "pip, network, proxy"


def test_an_array_is_still_accepted_for_older_callers():
    assert _tag_text(["pip", " network", ""]) == "pip, network"


def test_none_and_empty_are_empty_not_the_string_none():
    assert _tag_text(None) == ""
    assert _tag_text("") == ""
    assert _tag_text([]) == ""
    assert _tag_text(" , ,") == ""


def test_a_non_ascii_tag_survives():
    """The queue file this becomes is written with an explicit encoding (#4382)."""
    assert _tag_text("代理, 网络") == "代理, 网络"


def _lesson_args(**overrides):
    args = {
        "title": "pip install times out behind a proxy",
        "domain": "python",
        "problem": "pip install hangs until the default timeout.",
        "root_cause": "The proxy does not forward the default index and pip never retries.",
        "fix": "Raise --timeout and pin the index URL.",
        "token": "mcp_testtoken",
    }
    args.update(overrides)
    return args


@pytest.mark.parametrize("tags, expected", [
    ("pip, network", "pip, network"),
    (["pip", "network"], "pip, network"),
    ("", "none"),
])
def test_the_queued_message_carries_the_flat_tag_text(tags, expected):
    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return {"id": "contrib_1", "quality_score": 90, "status": "pending"}

    with patch("scripts.contribution_queue.submit_contribution", fake_submit):
        result = handle_write_lesson(_lesson_args(tags=tags))

    assert result["submitted"] is True, result
    assert f"Tags: {expected}" in captured["message"], captured["message"].splitlines()[:6]
