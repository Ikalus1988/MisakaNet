#!/usr/bin/env python3
"""The VS Code extension's manifest must agree with its code and with the repository.

Three defects, all found by a staleness sweep of `vscode-extension/` (last touched 2026-08-21)
and all of the same shape: **a file makes a claim about itself that nothing checks.**

1. `src/extension.ts` registers four commands; `package.json` declared two. The two missing ones
   are not cosmetic. `extension.ts:130` sets `command: 'misakanet.openLesson'` as a TreeItem's
   `command`, and VS Code only resolves a TreeItem command that is declared in
   `contributes.commands` — otherwise the click does nothing. So the README's advertised
   "Click to Open" was wired to a command VS Code could not find.

2. `loadLessons()` iterated `['core', 'contrib']`. `lessons/` has 12 subdirectories and
   `lessons/en/` alone holds **64** lessons, so the extension could not see the English tree while
   the README promised "Browse lessons by domain". The list is now the one
   `scripts/lesson_gate.py` already defines as `ACTIVE_LESSON_SUBDIRS` — the same gate that
   validates lessons — and this test is what stops the two copies drifting.

3. The README said `MIT`. The repository is Apache-2.0: root `LICENSE`, `package.json:4` and
   `pyproject.toml:10` all say so, and the extension ships no separate license file.

Nothing in CI read `vscode-extension/`. These assertions are about consistency between files, so
they hold whatever the extension's runtime does.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXT = REPO / "vscode-extension"
MANIFEST = EXT / "package.json"
SOURCE = EXT / "src" / "extension.ts"
README = EXT / "README.md"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_every_registered_command_is_declared_in_the_manifest():
    """A `registerCommand` that the manifest does not declare is unreachable from the UI."""
    source = SOURCE.read_text(encoding="utf-8")
    registered = set(re.findall(r"registerCommand\(\s*'([^']+)'", source))
    assert registered, "found no registerCommand calls — the regex needs updating, not passing"

    declared = {c["command"] for c in _manifest()["contributes"]["commands"]}
    undeclared = sorted(registered - declared)
    assert not undeclared, (
        f"registered but not in contributes.commands: {undeclared}. VS Code will not resolve a "
        "TreeItem `command` that is not declared, so the click silently does nothing."
    )


def test_the_manifest_declares_no_command_the_code_does_not_register():
    """The other direction: a declared command with no handler is a Command Palette dead entry."""
    source = SOURCE.read_text(encoding="utf-8")
    registered = set(re.findall(r"registerCommand\(\s*'([^']+)'", source))
    declared = {c["command"] for c in _manifest()["contributes"]["commands"]}
    orphans = sorted(declared - registered)
    assert not orphans, f"declared in package.json but never registered: {orphans}"


def test_the_scanned_lesson_subdirs_are_the_ones_lesson_gate_defines():
    """One definition of "a publishable lesson", not two."""
    sys.path.insert(0, str(REPO))
    from scripts.lesson_gate import ACTIVE_LESSON_SUBDIRS

    source = SOURCE.read_text(encoding="utf-8")
    match = re.search(r"for \(const subdir of \[([^\]]+)\]\)", source)
    assert match, "the loadLessons subdir loop was reshaped — update this test rather than skip it"
    scanned = set(re.findall(r"'([^']+)'", match.group(1)))

    assert scanned == set(ACTIVE_LESSON_SUBDIRS), (
        f"extension scans {sorted(scanned)} but scripts/lesson_gate.py:ACTIVE_LESSON_SUBDIRS is "
        f"{sorted(ACTIVE_LESSON_SUBDIRS)}. Missing {sorted(set(ACTIVE_LESSON_SUBDIRS) - scanned)} "
        "means those lessons are invisible to the extension."
    )


def test_every_active_lesson_subdir_actually_exists():
    """The list above is only worth having if the directories are real."""
    for subdir in ("core", "contrib", "en"):
        assert (REPO / "lessons" / subdir).is_dir(), f"lessons/{subdir} is gone"


def test_the_readme_license_is_the_repositories_license():
    """The extension ships no separate LICENSE, so it inherits the root one."""
    repo_license = _license_of_root_package()
    readme = README.read_text(encoding="utf-8")
    match = re.search(r"^##[ \t]+License[ \t]*$(.*?)(?=^##|\Z)", readme, re.DOTALL | re.MULTILINE)
    assert match, "the README lost its License section — update this test rather than skip it"
    section = match.group(1)
    assert repo_license.lower() in section.lower(), (
        f"README says {section.strip()!r} but package.json declares {repo_license!r}. The root "
        "LICENSE is the Apache License 2.0."
    )


def _license_of_root_package() -> str:
    declared = json.loads((REPO / "package.json").read_text(encoding="utf-8")).get("license", "")
    assert declared, "root package.json no longer declares a license"
    return declared


def test_the_self_test_inputs_are_real():
    """Guard against this file passing because its regexes found nothing.

    Same reason `test_misaka_verify_contract.py` asserts against its own source: a test that
    silently matches nothing is indistinguishable from a test that passes.
    """
    assert len(re.findall(r"registerCommand\(\s*'([^']+)'", SOURCE.read_text(encoding="utf-8"))) >= 4, (
        "expected at least the four commands the extension registers"
    )
    assert "Apache License" in (REPO / "LICENSE").read_text(encoding="utf-8")[:200]