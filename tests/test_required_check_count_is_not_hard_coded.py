#!/usr/bin/env python3
"""No file may hard-code how many status checks `main` requires.

`main` is protected by ruleset 23826057, *\"main: the deterministic gates\"*. How many contexts
that ruleset demands is a fact that moves: the set grew when the corpus and accessibility
checks were added, and nothing inside the repository would have said so. Meanwhile several
files stated the old count in prose — a maintainer document, several test docstrings, a
workflow comment, the lander's own docstring, and a Chinese registration guide. Each was
individually reasonable and collectively wrong, and the failure is silent: the sentence keeps
reading true long after the ruleset moves.

The fix is not to write down the new number. It is to make the text say *the required status
checks* and carry no count, so the next change to the ruleset cannot make it wrong. This test is
what keeps the next honest sentence from being a hard-coded one.

Three things this deliberately does **not** do:

* **It does not pin the number.** A test asserting the live count would be the same drift one
  level down — it would need editing on every ruleset change, by the person who has to notice
  the change.
* **It does not read the ruleset.** No network, no token, nothing that goes red when GitHub is
  unreachable. The count is not knowable from the checkout, and pretending otherwise is how a
  test starts failing for reasons unrelated to the code.
* **It does not try to tell a quotation from a claim by its shape.** That was tried, three
  ways, and each one broke on a real quotation in this repository — GitHub's refusal is quoted
  mid-sentence, inside backticks, inside a full-width bracket, and wrapped across lines. A rule
  tuned that tightly is a rule the repository cannot satisfy, and a gate nobody can satisfy
  gets deleted rather than fixed. So the quotations are listed by hand instead, each with its
  reason, and the list is checked in both directions.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Files that can hold repository prose. The benchmark JSON and the lesson corpus are excluded by
# the prefixes below rather than by extension, so a future `.rst` still gets scanned.
SCANNED_SUFFIXES = frozenset(
    {".py", ".md", ".yml", ".yaml", ".js", ".mjs", ".cjs", ".toml", ".sh", ".txt", ".cfg"}
)

# Whole files, path → why the count inside is not a claim about today's ruleset.
EXCLUDED_FILES = {
    "CHANGELOG.md": "a historical record; its sentences describe the day they were written",
}

EXCLUDED_PREFIXES = (
    "docs/benchmarks/",  # generated benchmark output, not repository prose
)

# Files that quote GitHub's own push rejection verbatim. The message is
# `remote: - N of N required status checks are expected.` and it necessarily contains a count
# — that count is the day it was copied, which is the whole reason it is quoted. Only the full
# message exempts a line, and only inside these files.
QUOTED_REFUSAL = re.compile(
    r"[2-9]\s+of\s+[2-9]\s+required\s+status\s+checks\s+are\s+expected", re.IGNORECASE
)
QUOTED_SITES = {
    "docs/agents/repo-operations.md": "reproduces the rejection in a troubleshooting table",
    
    "docs/maintainer/automation-lands-via-pr.md": "explains what a refused push looks like",
    "docs/maintainer/state-of-the-repo.md": "shows the rejection next to what replaced it",
    "docs/registration-channels.md": "explains why a registration push never landed",
    "scripts/ci/land_change.py": "the module docstring contrasts the old push with the new PR",
    "scripts/register_issue.py": "its docstring carries the rejection it was written against",
    "tests/test_no_workflow_pushes_to_main.py": "the failure this test exists to describe",
}

_COUNT = r"(?:two|three|four|five|six|seven|eight|nine|[2-9])"
_CHECKS = r"required\s+(?:status\s+|sign-off\s+)?(?:check|context)"

# A count sitting immediately in front of the phrase: the shape this test exists to refuse.
COUNT_BEFORE = re.compile(rf"\b{_COUNT}\s+{_CHECKS}s?\b", re.IGNORECASE)

# GitHub's "N of N are expected" form, which is what a reader sees in a push rejection.
COUNT_AROUND = re.compile(rf"\b{_COUNT}\s+of\s+{_COUNT}\s+{_CHECKS}s?\b", re.IGNORECASE)


def tracked_text_files() -> list[str]:
    """Every tracked file whose extension can carry prose.

    `git ls-files` rather than a directory walk, so the gate reads the same tree the pipeline
    indexes: an untracked file is not yet part of the repository and must not hold it red.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "."],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    keep = []
    for raw in listed.split("\0"):
        if not raw:
            continue
        if Path(raw).suffix.lower() not in SCANNED_SUFFIXES:
            continue
        if raw in EXCLUDED_FILES or raw.startswith(EXCLUDED_PREFIXES):
            continue
        keep.append(raw)
    return keep


def read(name: str) -> str:
    try:
        return (REPO / name).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""  # a file that is not text is not prose; nothing to drift


def quoted_lines(name: str, text: str) -> set[int]:
    """Line numbers covered by a verbatim quotation of GitHub's refusal, in a listed file.

    Matched against a whitespace-collapsed copy so a quote wrapped across two lines is still
    recognised; each character remembers its line, so every line the message touches is
    exempted rather than only the one it ends on.
    """
    if name not in QUOTED_SITES:
        return set()
    collapsed: list[str] = []
    origin: list[int] = []
    line = 1
    previous_space = True
    for char in text:
        if char == "\n":
            line += 1
        if char.isspace():
            if previous_space:
                continue
            collapsed.append(" ")
            origin.append(line)
            previous_space = True
            continue
        collapsed.append(char)
        origin.append(line)
        previous_space = False
    flat = "".join(collapsed)
    exempt: set[int] = set()
    for match in QUOTED_REFUSAL.finditer(flat):
        exempt.update(range(origin[match.start()], origin[match.end() - 1] + 1))
    return exempt


def findings(name: str) -> list[str]:
    """Every hard-coded count in one file, as `path:line` plus the line carrying it."""
    text = read(name)
    exempt = quoted_lines(name, text)
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number in exempt:
            continue
        if COUNT_BEFORE.search(line) or COUNT_AROUND.search(line):
            found.append(f"{name}:{number}: {line.strip()}")
    return found


def test_no_file_hard_codes_the_number_of_required_checks() -> None:
    """The sentence must survive the ruleset changing underneath it."""
    found = [hit for name in tracked_text_files() for hit in findings(name)]
    assert not found, (
        "these files state how many status checks `main` requires, which goes stale the moment\n"
        "the ruleset changes. Say `the required status checks` and carry no count:\n"
        + "\n".join(f"  {line}" for line in found)
    )


def test_the_quotation_allowlist_has_not_rotted() -> None:
    """A listed file that stopped quoting is an exemption nobody is reading any more.

    Checked in the other direction for the same reason the lander's exception list is: a
    stale entry is a hole that looks deliberate, and the next person cannot tell it apart
    from a real one.
    """
    stale = [
        f"{name} ({reason})"
        for name, reason in sorted(QUOTED_SITES.items())
        if not QUOTED_REFUSAL.search(re.sub(r"\s+", " ", read(name)))
    ]
    assert not stale, (
        "these files no longer quote GitHub's refusal, so they no longer need an exemption —\n"
        "drop them from QUOTED_SITES:\n" + "\n".join(f"  {line}" for line in stale)
    )


def test_the_gate_itself_would_not_trip_its_own_rule() -> None:
    """A scanner that matches this file is matching its own documentation.

    The docstring above describes the shape being searched for. Were the patterns ever
    loosened enough to match it, the gate would be reporting its own explanation as a
    violation — and a gate that cries wolf is a gate that gets deleted.
    """
    self_lines = read("tests/test_required_check_count_is_not_hard_coded.py").splitlines()
    offenders = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(self_lines, start=1)
        if not line.lstrip().startswith("#")
        and (COUNT_BEFORE.search(line) or COUNT_AROUND.search(line))
    ]
    assert not offenders, (
        "this file's own prose now matches its own rule:\n"
        + "\n".join(f"  {line}" for line in offenders)
    )
