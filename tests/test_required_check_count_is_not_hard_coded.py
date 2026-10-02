#!/usr/bin/env python3
"""No file may hard-code how many status checks `main` requires.

`main` is protected by ruleset 23826057, *\"main: the deterministic gates\"*. How many contexts
that ruleset demands is a fact that moves: the set grew when the corpus and accessibility
checks were added, and nothing inside the repository would have said so. Meanwhile a long tail
of files stated the count in prose — maintainer documents, test docstrings, workflow comments,
the lander's own docstring and its runtime output, and both the English and Chinese operator
guides. Each was individually reasonable and collectively wrong, and the failure is silent: the
sentence keeps reading true long after the ruleset moves.

The fix is not to write down the new number. It is to make the text say *the required status
checks* and carry no count, so the next change to the ruleset cannot make it wrong. This test is
what keeps the next honest sentence from being a hard-coded one.

**Why this scans normalised text rather than lines.** A line-by-line reader is defeated by
ordinary writing, and it was: `**four**` in bold, `requires four` with the verb first, a count
on one line and its noun on the next, and the entire Chinese corpus all slipped past a
line-scanning first version of this gate. The count and the noun are frequently not adjacent
*and not on the same line*, so the text is whitespace-collapsed into one string first — each
character remembering the line it came from, so a hit can still be reported at the right place.
Markdown emphasis and code markers are removed for the same reason: a word wrapped in
asterisks or backticks is the same word to a reader, and the gate has to read it that way.

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
# the prefixes below rather than by extension, so a format nobody thought of is still scanned.
SCANNED_SUFFIXES = frozenset(
    {".py", ".md", ".yml", ".yaml", ".js", ".mjs", ".cjs", ".toml", ".sh", ".txt", ".cfg", ".rst"}
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
    r"[1-9][0-9]?\s+of\s+[1-9][0-9]?\s+required\s+status\s+checks\s+are\s+expected", re.IGNORECASE
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

# ── English ────────────────────────────────────────────────────────────────────────────────────
# "two", "three", … and plain digits. Two-digit counts are included: the set is small now and
# the point of this gate is to survive the day it stops being small.
_COUNT_EN = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[1-9][0-9]?)"
# The noun, and it must actually be about the *required* checks. Making the adjectives optional
# was a mistake: it turned every "three checks" and "two contexts" in the repository into a hit,
# including lesson text about ordinary CI checks, a watcher asserting on "2 context lines", and a
# table cell that merely contains the word. A required check is named either by `required` or by
# `status`; a bare "check" is some other check and is none of this gate's business.
_NOUN_EN = (
    r"(?:(?:required|sign[- ]off)[\s-]+(?:status[\s-]+)?(?:check|context)s?"
    r"|status[\s-]+(?:check|context)s?)"
)

# ── Chinese ────────────────────────────────────────────────────────────────────────────────────
# This repository documents itself in both languages and the count is a hard-coded number in
# both. A gate that only reads English is a gate that leaves half the repository unwatched.
#
# The measure word is mandatory. Without it the numeral is read inside ordinary words — 任**一**
# 必需检查 ("any one of the required checks") is a table row about no particular number, and a
# first version of this pattern counted it as a claim. A real count in Chinese prose carries
# its measure word: 三个 / 四条 / 两项.
_COUNT_ZH = r"[一二三四五六七八九十两]"
_MEASURE_ZH = r"(?:条|个|项|道|种|枚)"
_NOUN_ZH = rf"{_MEASURE_ZH}\s*必需检查"

PATTERNS = (
    # A count placed before the noun.
    re.compile(rf"\b{_COUNT_EN}\s+of\s+{_NOUN_EN}\b", re.IGNORECASE),
    re.compile(rf"\b{_COUNT_EN}\s+{_NOUN_EN}\b", re.IGNORECASE),
    # A verb placed before the count, which is as common an order as the other one.
    re.compile(rf"\brequires?\s+{_COUNT_EN}\s+{_NOUN_EN}\b", re.IGNORECASE),
    # The same sentence in Chinese, where the count precedes the noun outright.
    re.compile(rf"{_COUNT_ZH}\s*{_NOUN_ZH}"),
)

# Markdown emphasis and code markers: formatting, not words. A word wrapped in asterisks or
# backticks reads the same to a person and must read the same here. The space this leaves
# behind is load-bearing — a first version swallowed the markers without emitting it and
# welded the neighbouring words together, which then matched nothing at all.
_DECORATION = re.compile(r"[`*_~]")

# The structural prefix a line may open with: a heading marker, a blockquote, a bullet, a table
# bar, an ordered-list number. A count behind one of these is a row label or a list index, not a
# claim — `| 7 | …必需检查 |` is table row seven, and joining it to the next line would invent a
# sentence that nobody wrote.
_STRUCT_PREFIX = re.compile(r"^[ \t]*(?:[|>#*+\-•·]|\d+[.)])*[ \t]*")


def normalise(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace, drop decoration and line prefixes, keep every source line.

    Returns a single-line reading of the file and, for each character of it, the line it came
    from — which is what lets a sentence broken across two lines still be matched, and still be
    reported at the line a reader would go and look at.
    """
    out: list[str] = []
    origin: list[int] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        pending_space = True  # also swallows the gap between lines
        for char in _STRUCT_PREFIX.sub("", raw):
            if char.isspace():
                if pending_space:
                    continue
                out.append(" ")
                origin.append(number)
                pending_space = True
                continue
            if _DECORATION.match(char):
                out.append(" ")
                origin.append(number)
                pending_space = True
                continue
            out.append(char)
            origin.append(number)
            pending_space = False
        out.append(" ")
        origin.append(number)
    return "".join(out), origin


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


def quoted_lines(name: str, flat: str, origin: list[int]) -> set[int]:
    """Lines covered by a verbatim quotation of GitHub's refusal, in a listed file."""
    if name not in QUOTED_SITES:
        return set()
    exempt: set[int] = set()
    for match in QUOTED_REFUSAL.finditer(flat):
        exempt.update(range(origin[match.start()], origin[match.end() - 1] + 1))
    return exempt


def findings(name: str) -> list[str]:
    """Every hard-coded count in one file, as `path:line` plus the source line carrying it."""
    text = read(name)
    if not text:
        return []
    flat, origin = normalise(text)
    exempt = quoted_lines(name, flat, origin)
    raw_lines = text.splitlines()
    hits: set[str] = set()
    for pattern in PATTERNS:
        for match in pattern.finditer(flat):
            line = origin[match.start()]
            if line in exempt:
                continue
            source = raw_lines[line - 1].strip() if line - 1 < len(raw_lines) else ""
            hits.add(f"{name}:{line}: {source[:90]}")
    return sorted(hits)


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

    Checked in the other direction for the same reason the lander's exception list is: a stale
    entry is a hole that looks deliberate, and the next person cannot tell it apart from a real
    one. A renamed or deleted file fails here too, which is the point — an allowlist naming a
    path that no longer exists must not read as "nothing to exempt".
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
    name = "tests/test_required_check_count_is_not_hard_coded.py"
    assert not findings(name), (
        "this file's own prose now matches its own rule:\n"
        + "\n".join(f"  {line}" for line in findings(name))
    )
