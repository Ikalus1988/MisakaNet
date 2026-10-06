#!/usr/bin/env python3
"""A `file:line` citation in a document is a promise to keep pointing at the same line.

Found in the wild (2026-10-06)
------------------------------
`ROADMAP.md` carried a self-audit note saying `README.md` still listed
"Q1 2027 | Hub Federation, i18n | 📋 Planned". Two things about that note were wrong,
and the second is why this file exists:

1. The claim was stale — that row was removed 2026-09-20 (`26fc0eeb`).
2. **The note itself cited a line that had not existed for weeks.** It pointed at
   `README.md:617`; the file is 449 lines.

So the document whose job was to record staleness elsewhere was itself stale, and nothing
noticed. `tests/test_handoff_citations_resolve.py` already checks that files *cited from
code* exist — but only for handoffs, and only for file existence, not line position.
A path that exists is not the same as a line that still says what the citation claims.

What this checks
----------------
Every `path/to/file.ext:NNN` in every tracked markdown file must name a file that exists
**and** have at least `NNN` lines. Ranges (`:10-20`) are checked against the upper bound,
because that is the line someone will actually land on.

Deliberately narrow, because a citation gate that cries wolf gets ignored:

- Only markdown is scanned. Prose citations are the ones that rot quietly; code is
  version-controlled next to the thing it cites.
- The path must resolve to a tracked file. A citation into an untracked scratch path is
  not checkable and is not this gate's business.
- `://` is excluded, so URLs never parse as a path.
- Non-ASCII paths are not parsed. `lessons/` filenames are ASCII but display text is not,
  and a Chinese sentence containing `第 3 步` must not become a citation.

The fix for a failure is to correct the citation or the file — never to delete the gate.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# `path/to/file.ext:123` or `path/to/file.ext:10-20`.
# The negative lookbehind stops `foo.md` inside `barfoo.md:1` from matching, and stops the
# tail of an escape sequence from being read as a path: in `\ntests/test_x.py:12` the `n`
# would otherwise be swallowed and produce a path that never existed.
CITATION = re.compile(
    r"(?<![\w/.\-\\])"
    r"((?:[\w.-]+/)*[\w.-]+\.(?:md|py|js|mjs|cjs|ts|tsx|yml|yaml|json|toml|sh|sql|txt|css|html))"
    r":(\d+)(?:\s*[-–]\s*(\d+))?"
)

# A path made only of non-ASCII is display text that happens to look like a filename.
NON_ASCII_PATH = re.compile(r"[^\x00-\x7f]")

# Citations written as a bare filename (`doctor.py:45`, `register-proxy-sw.js:12`) are common
# in this repository and are only meaningful if exactly one tracked file has that name. Zero
# matches means the file was deleted or renamed; two or more means the citation was always
# ambiguous and the author knew the directory. Neither is checkable, so neither is an error —
# the gate reports what it can actually settle, and says so rather than guessing.
_BARE_NAME_CACHE: dict[str, list[str]] = {}


def _resolve_bare(name: str) -> list[str]:
    if name not in _BARE_NAME_CACHE:
        try:
            out = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--", f"*/{name}", name],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            _BARE_NAME_CACHE[name] = []
            return []
        hits = [p for p in out.stdout.split("\0") if p.strip()]
        _BARE_NAME_CACHE[name] = [p for p in hits if p.rsplit("/", 1)[-1] == name]
    return _BARE_NAME_CACHE[name]


def _tracked_markdown() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--", "*.md"],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git unavailable")
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return [REPO_ROOT / p for p in out.stdout.split("\0") if p.strip()]


# Archives. A stale citation inside a dated review or a submitted lesson is not actionable —
# `docs/reviews/2026-05-23-code-review.md` reviews code in *other* repositories and cites their
# paths by design, and `lessons/xxx.md` in `lessons/contrib/` is an illustrative placeholder, not
# a reference. Editing submitted lessons to satisfy a maintainer's gate is also the wrong
# bargain. Living documentation is the scope; these are records.
ARCHIVE_PREFIXES = ("lessons/", "docs/reviews/", "docs/field-reports/", "docs/openclaw-pr/")

# Dated records are excluded by filename, not by directory: `handoff-2026-09-15.md` and
# `capability-inventory-*-2026-09-18.md` record what was true *on that date*. Correcting their
# line numbers so they resolve against today's files would falsify the record — a handoff from
# 2026-09-15 pointing at a 2026-10-06 file is wrong in a different way from one pointing past
# end-of-file, and "fixing" it destroys the only thing the document is for.
DATED_RECORD = re.compile(r"-\d{4}-\d{2}-\d{2}\.md$")

_TOP_LEVEL: set[str] | None = None


def _top_level_entries() -> set[str]:
    """Every top-level name in the repository, cached once."""
    global _TOP_LEVEL
    if _TOP_LEVEL is None:
        try:
            out = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "ls-tree", "-z", "--name-only", "HEAD"],
                capture_output=True, text=True, timeout=60, check=False,
            )
            _TOP_LEVEL = {p for p in out.stdout.split("\0") if p.strip()} if out.returncode == 0 else set()
        except (OSError, subprocess.SubprocessError):
            _TOP_LEVEL = set()
    return _TOP_LEVEL


def _belongs_to_this_repo(path: str) -> bool:
    """Is this citation about *this* repository?

    `hub/federation/sync_protocol.py` and `node_modules/pg/lib/connection.js` are not stale
    references to files that were deleted — they are paths in somebody else's tree, quoted by a
    document that is describing something else. The cheapest reliable tell is the first segment:
    if it is not a top-level entry here, the citation cannot be about this repository, and
    failing on it would be the gate crying wolf on 11 documents to catch 4.
    """
    head = path.split("/", 1)[0]
    return head in _top_level_entries()


def _citations(text: str) -> list[tuple[str, int]]:
    """Yield (path, highest_line) for each citation, skipping URLs and non-ASCII paths."""
    found: list[tuple[str, int]] = []
    for m in CITATION.finditer(text):
        path, first, second = m.group(1), int(m.group(2)), m.group(3)
        # `https://x/y.md:1` — the regex can still reach the tail after `://`.
        if m.start() and text[max(0, m.start() - 3):m.start()] == "://":
            continue
        if NON_ASCII_PATH.search(path):
            continue
        found.append((path, int(second) if second else first))
    return found


def test_no_markdown_cites_a_line_that_does_not_exist():
    offenders: list[str] = []
    unresolvable: list[str] = []
    outside = 0
    checked = 0

    for md in _tracked_markdown():
        if not md.is_file():
            continue
        rel_posix = md.relative_to(REPO_ROOT).as_posix()
        if rel_posix.startswith(ARCHIVE_PREFIXES) or DATED_RECORD.search(rel_posix):
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = md.relative_to(REPO_ROOT)
        for path, line in _citations(text):
            if not _belongs_to_this_repo(path):
                outside += 1
                continue
            checked += 1
            if "/" in path:
                target = REPO_ROOT / path
            else:
                matches = _resolve_bare(path)
                if len(matches) != 1:
                    # 0 = the file is gone; 2+ = the citation was always ambiguous. Neither
                    # is something this gate can settle, and guessing would make it cry wolf.
                    unresolvable.append(f"{rel}: `{path}:{line}` — "
                                        f"{len(matches)} tracked files named {path}")
                    continue
                target = REPO_ROOT / matches[0]
            if not target.is_file():
                offenders.append(f"{rel}: cites {path} — file does not exist")
                continue
            try:
                total = sum(1 for _ in target.open("rb"))
            except OSError:
                continue
            if line > total:
                offenders.append(
                    f"{rel}: cites {path}:{line} but that file has only {total} lines"
                )

    assert not offenders, (
        f"{len(offenders)} document citation(s) point at a line that no longer exists "
        f"(checked {checked} citation(s) across the tracked markdown). "
        "A stale citation is worse than none — the reader cannot tell it is stale:\n  "
        + "\n  ".join(offenders[:20])
    )
    # Not an assertion: bare-name citations are reported so the count stays visible, but a
    # deleted-or-ambiguous one is not this gate's verdict to render. See _resolve_bare.
    print(f"\n[doc-citations] checked {checked}; other-repo citations skipped: {outside}; unresolvable bare names: {len(unresolvable)}")
    for line in unresolvable[:5]:
        print(f"  note: {line}")


def test_the_gate_would_catch_a_dangling_citation():
    """A gate nobody has seen go red is not a gate. This is the red, on demand."""
    sample = "see docs/maintainer/handoff-2026-10-05.md:99999 for the details"
    cites = _citations(sample)
    assert cites == [("docs/maintainer/handoff-2026-10-05.md", 99999)], cites

    # …and the real target is nowhere near that line, which is the whole point.
    target = REPO_ROOT / "docs/maintainer/handoff-2026-10-05.md"
    if not target.is_file():
        pytest.skip("target document not in this checkout")
    total = sum(1 for _ in target.open("rb"))
    assert 99999 > total, "the fixture line is supposed to be out of range"


def test_urls_are_not_citations():
    """`https://example.com/a.md:5` must not be read as a path — that is the obvious false positive."""
    text = "See https://example.com/docs/guide.md:42 and http://x.io/r.md:1 for details."
    assert _citations(text) == [], _citations(text)


def test_ranges_are_checked_against_the_upper_bound():
    """`:10-20` — the line a reader lands on is 20, so 20 is what has to exist."""
    text = "workers/register-proxy-sw.js:10-20 and README.md:3-9"
    cites = dict(_citations(text))
    assert cites["workers/register-proxy-sw.js"] == 20, cites
    assert cites["README.md"] == 9, cites