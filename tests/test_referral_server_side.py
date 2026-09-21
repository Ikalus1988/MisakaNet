#!/usr/bin/env python3
"""The referral chain needed a server-side record, because a local one was never a relation (#1996).

`scripts/referral.py --stats` counted invitations by grepping git history for the referral code inside
`misakanet/profile.json`:

    git log --all --oneline --grep=<code> -- misakanet/profile.json

That counted how many people had accidentally committed their own node state — the file is
per-machine (`stage`, counters, `last_active`) and is rewritten by every search — and it stopped
counting entirely the day the file was untracked (#1991/#1993). Nothing on the server side knew the
word `referral`: the worker accepted `agent_type` and `client_id` and nothing else.

The tests here pin the client half of the fix, and they are deliberately about *what leaves the
machine* and *what is displayed*:

* the code is written where every client can read it, and only when it is code-shaped — the value
  travels from a file into an API request, so the boundary is here;
* `--stats` asks the server, and says "I could not read it" instead of printing `0`. A counter that
  cannot be read and a counter that is genuinely empty are different answers, and printing `0` for
  the first is how a broken counter passes for a fact;
* both installers send the same argument name with the same shape rule — two installers maintaining
  one contract is how this repository's other drift started (`tests/test_installer_parity.py`).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
REFERRAL = REPO / "scripts" / "referral.py"
NPM = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
PY_INSTALLER = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"
WORKER = REPO / "workers" / "register-proxy-sw.js"

sys.path.insert(0, str(REPO / "scripts"))
import referral  # noqa: E402  (the module under test)


def test_the_client_refuses_a_value_that_is_not_code_shaped(tmp_path, monkeypatch):
    """The value goes from a file into an API request; this is the boundary that checks it."""
    target = tmp_path / "referral_code"
    monkeypatch.setattr(referral, "REFERRAL_FILE", target)
    for bad in ("", "a", "has space", "way-too-long-to-be-a-code", "semi;colon", "quote'code", "emoji🙂xx"):
        assert referral.record_referral_for_clients(bad) is False, bad
        assert not target.exists(), f"{bad!r} must not be written"
    assert referral.record_referral_for_clients("  MDQIYJCP  ") is True, "shape-valid codes are written"
    assert target.read_text(encoding="utf-8").strip() == "MDQIYJCP"


def test_the_default_location_is_the_directory_every_client_reads(tmp_path, monkeypatch):
    """The whole mechanism depends on this path: `~/.misakanet-agent` is where the npm installer,
    the bootstrap installer and the CLI all look for `client_id` and `token`. Checked as a constant
    (before any monkeypatching) — my first version asserted it *after* pointing the module at a tmp
    path, which tested the tmp path."""
    assert referral.REFERRAL_FILE == Path.home() / ".misakanet-agent" / "referral_code"


def test_the_client_creates_the_state_directory_when_missing(tmp_path, monkeypatch):
    target = tmp_path / "agent-state" / "referral_code"
    monkeypatch.setattr(referral, "REFERRAL_FILE", target)
    assert referral.record_referral_for_clients("ABCD1234") is True
    assert target.is_file(), "the file is written"
    assert target.parent.is_dir(), "the state directory is created when missing"
    assert target.read_text(encoding="utf-8").strip() == "ABCD1234"


def test_the_stats_command_asks_the_server_and_does_not_invent_a_zero(monkeypatch, capsys):
    """`0` means "nobody used your code yet"; a failed read must not look like that."""
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"code": "MDQIYJCP", "invited": 7, "source": "d1"}).encode()

    def fake_urlopen(url, timeout=0):
        calls.append(url)
        return Response()

    monkeypatch.setattr(referral.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(referral, "get_referral_code", lambda: "MDQIYJCP")
    assert referral._server_count("MDQIYJCP") == 7
    assert calls and "code=MDQIYJCP" in calls[0], calls
    assert referral._server_count("") is None, "no code means nothing to ask about"

    def broken(url, timeout=0):
        raise OSError("network down")

    monkeypatch.setattr(referral.urllib.request, "urlopen", broken)
    assert referral._server_count("MDQIYJCP") is None, (
        "a failed read is None, not 0 — otherwise an unreachable server reads as 'nobody invited anyone'")

    monkeypatch.setattr(referral.urllib.request, "urlopen",
                        lambda url, timeout=0: (_ for _ in ()).throw(ValueError("not json")))
    assert referral._server_count("MDQIYJCP") is None


def test_the_worker_counts_a_new_node_and_not_a_renewal():
    """The two halves of the contract, pinned where the server implements them."""
    source = WORKER.read_text(encoding="utf-8")
    assert 'bumpCounter(env, "referral", referralCode, "all", 1)' in source, (
        "the referral must be counted as a counter row, not as a new key per node — the daily "
        "distinct-key budget is what registration depends on (#1890)")
    # The count lives in the new-node path: the reuse branch returns before it.
    reuse_return = source.index("        reused: true,")
    counted_at = source.index('bumpCounter(env, "referral"')
    assert counted_at > reuse_return, (
        "the counter increment must sit after the reuse branch, or every token renewal would "
        "inflate the inviter's number")
    assert "referred_by" in source


def test_both_installers_send_the_same_argument_with_the_same_shape():
    npm = NPM.read_text(encoding="utf-8")
    py = PY_INSTALLER.read_text(encoding="utf-8")
    for name, text in (("npm installer", npm), ("bootstrap installer", py)):
        assert "referral_code" in text, f"{name} does not send referral_code"
        assert "referral_code" in text.replace("referral_code:", "referral_code:"), name
        assert re.search(r"\^\[A-Za-z0-9\]\{4,16\}\$", text), (
            f"{name} must shape-check the code with the same rule the server applies")
    # …and the server applies exactly that rule.
    assert re.search(r"/\^\[A-Za-z0-9\]\{4,16\}\$/", WORKER.read_text(encoding="utf-8"))


def test_a_workflow_that_registers_sends_the_code_too():
    """The two installers are the clients that actually call `misakanet_register` in CI/first run."""
    for path in (NPM, PY_INSTALLER):
        text = path.read_text(encoding="utf-8")
        # `misakanet_register` and `referral_code` must appear in the same payload construction.
        assert re.search(r"misakanet_register[\s\S]{0,400}referral_code", text) or \
               re.search(r"referral_code[\s\S]{0,400}misakanet_register", text), path.name
