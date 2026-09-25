#!/usr/bin/env python3
"""Every `fetchFromGitHub` call must name a ref, and that ref must carry that path (#1820).

The worker's last-resort reads go through `fetchFromGitHub(token, path, ref)`. That function used to
default `ref` to `"data"` — a branch `update-badges.yml` maintains for badges and a compact index — and
two callers relied on the default:

    return fetchFromGitHub(token, "data/counter.json");          // /api/counter, last resort
    return fetchFromGitHub(token, "data/pr-genius-stats.json");  // PR Genius stats, token branch

Neither path exists on `data`, measured 2026-09-25 (`contents/data/counter.json?ref=data` → 404), so
both asked for a file that is not there, got a 404, and surfaced as `502` at exactly the moment the
fallback was the only thing left. The counter's maintained copy is on `main`
(`data/counter.json`, rewritten daily by `sync-node-counter.yml`, with its own `updated` date); the
pr-genius handler's *no-token* branch had always read `main`, so one handler disagreed with itself.

The counter case has a second edge worth recording: the `data` branch does carry a `counter.json`, at
its **root**, frozen on **2026-06-01** (`{"current": 10047, "updated": "2026-06-01T02:25:00Z"}`) — that
is the stale number issue #1820 was filed about. It is not a fallback; reading it again would restore the
original defect in a different shape. Hence: no default ref, and every named (path, ref) pair is checked.

Two rules, both derived from the source rather than remembered:

1. the signature takes no default, so a call that forgets the ref is a lint-level mistake, not a silent
   read of the wrong branch;
2. every call names a ref explicitly, and a path under `main` must exist in this checkout.

A non-`main` ref cannot be verified offline (the branch is not in the working tree), so the few that
exist are listed with a reason — and the list is checked for dead entries.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKER = REPO / "workers" / "register-proxy-sw.js"

# (path, ref) pairs other than `main` that are legitimate, each with the reason it is legitimate.
OTHER_REFS: dict[tuple[str, str], str] = {
    ("lessons.json", "data"): (
        "the `data` branch keeps a compact lesson index at its root (81 KB against main's 1.26 MB "
        "`data/lessons.json` — a different artifact by design), written by update-badges.yml"
    ),
}

# `fetchFromGitHub(<anything>, "<path>"[, "<ref>"])` — the call, not the definition, and not a mention
# inside a comment: this test's own explanation quotes the broken calls, and a whole-file search would
# match those instead of the code.
CALL_RE = re.compile(
    r"fetchFromGitHub\(\s*[^,()]+,\s*\"([^\"]+)\"\s*(?:,\s*\"([^\"]+)\")?\s*\)"
)
DEF_RE = re.compile(r"async\s+function\s+fetchFromGitHub\s*\(([^)]*)\)")


def _code_lines() -> list[str]:
    """The worker's lines with comments removed — the same trap that has cost this repo four tests."""
    out = []
    for raw in WORKER.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped.startswith(("//", "*", "/*")):
            continue
        out.append(re.sub(r"//.*$", "", raw))
    return out


def calls() -> list[tuple[str, str | None]]:
    return CALL_RE.findall("\n".join(_code_lines()))


def test_the_scanner_sees_the_calls_it_is_about():
    """A regex that matched nothing would make every assertion below vacuous."""
    found = calls()
    assert len(found) >= 3, found
    assert any(path == "data/counter.json" for path, _ in found), found


def test_the_reader_has_no_default_ref():
    """A default is what made two callers read the wrong branch without saying so."""
    signature = DEF_RE.search("\n".join(_code_lines()))
    assert signature, "fetchFromGitHub is gone or renamed"
    params = signature.group(1)
    assert "ref" in params, params
    assert "=" not in params.split("ref")[1][:6], (
        f"the signature gives `ref` a default again ({params!r}) — a caller can then read a branch it "
        "never named, which is exactly #1820"
    )


def test_every_call_names_its_ref():
    unnamed = [path for path, ref in calls() if not ref]
    assert unnamed == [], (
        f"these calls do not name a ref: {unnamed}. Say which copy is meant — `main` for the files "
        "mirrored there, and the entry in OTHER_REFS with a reason for anything else."
    )


@pytest.mark.parametrize("path", ["data/counter.json", "data/pr-genius-stats.json"])
def test_the_main_backed_reads_name_main(path):
    """The two that were broken: their files live on `main` and nowhere else."""
    refs = {ref for p, ref in calls() if p == path}
    assert refs == {"main"}, (
        f"{path} is read from {refs or 'nowhere'}; the maintained copy is on `main` "
        f"(and `data/counter.json` is 404 on the `data` branch — measured 2026-09-25)"
    )


def test_a_main_path_exists_in_this_checkout():
    for path, ref in calls():
        if ref != "main":
            continue
        assert (REPO / path).is_file(), (
            f"{path} is read from `main` but is not in the tree — the fallback would 404 into a 502"
        )


def test_every_other_ref_is_declared_with_a_reason():
    undeclared = [(path, ref) for path, ref in calls() if ref and ref != "main"
                  and (path, ref) not in OTHER_REFS]
    assert undeclared == [], (
        f"these reads use a ref this test cannot verify offline: {undeclared}. Add each to OTHER_REFS "
        "with the reason it is the right copy — an undeclared one is how #1820 happened."
    )


def test_no_declared_other_ref_is_dead():
    """A stale exemption is a hole: if the call is gone, the entry has to go with it."""
    live = {(path, ref) for path, ref in calls()}
    for key, reason in OTHER_REFS.items():
        assert key in live, f"OTHER_REFS lists {key}, which no call uses any more"
        assert len(reason) > 40, f"{key} is exempted without a real reason: {reason!r}"
