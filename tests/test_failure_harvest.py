#!/usr/bin/env python3
"""Tests for failure_harvest P0 clustering (failure → draft lesson skeleton).

Locks the fixes from the P0 demo regression:
- specific error-class kind clusters by class only (pip 3 phrasings → 1 draft);
- 401/fatal are *weak* signals, not cluster keys (git "401" + "fatal:" → 1 draft);
- URL-stripping + R-stack drop keep stack sets stable across phrasings;
- noise / low-signal events never produce drafts.
"""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.failure_harvest import (  # noqa: E402
    classify,
    cluster_key,
    harvest,
    norm_stack,
    safe_filename,
)

PIP_VARIANTS = [
    "pip install ReadTimeoutError behind corporate proxy while reading from pypi",
    "ERROR: Could not install packages due to an OSError ReadTimeoutError proxy pypi pip",
    "pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool proxy timeout pip",
]
GIT_VARIANTS = [
    "git credential helper 401 credential lookup failed github helper path mismatch",
    "fatal: could not read Username for 'https://github.com': credential helper misconfigured git",
]
CF_VARIANTS = [
    "ReferenceError: env.MISAKANET_KV is undefined cloudflare worker kv binding",
    "ReferenceError: KV namespace binding missing in cloudflare workers env",
]


# ── classify ─────────────────────────────────────────────
def test_classify_takes_last_inner_class_and_strips_module_path():
    # 3 phrasings of the same family must land on the same specific class
    kinds = {classify(e)[0] for e in PIP_VARIANTS}
    assert kinds == {"ReadTimeoutError"}
    for e in PIP_VARIANTS:
        assert classify(e)[1] is True  # specific → clusterable by class


def test_classify_http_code_and_fatal_are_weak_signals():
    kind, specific, signals = classify(GIT_VARIANTS[0])
    assert kind == "http-401" and specific is False and "401" in signals
    kind2, spec2, sig2 = classify(GIT_VARIANTS[1])
    assert kind2 == "fatal" and spec2 is False and "fatal" in sig2


def test_classify_generic_failure_for_rust_borrow():
    kind, specific, signals = classify("error[E0308] borrow checker rust cargo")
    assert kind == "generic-failure" and specific is False and signals == []


# ── norm_stack ───────────────────────────────────────────
def test_norm_stack_strips_url_and_drops_r_false_positive():
    # "https://github.com" would hit web via http; "helper "/"for " would hit R
    assert norm_stack(GIT_VARIANTS[1]) == ("git",)
    assert norm_stack("git rebase conflict on branch main") == ("git",)
    assert "r" not in norm_stack("credential helper 401 github")


def test_norm_stack_python_for_pip():
    assert "python" in norm_stack(PIP_VARIANTS[0])


# ── cluster_key ──────────────────────────────────────────
def test_cluster_key_specific_ignores_stack():
    assert cluster_key(("git",), "ReadTimeoutError", True) == "K:ReadTimeoutError"
    assert cluster_key(("python", "web"), "ReadTimeoutError", True) == "K:ReadTimeoutError"


def test_cluster_key_generic_uses_stack():
    assert cluster_key(("git",), "http-401", False) == "G:generic|git"
    assert cluster_key(("git",), "fatal", False) == "G:generic|git"
    assert cluster_key(("rust",), "generic-failure", False) == "G:generic|rust"


# ── safe_filename ────────────────────────────────────────
def test_safe_filename_removes_colon_pipe():
    assert safe_filename("K:ReadTimeoutError") == "K-ReadTimeoutError"
    assert safe_filename("G:generic|git") == "G-generic-git"


# ── harvest end-to-end ───────────────────────────────────
def _demo_events():
    events = []
    for e in PIP_VARIANTS:
        events.append({"error": e, "source": "pilot-a"})
    for e in GIT_VARIANTS:
        events.append({"error": e, "source": "pilot-b", "what_tried": "checked credential.helper path"})
    for e in CF_VARIANTS:
        events.append({"error": e, "source": "pilot-a"})
    events += [
        {"error": "https://example.com/foo", "source": "pilot-a"},          # noise
        {"error": "it broke", "source": "pilot-b"},                          # noise
        {"error": "error[E0308] borrow checker rust cargo", "source": "pilot-c"},  # low signal
    ]
    return events


def test_harvest_three_families_one_draft_each(tmp_path):
    s = harvest(_demo_events(), tmp_path, min_occ=2)
    assert s["events"] == 10 and s["cleaned_noise"] == 2
    kinds = {d["kind"] for d in s["drafts"]}
    assert kinds == {"ReadTimeoutError", "http-401", "ReferenceError"}
    by_kind = {d["kind"]: d for d in s["drafts"]}
    assert by_kind["ReadTimeoutError"]["occurrences"] == 3   # 3 phrasings merged
    assert by_kind["http-401"]["occurrences"] == 2           # 401 + fatal merged
    # only rust singleton skipped as low signal
    assert [x["reason"] for x in s["skipped"]] == ["low signal (occ=1 < 2)"]


def test_harvest_writes_drafts_with_weak_signals_in_patterns(tmp_path):
    s = harvest(_demo_events(), tmp_path, min_occ=2)
    git_file = tmp_path / "G-generic-git.md"
    assert git_file.exists()
    body = git_file.read_text(encoding="utf-8")
    fm = json.loads(body.split("---")[1])
    assert fm["failure_patterns"] == ["http-401", "401", "fatal", "git"]
    assert "fatal: could not read Username" in body       # variant preserved
    assert "checked credential.helper path" in body       # what_tried preserved
