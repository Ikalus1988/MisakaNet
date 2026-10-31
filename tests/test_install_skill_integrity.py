#!/usr/bin/env python3
"""The installer must not execute instructions it cannot vouch for.

`install_misakanet_agent.py` downloads `skills/misakanet/SKILL.md` and writes it into
`~/.agents/skills/misakanet/SKILL.md`. That file is **not a resource the agent reads** — it is a set of
instructions the agent follows, so an unverified download is remote code execution by prose.

The 2026-10-31 audit (F19) found the fetch unpinned (`@main`, three mirrors, no checksum) and
`bootstrap.sh` downloading the installer itself the same way before `exec`ing it. The fix has two
halves, and this file pins both:

  * the ref is a **release tag**, not `main` (a tag does not move);
  * `SKILL.md`'s sha256 is **embedded in the installer**, so a mirror serving different bytes for the
    same tag is refused rather than written.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "integrations" / "agent-autostart" / "install_misakanet_agent.py"
BOOTSTRAP = REPO / "integrations" / "agent-autostart" / "bootstrap.sh"
SKILL = REPO / "skills" / "misakanet" / "SKILL.md"


def _module():
    spec = importlib.util.spec_from_file_location("install_misakanet_agent", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_embedded_digest_matches_the_skill_file():
    module = _module()
    actual = hashlib.sha256(SKILL.read_bytes()).hexdigest()
    assert module.SKILL_MD_SHA256 == actual, (
        "SKILL.md changed without bumping SKILL_MD_SHA256 — that bump is the review step: a modified "
        "instruction file must be a deliberate, visible change, not something a download can do")


def test_the_mirrors_are_pinned_to_a_release_tag_not_main():
    module = _module()
    assert module.PINNED_REF.startswith("misakanet-setup-v"), module.PINNED_REF
    assert "@main" not in module.RAW_BASE_DEFAULT
    assert not module.RAW_BASE_DEFAULT.endswith("/main")
    for name, url in module.MIRRORS.items():
        assert "main" not in url.replace(module.PINNED_REF, ""), f"{name} mirror still points at main: {url}"
        assert module.PINNED_REF in url, f"{name} mirror is not pinned: {url}"


def test_bootstrap_pins_its_mirrors_too():
    text = BOOTSTRAP.read_text(encoding="utf-8")
    assert "MISAKANET_PINNED_REF" in text
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "@main" not in code, "bootstrap still downloads a mirror at @main"
    assert "/MisakaNet/main" not in code, "bootstrap's primary source still points at main"


def test_a_mirror_serving_other_bytes_is_refused(monkeypatch, tmp_path):
    """The digest check itself: same URL, different payload, no file written."""
    module = _module()
    payloads = {f"https://example.test/{module.SKILL_MD_PATH}": b"# tampered\n"}

    class FakeResponse:
        def __init__(self, data): self._data = data
        def read(self): return self._data
        def __enter__(self): return self
        def __exit__(self, *_): return False

    def fake_urlopen(url, timeout=None):
        if url in payloads:
            return FakeResponse(payloads[url])
        raise OSError("unreachable")

    monkeypatch.setenv("MISAKANET_RAW_BASE", "https://example.test")
    monkeypatch.setenv("MISAKANET_RAW_ONLY", "1")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert module._fetch_raw(module.SKILL_MD_PATH) == "", "a digest mismatch must return nothing"


def test_the_real_file_passes_the_same_check(monkeypatch):
    module = _module()
    real = SKILL.read_bytes()

    class FakeResponse:
        def __init__(self, data): self._data = data
        def read(self): return self._data
        def __enter__(self): return self
        def __exit__(self, *_): return False

    monkeypatch.setenv("MISAKANET_RAW_BASE", "https://example.test")
    monkeypatch.setenv("MISAKANET_RAW_ONLY", "1")
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda url, timeout=None: FakeResponse(real))
    assert module._fetch_raw(module.SKILL_MD_PATH).startswith("---"), "frontmatter, i.e. the real file"
