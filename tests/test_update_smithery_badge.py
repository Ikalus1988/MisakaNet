#!/usr/bin/env python3
"""The Smithery badge job must not go red because a listing page moved.

Measured 2026-11-02..2026-11-04: the workflow failed every day on
`HTTP Error 404: Not Found` from `smithery.ai/servers/misakanet/misakanet` while the Smithery
API still listed the server. A daily red that means "nothing changed" is the kind of red people
learn to ignore, which is worse than no check.
"""
from __future__ import annotations

import importlib.util
import sys
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def _module():
    spec = importlib.util.spec_from_file_location(
        "update_smithery_badge", REPO / "scripts" / "update-smithery-badge.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_a_404_is_a_state_not_a_failure(monkeypatch, tmp_path, capsys):
    mod = _module()

    def raise_404(*args, **kwargs):
        raise urllib.error.HTTPError(mod.SMITHERY_SERVER_URL, 404, "Not Found", None, None)

    monkeypatch.setattr(mod.urllib.request, "urlopen", raise_404)
    out = tmp_path / "smithery.json"
    monkeypatch.setattr(sys, "argv", ["update-smithery-badge.py", "--output", str(out)])

    mod.main()  # must not SystemExit

    assert not out.exists(), "an unpublished listing must not overwrite the last good badge"
    assert "404" in capsys.readouterr().err


def test_a_non_404_failure_still_fails(monkeypatch, tmp_path):
    mod = _module()

    def raise_500(*args, **kwargs):
        raise urllib.error.HTTPError(mod.SMITHERY_SERVER_URL, 500, "Server Error", None, None)

    monkeypatch.setattr(mod.urllib.request, "urlopen", raise_500)
    monkeypatch.setattr(sys, "argv", ["update-smithery-badge.py", "--output", str(tmp_path / "x.json")])

    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 1
