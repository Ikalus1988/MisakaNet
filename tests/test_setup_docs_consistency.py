#!/usr/bin/env python3
"""The installer's documented commands must exist, and the pages must agree with each other.

Why this exists (2026-09-17): `docs/install/index.html` — the page a visitor reaches from the
README — recommended `git clone` + `pip install misakanet-core` and **never mentioned the installer
at all**, while the README's step ① is `npx @misaka-net/misakanet-setup`. README itself says the
Python package is a *library* that does not wire anything into an assistant. The page sold a
different product than the page it belonged to, and nothing noticed, because the only test that
touched it (`tests/test_lesson_count_ssot.py`) watches two *numbers* on it, never a command.

`tests/test_onboarding_example.py` already pins this exact pattern for the onboarding queries
("one fact, several files → a test that keeps them aligned"). This is the same guard for the
commands and flags.

It is not a new invention: run the first assertion against the page as it shipped before #1805 and
it fails, which is the whole argument for having it.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
ENTRY_POINTS = (
    REPO / "README.md",
    REPO / "JOIN.md",
    REPO / "docs" / "install" / "index.html",
    REPO / "packages" / "misakanet-setup" / "README.md",
)
COMMAND = "npx @misaka-net/misakanet-setup"


def installer_flags() -> set[str]:
    """The flags the shipped installer accepts, read from its help table (one source of truth)."""
    text = INSTALLER.read_text(encoding="utf-8")
    table = re.search(r"const FLAGS = \[(.*?)\n\];", text, re.DOTALL)
    assert table, "the installer must keep a FLAGS table for --help (and for this test)"
    return {flag for flag in re.findall(r"'(--[a-z-]+)", table.group(1))}


def documented_flags(text: str) -> set[str]:
    """Flags these docs attach to *our* command — i.e. mentioned on a line that names it."""
    found: set[str] = set()
    for line in text.splitlines():
        if "misakanet-setup" not in line:
            continue
        found.update(re.findall(r"(--[a-z][a-z-]+)", line))
    return found


def test_every_entry_point_shows_the_one_line_installer():
    """The page, the README and the package README must send people to the same command."""
    missing = [str(p.relative_to(REPO)) for p in ENTRY_POINTS if COMMAND not in p.read_text(encoding="utf-8")]
    assert not missing, (
        f"these entry points never mention `{COMMAND}`: {missing}. "
        "docs/install/index.html shipped in exactly this state until #1805 and it sent visitors to "
        "a different product; the landing page is the first page a stranger reads."
    )


def test_every_documented_installer_flag_exists():
    """A doc that names a flag the tool does not accept is a broken instruction."""
    known = installer_flags()
    assert known, "the FLAGS table parsed empty — fix this test before trusting it"
    unknown: dict[str, list[str]] = {}
    for path in ENTRY_POINTS:
        for flag in documented_flags(path.read_text(encoding="utf-8")):
            if flag not in known:
                unknown.setdefault(flag, []).append(str(path.relative_to(REPO)))
    assert not unknown, f"documented but not accepted by the installer: {unknown}"


def test_the_installer_documents_its_own_landing_page_claims():
    """The three things the landing page promises must be real flags (or the page is lying)."""
    known = installer_flags()
    for flag in ("--verify", "--uninstall"):
        assert flag in known, f"{flag} is promised on the landing page and in README"
    page = (REPO / "docs" / "install" / "index.html").read_text(encoding="utf-8")
    for promise in ("--verify", "--uninstall"):
        assert promise in page, f"the landing page should tell people about {promise}"


def test_nothing_under_docs_recommends_the_python_library_as_the_install_path():
    """`pip install misakanet-core` is a library, not an install path (README says so itself)."""
    page = (REPO / "docs" / "install" / "index.html").read_text(encoding="utf-8")
    # What the visitor sees: strip comments first. This test failed on its own explanatory comment
    # when it was written, which is the same mistake as reading a rendered page's source.
    visible = re.sub(r"<!--.*?-->", "", page, flags=re.DOTALL)
    first_card = visible.split("</div>", 1)[0]
    assert "pip install misakanet-core" not in first_card, (
        "the first card on the install page must be the one-line installer; the Python library is "
        "for scripted use, and README states it does not wire anything into an assistant"
    )
