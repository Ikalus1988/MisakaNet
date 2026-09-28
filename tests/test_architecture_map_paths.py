#!/usr/bin/env python3
"""Every file the architecture map names must be a file you can find (#2082).

`ARCHITECTURE.md` opens with a directory tree, and it is the first thing a new contributor reads.
On 2026-09-25 that tree still listed `scripts/update_status.py`, which had been deleted with its
output four days earlier (#2095) — so the repository's own map was pointing at nothing, and nothing
noticed. That is #2082's actual complaint: 可复现 ≠ 会被重算, for prose as much as for numbers.

The rule is deliberately one-directional. The tree is a *partial* map — it lists eight of the ~120
scripts on purpose — so "every script is in the tree" would be false and the test would be deleted
within a week. What it does assert is the direction that was broken: a name in the map must resolve.

Two legitimate escapes, both of which must be stated rather than discovered:

* **`gitignore`** — `misakanet/profile.json` is generated at runtime. The map may name it; the rule is
  satisfied by the ignore entry, which is the file's real provenance.
* **A directory** — `search/`, `node/`, `lessons/` end in `/` and are checked as directories.

Mutation check (2026-09-25), all five red: the deleted script re-added to the map · a directory entry
written as a file · the entry regex broken · nesting flattened to "prepend the last section" (which
reports `misakanet/search/engine.py`, a file that exists, as missing) · the gitignore escape hatch
removed. The last one was green on the first attempt and had to be rewritten — the reason it was
green is in `test_a_generated_entry_is_allowed_by_its_ignore_entry`. The intended asymmetry still
holds: *omitting* a real file from the map is not a defect, because the tree is partial on purpose.
"""
from __future__ import annotations

import re
import sys
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARCHITECTURE = REPO / "ARCHITECTURE.md"

# `├── name.py   # comment` / `│   └── name/` — indent, tree character, name, comment.
ENTRY_RE = re.compile(r"^([\s│]*)[├└]──\s+(\S+)")
# Directory headers inside the tree (`scripts/`, `lessons/`) have no tree character.
HEADER_RE = re.compile(r"^([A-Za-z0-9_.-]+/)\s*(?:#.*)?$")


def map_entries() -> list[tuple[str, str]]:
    """(named path, its line in the map) for every entry in the first fenced tree.

    Nesting is by indentation, not by position: `misakanet/search/engine.py` is written as
    `│   └── engine.py` under `├── search/`, and a flat "prepend the last section" rule resolves it
    as `misakanet/engine.py` — which is how the first version of this parser reported a file that
    exists as missing.
    """
    inside = False
    section = ""
    stack: list[tuple[int, str]] = []   # (indent, directory name) of the open subdirectories
    out: list[tuple[str, str]] = []
    for line in ARCHITECTURE.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            if inside:
                break           # the tree is the first fenced block; stop at its end
            inside = True
            continue
        if not inside:
            continue
        header = HEADER_RE.match(line)
        if header:
            section = header.group(1)
            stack.clear()
            continue
        entry = ENTRY_RE.match(line)
        if entry:
            indent, name = len(entry.group(1)), entry.group(2)
            while stack and stack[-1][0] >= indent:
                stack.pop()
            out.append((section + "".join(d for _, d in stack) + name, line.strip()))
            if name.endswith("/"):
                stack.append((indent, name))
    return out


def _gitignored(path: str) -> bool:
    """`git check-ignore` rather than re-implementing the pattern language (see #2082's sibling test
    `test_gitignore_index_agreement.py`, which had to learn this lesson about case-insensitive hosts).
    """
    return subprocess.run(["git", "check-ignore", "-q", path], cwd=REPO).returncode == 0


def _resolvable(path: str) -> bool:
    """A map entry is honest if the file is in the checkout **or** is generated and ignored.

    The ignore check comes first on purpose. `misakanet/profile.json` is written by the CLI, so it sits
    in the working tree of anybody who has run it — and with a presence-first order the escape hatch
    below could be deleted while the suite stayed green here and went red in a fresh clone. The
    mutation run caught exactly that.
    """
    if _gitignored(path):
        return True
    return (REPO / path).exists()


def test_the_map_is_not_empty_and_we_can_read_it():
    """A parser that silently returns nothing would make every assertion below vacuous."""
    entries = map_entries()
    assert len(entries) >= 8, entries
    assert any(p == "scripts/update_lessons_json.py" for p, _ in entries), entries


def test_every_named_file_exists_or_is_generated():
    missing = [f"{path}   (from: {line})" for path, line in map_entries() if not _resolvable(path)]
    assert missing == [], (
        "ARCHITECTURE.md names files that are not in the repository and are not generated:\n  "
        + "\n  ".join(missing)
        + "\nEither the file is back, or the map has to stop promising it (#2095 deleted "
          "scripts/update_status.py and left this behind)."
    )


def test_a_generated_entry_is_allowed_by_its_ignore_entry():
    """Asserted on the *ignore entry*, not on the file's presence: `misakanet/profile.json` is in the
    working tree of anyone who has run the CLI, so a presence check passes here and fails in CI."""
    named = {p for p, _ in map_entries()}
    assert "misakanet/profile.json" in named, named
    assert _gitignored("misakanet/profile.json"), (
        ".gitignore must keep misakanet/profile.json ignored, or the map names a file that exists on "
        "a developer's disk and nowhere in a fresh clone"
    )
    assert _resolvable("misakanet/profile.json")


def test_a_removed_entry_is_not_reported():
    """The asymmetry, stated as a test: the map is partial, so an omission is not a defect."""
    named = {p for p, _ in map_entries()}
    assert "scripts/lesson_gate.py" not in named, "pick another unlisted script if this one was added"
    assert (REPO / "scripts/lesson_gate.py").is_file(), "the premise of this test is that it exists"


def test_a_directory_entry_is_checked_as_a_directory():
    dirs = [p for p, _ in map_entries() if p.endswith("/")]
    assert dirs, "the tree has directory lines; if none parsed, the regex broke"
    for d in dirs:
        assert (REPO / d).is_dir(), f"{d} is named in the map but is not a directory"


def test_the_rule_can_go_red(monkeypatch, tmp_path):
    """Run the rule against a map that names a file which cannot exist.

    Monkeypatched on this module rather than by dotted path: `tests/` is not a package, so
    `monkeypatch.setattr("tests.test_architecture_map_paths.ARCHITECTURE", …)` would raise.
    """
    fake = tmp_path / "ARCHITECTURE.md"
    fake.write_text(
        "```\nscripts/\n├── lesson_gate.py\n└── update_status.py\n```\n", encoding="utf-8"
    )
    monkeypatch.setattr(sys.modules[__name__], "ARCHITECTURE", fake)
    entries = map_entries()
    assert [p for p, _ in entries] == ["scripts/lesson_gate.py", "scripts/update_status.py"]
    bad = [p for p, _ in entries if not (REPO / p).exists() and not _gitignored(p)]
    assert bad == ["scripts/update_status.py"], bad
