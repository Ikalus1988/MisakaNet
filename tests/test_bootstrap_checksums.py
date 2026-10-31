#!/usr/bin/env python3
"""`bootstrap.sh` must not `exec` a download it cannot vouch for.

The audit's F19: the one-line installer downloaded three files from three hosts and ran them. #4212
pinned the ref (so `main` cannot move under it) and gave the *installer* a digest for `SKILL.md`; this
file covers the remaining half — the installer itself, and its three siblings, verified in the script
that runs them.

The interesting failure is not "the check is missing", it is "the check is there and cannot fire":
a digest block that has drifted from the files, or a verification step placed after the `exec`. Both
are asserted below.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "integrations" / "agent-autostart"
BOOTSTRAP = BASE / "bootstrap.sh"
TEXT = BOOTSTRAP.read_text(encoding="utf-8")


def _digest(name: str) -> str:
    return hashlib.sha256((BASE / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _block() -> dict[str, str]:
    match = re.search(r'^CHECKSUMS="\n(.*?)\n"', TEXT, re.M | re.S)
    assert match, "bootstrap.sh has no CHECKSUMS block"
    pairs = {}
    for line in match.group(1).splitlines():
        digest, name = line.split()
        pairs[name] = digest
    return pairs


def test_every_downloaded_file_has_a_digest():
    files = re.search(r'^FILES="([^"]+)"', TEXT, re.M).group(1).split()
    assert set(files) == set(_block()), f"FILES {files} vs CHECKSUMS {sorted(_block())}"


def test_the_digests_match_the_committed_files():
    for name, recorded in _block().items():
        assert _digest(name) == recorded, (
            f"{name} changed without bumping the CHECKSUMS block — run "
            "`python3 scripts/update_install_checksums.py --write` and review the diff")


def test_the_generator_agrees():
    """The test does not own the format; the script that rewrites it does."""
    result = subprocess.run([sys.executable, str(REPO / "scripts" / "update_install_checksums.py"),
                             "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_verification_happens_before_the_exec():
    verified = TEXT.index("verify_downloads\n")
    executed = TEXT.index('exec "$PY"')
    assert verified < executed, "the installer is executed before it is verified"


def test_a_mismatch_aborts_and_deletes_the_file():
    assert "sha256 与脚本内置值不一致" in TEXT
    assert 'rm -f "$DIR/$name"' in TEXT
    # The abort has to be an exit, not a warning that falls through to `exec`.
    verify = TEXT[TEXT.index("verify_downloads() {"):TEXT.index("verify_downloads\n")]
    assert "exit 1" in verify


def test_no_digest_tool_is_a_refusal_not_a_skip():
    """A machine without sha256sum/shasum must not silently run unverified code."""
    assert "没有 sha256sum / shasum" in TEXT
    verify = TEXT[TEXT.index("verify_downloads() {"):TEXT.index("verify_downloads\n")]
    assert "exit 1" in verify


def test_the_mirrors_are_still_pinned():
    """The digest block complements the pin; it does not replace it."""
    assert "MISAKANET_PINNED_REF" in TEXT
    code = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
    assert "@main" not in code
