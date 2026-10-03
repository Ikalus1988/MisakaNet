#!/usr/bin/env python3
"""Reads that must see *every* element of a GitHub list have to paginate.

## Why this rule exists

This repository has now shipped the same pagination defect three times, and the third was the worst.
`per_page=100` reads one page. It is not "all of them", and on two endpoints in particular the
difference is silent:

- **check-runs** (`workers_builds_watch.py`). Real commits here carry 118–187 check-runs and the
  Workers Builds run is not always on the first page of them, so a one-page filter reported the
  commit as having no build at all — and the watcher answered "no state change", which for a *red*
  build is silence. Fixed in #2797.
- **issue comments** (`workers_builds_watch.py: last_state`). GitHub returns comments oldest-first, so
  one page yields the **oldest** 100. A tracker issue grows by one comment per state transition, so the
  newest state is exactly the one that goes missing; a stale `red` read out of a resolved transition
  gets re-reported as current, forever.

The threshold is not theoretical. Measured 2026-10-04: seven issues in this repository carry more than
100 comments and **#2020 carries 249** (also #761/762/763 at 237/230/200). The trackers here are
small — the largest is #2637 at 6 — so nothing is broken today. That is a property of the current issue
set, not of the code.

The first two survived because of a stub, not a shortage of tests: `StubGitHub` answered every list
request with the whole collection, so `per_page=100` was ignored and every test saw one complete page.
The stub now paginates. This rule is the second half of that fix.

## What it covers, and what it deliberately does not

The rule is scoped to the two endpoints where a caller needs **completeness** and truncation produces
no error:

    .../comments?per_page=N        dedup against all of them, or scan for the newest
    .../timeline?per_page=N        read the whole history
    .../check-runs?per_page=N      filter for a run that may be on any page

It deliberately does **not** cover `issues` and `pulls` reads, and that is a real judgement rather
than a convenient one. Most of those are deliberate top-N fetches — `workers_builds_watch.py:182` asks
for the 10 newest open issues carrying a label, and paginating it would answer a different question
than the one asked. A small `per_page` on a sorted list is a page size; a large one on a
completeness-required list is a bug. The two look identical to a scanner, so the scanner does not
guess: anything that genuinely needs every issue is currently rare enough to paginate at the call
site, and the ones that do not are left alone.

`ALLOWED` is a list of decisions, not of known bugs to tolerate. Each entry says what makes the site
acceptable *today* and what would change that.
"""
from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# The endpoints where completeness is required. Anchored on the path, not on the query, so a
# `per_page` on some other endpoint is not swept in.
NEEDS_ALL = re.compile(r"/(comments|timeline|check-runs)\?")

PER_PAGE = re.compile(r"per_page=(\d+)")

# A `page=` that is not the tail of `per_page=`. The negative lookbehind is load-bearing: `per_page=100`
# *contains* the substring `page=100`, so a naive `page=` search classifies every call as paginated and
# this rule passes vacuously — which is the failure mode of a guard that looks like it works.
PAGE_PARAM = re.compile(r"(?<!per_)page=")

# Non-Python line prefixes, plus a docstring line. A rule that trips over the prose describing the bug
# is a rule people learn to disable; the `#2797` docstring in `all_check_runs` quotes `per_page=100`
# and the first version of this scanner matched it.
def _prose_lines(source: str) -> set[int]:
    """1-indexed line numbers that are wholly prose: a comment, or inside a multi-line string.

    Tokenised rather than pattern-matched, because a line-prefix regex is wrong in the one case that
    matters here: the `#2797` docstring in `all_check_runs` explains the bug by quoting
    `` `per_page=100` ``, and only the *first* line of a docstring opens with a triple quote. Every
    continuation line looks like ordinary code, so a prefix rule either misses the prose — and then
    fires on the fix's own explanation — or has to guess at it.

    A line is prose only if it is a comment, or if a string token **spans** it. That last qualifier is
    load-bearing and was not obvious: marking every line that merely *contains* a string literal marks
    almost every line of Python, because `"GET"` and `item['number']` are strings too. Doing that hid
    two real reads — `register_issue.py:350` and `question_autopilot.py:617` — which is the failure
    this function exists to prevent, committed by the function itself.

    Token *names* rather than the `tokenize.FSTRING_*` constants, because those were added in Python
    3.12 and this repository runs a 3.11 / 3.12 / 3.13 matrix. Referencing the constant directly passed
    on the interpreter it was written on and raised `AttributeError` on `test (ubuntu-latest, 3.11)` —
    which is precisely what that leg is for. `tok_name` maps whatever types the running interpreter has,
    so the 3.12-only names simply never appear on 3.11, and there a multi-line f-string is one `STRING`.

    Returns what it classified if the file does not tokenise. A syntax error elsewhere in `scripts/`
    should fail whichever test compiles that file, not silently widen this one.
    """
    multi_line_string_names = {"STRING", "FSTRING_START", "FSTRING_MIDDLE"}
    marked: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                marked.add(tok.start[0])
            elif (tokenize.tok_name.get(tok.type) in multi_line_string_names
                  and tok.start[0] != tok.end[0]):
                marked.update(range(tok.start[0], tok.end[0] + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return marked


def _reads_paginate(line: str, window: list[str]) -> bool:
    """True when this call is one page of a paging loop, or carries its own `page=`."""
    if PAGE_PARAM.search(PER_PAGE.sub("", line)):
        return True
    # `for page in range(...)` / `while page <=` within a few lines above means the caller paginates.
    # A small window, so an unrelated `page` variable further up cannot be mistaken for a loop.
    return any(
        PAGE_PARAM.search(PER_PAGE.sub("", above))
        and ("range(" in above or "while " in above or "+=" in above or "+ 1" in above)
        for above in window
    )


def _needs_all(source: str) -> bool:
    return bool(NEEDS_ALL.search(source))


def exhaustive_reads() -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for path in sorted(SCRIPTS.rglob("*.py")):
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        prose = _prose_lines(source)
        for i, line in enumerate(lines):
            if not PER_PAGE.search(line) or (i + 1) in prose:
                continue
            if not _needs_all(line):
                continue
            if _reads_paginate(line, lines[max(0, i - 4):i]):
                continue
            found.append((path.relative_to(REPO).as_posix(), i + 1, line.strip()))
    return found


ALLOWED: dict[tuple[str, str], str] = {
    ("scripts/bounty_claim.py", "/issues/N/timeline"):
        "`_satisfaction_evidence` reads an issue's timeline to support a claim. Advisory only: the "
        "caller falls back to the issue state when the read fails and settles satisfaction from the "
        "state, so a truncated timeline changes the evidence quoted, not the outcome. Bounded in "
        "practice: a timeline grows with *events* (labels, closes, cross-references) rather than with "
        "discussion, and the claim it supports is read from a bounded window around the settlement. "
        "Not re-measured against a specific issue — the comment counts in the module docstring are "
        "comment counts and are not evidence about timelines.",

    ("scripts/bounty_claim.py", "/issues/N/comments"):
        "`upsert_receipt` reads a PR's comments to update its own previous receipt rather than posting "
        "a second one. Bounded by PR discussion length — the busiest PR here has 21 comments against a "
        "cliff of 100 (measured 2026-10-04) — and the failure mode is a duplicate receipt on a money "
        "record, so paginate this before any bounty PR can run for a month.",

    ("scripts/register_issue.py", "/issues/N/comments"):
        "`build_welcome` de-duplicates its own welcome comment on the registration issue. Bounded by one "
        "thread per registration, and no registration issue in this repository has come close to 100 "
        "comments. The failure mode is a duplicated welcome, which is noise rather than a wrong record.",

    ("scripts/question_autopilot.py", "/issues/N/comments"):
        "`main` checks whether its digest receipt is current before reposting. This is the closest of the "
        "four to the cliff, because the list is the autopilot's own receipts and grows with its run "
        "count. Paginate when the digest issues it manages reach 100 comments; at the current cadence "
        "they are well under.",
}


def _key(path: str, source: str) -> str | None:
    """The `ALLOWED` key for a read: `/issues/N/<collection>`.

    Normalises the resource id to `N` so a rename of the local variable does not orphan an entry, and
    keys on the collection rather than the file so a *second* endpoint in the same file cannot inherit
    the first one's permission.
    """
    match = re.search(r"/(comments|timeline|check-runs)\?", source)
    if not match:
        return None
    head = source[:match.start()]
    if re.search(r"/(?:issues|commits)/", head):
        return f"/issues/N/{match.group(1)}"
    return f"/{match.group(1)}"


def test_every_exhaustive_read_is_a_written_down_decision():
    reads = exhaustive_reads()
    assert reads, (
        "the scan found no read that needs every element of a list, which means it stopped matching — "
        "a guard that passes because it found nothing is not a guard. Check PER_PAGE / NEEDS_ALL.")

    undecided = []
    for path, lineno, source in reads:
        key = _key(path, source)
        if key is None or (path, key) not in ALLOWED:
            undecided.append(f"  {path}:{lineno}  {source[:84]}")
    assert not undecided, (
        f"{len(undecided)} read(s) of a list that must be seen whole, taking one page. `per_page=100` is "
        f"not 'all of them', and on comments one page is the OLDEST 100 — so for a newest-first read the "
        f"newest element is the one that goes missing, with no error to show for it. Paginate, or add to "
        f"ALLOWED with what makes it acceptable now and what would change that:\n" + "\n".join(undecided))


def test_every_allowed_entry_still_matches_a_read():
    """Compares (path, shape) pairs, not bare shapes.

    A bare-shape comparison cannot detect per-file staleness at all: `/issues/N/comments` is present
    while any *one* file still has an unallowlisted read of comments, so deleting or paginating
    `register_issue.py`'s read left its entry looking live. Verified by mutation — with the shape-only
    comparison this test stayed green while its subject had moved.
    """
    present = {(path, _key(path, src)) for path, _l, src in exhaustive_reads() if _key(path, src)}
    stale = [f"  {path} — {shape}" for (path, shape) in ALLOWED if (path, shape) not in present]
    assert not stale, (
        "these ALLOWED entries no longer match any read — the code was probably paginated or removed, "
        "which is good news. Delete the entry:\n" + "\n".join(stale))
    for path, _shape in ALLOWED:
        assert (REPO / path).is_file(), f"{path} does not exist; remove the ALLOWED entry"


def test_a_second_read_of_an_allowed_shape_does_not_inherit_the_permission():
    """One permission, one read.

    `ALLOWED` is keyed by (path, shape), so a *second* un-paginated read of the same collection in the
    same file would satisfy the same key and slip through — the permission would cover a call nobody
    read. The `_key` docstring used to claim this was impossible; it is not, and this is what makes the
    claim true. Verified by mutation: adding a second such read left the rule green.
    """
    counts: dict[tuple[str, str], int] = {}
    for path, _lineno, source in exhaustive_reads():
        key = _key(path, source)
        if key:
            counts[(path, key)] = counts.get((path, key), 0) + 1

    duplicated = {k: n for k, n in counts.items() if n > 1}
    assert not duplicated, (
        f"these (file, endpoint) pairs have more than one single-page read, so the single ALLOWED entry "
        f"covering them authorises a call nobody assessed: {duplicated}. Either paginate the extra "
        f"read, or give it its own entry with its own reason.")


def test_every_allowed_entry_states_what_makes_it_acceptable():
    """A bare entry is an oversight with extra steps, and an unexercisable one is a rumour."""
    for (path, shape), reason in ALLOWED.items():
        assert len(reason.split()) >= 25, f"{path} {shape}: the reason is too short to be a decision"
        assert any(word in reason.lower() for word in ("measured", "bounded", "advisory", "cadence")), (
            f"{path} {shape}: the reason does not say what makes it acceptable now — say what was "
            f"measured or what bounds the list")


def test_the_prose_detector_does_not_depend_on_a_python_version_specific_token():
    """Pins the defect `test (ubuntu-latest, 3.11)` caught on this file's first version.

    `tokenize.FSTRING_START` / `FSTRING_MIDDLE` arrived in Python 3.12 (PEP 701). Referencing them
    directly passed on the 3.12 interpreter it was written on and raised
    `AttributeError: module 'tokenize' has no attribute 'FSTRING_START'` on the 3.11 leg — every test
    in this file failed at once, in a file whose whole purpose is to be a guard. The repository runs a
    3.11 / 3.12 / 3.13 matrix precisely to catch this, and the local interpreter it was developed on was
    the one version where the bug could not appear.

    Two assertions, because either alone is satisfiable without being right: no *code* line may name a
    3.12-only constant, and the scan must produce the same answer whichever string-token types the
    running interpreter has.

    The scan filters prose with `_prose_lines` for the same reason the main scanner does. Without it
    this test fails on itself — the assertion message and this docstring both contain the literal
    `tokenize.FSTRING_*`, so a naive regex over the file matches the sentence explaining the rule. That
    is the failure this file was written to prevent, committed by the file.
    """
    own_path = REPO / "tests" / "test_github_list_reads_paginate.py"
    own = own_path.read_text(encoding="utf-8")
    prose = _prose_lines(own)
    direct = [
        (n, m.group(0))
        for n, line in enumerate(own.splitlines(), 1)
        if n not in prose
        for m in re.finditer(r"tokenize\.(FSTRING_\w+)", line)
    ]
    assert not direct, (
        f"these code lines reference {direct} directly. Those token types exist only on Python 3.12+, so "
        f"the 3.11 leg of the test matrix raises AttributeError. Look the name up through "
        f"`tokenize.tok_name.get(...)` instead — it maps whatever types the running interpreter has.")

    # Same answer regardless of which string tokens this interpreter knows about. A 3.11 run has no
    # FSTRING_* at all and must still find the same four reads.
    reads = exhaustive_reads()
    assert len(reads) == 4, f"expected 4 exhaustive reads on any supported interpreter, got {len(reads)}"

    # And a multi-line f-string is prose here whichever way the interpreter tokenises it.
    sample = 'x = 1\ny = f"""\nper_page=100\n"""\nz = 2\n'
    prose = _prose_lines(sample)
    assert 3 in prose, (
        f"line 3 is inside a multi-line f-string and must count as prose; got {sorted(prose)} on "
        f"{sys.version_info.major}.{sys.version_info.minor}")


def test_the_detector_distinguishes_paginated_from_not():
    """The rule passes vacuously if the detector cannot tell the two apart, and that is not
    hypothetical: the first version matched `page=` inside `per_page=100` and so classified every read
    in the repository as already paginated."""
    paginated = [
        'd = gh_api(f"/issues?state={state}&labels=question&per_page=100&page={page}")',
        'batch = github_get(f"{url}{separator}per_page=100&page={page}", token)',
    ]
    for line in paginated:
        assert _reads_paginate(line, []), f"should be seen as paginated: {line}"
    for line in ['comments = gh("GET", f"/issues/{n}/comments?per_page=100") or []',
                 'existing = _api(f"{API}/repos/{repo}/issues/{issue}/timeline?per_page=100", token)']:
        assert not _reads_paginate(line, []), f"should be seen as single-page: {line}"
    loop_above = ["    page = 1", "    while True:", '        items = api("x")']
    assert _reads_paginate('        items = api(f"/issues/N/comments?per_page=100&page={page}")', loop_above)


def test_the_lookbehind_that_keeps_the_detector_honest_is_pinned():
    """Pins `PAGE_PARAM` itself, which the test above cannot see.

    `_reads_paginate` strips `per_page=NNN` *before* looking for `page=`, so on any line where the two
    are the only occurrence the negative lookbehind is doing all the work and the strip hides it. With
    the lookbehind deleted, every test above stayed green — the detector silently reported every read
    in the repository as paginated, which is the exact vacuous pass this rule was written to prevent.
    """
    assert not PAGE_PARAM.search("per_page=100"), (
        "PAGE_PARAM matches the tail of `per_page=100`; without the lookbehind every single-page read "
        "in scripts/ is classified as paginated and this rule can never fail")

    # And the two shapes that must and must not match, stated directly.
    assert PAGE_PARAM.search("per_page=100&page={page}")
    assert PAGE_PARAM.search("?per_page=100&page=2")
    assert not PAGE_PARAM.search("?per_page=100")


def test_prose_and_other_endpoints_are_not_swept_in():
    """Scope check, in both directions, against the real file rather than a sample.

    The `all_check_runs` docstring quotes `per_page=100` while explaining the very bug this rule
    exists for; matching it would make the rule fire on the fix's own explanation, and a rule people
    learn to disable is worse than no rule. And `issues`/`pulls` reads with a small `per_page` are
    deliberate top-N fetches — `workers_builds_watch.py:182` asks for the 10 newest open issues
    carrying a label, and paginating that would answer a different question than the one asked."""
    real = (REPO / "scripts" / "workers_builds_watch.py").read_text(encoding="utf-8")
    prose = _prose_lines(real)
    lines = real.splitlines()

    quoted_in_prose = [n for n, line in enumerate(lines, 1)
                       if "per_page=100" in line and n in prose]
    assert quoted_in_prose, (
        "expected the `all_check_runs` docstring to quote `per_page=100` on a line tokenised as prose. "
        "If that text moved, point this at its new home — do not delete the test, because a scanner "
        "that cannot tell prose from code is the failure this guards against")

    # And the live call on the same file must be seen as code, not prose — otherwise the exclusion is
    # simply excluding everything.
    as_code = [n for n, line in enumerate(lines, 1) if "per_page=100" in line and n not in prose]
    assert as_code, "the paginating check-runs call should be seen as code, not prose"

    top_n = 'issues = gh("GET", f"/issues?labels={LABEL}&state=open&sort=created&per_page=10") or []'
    assert not _needs_all(top_n), "a top-N issues fetch is not an exhaustive read"
    exhaustive = 'comments = gh("GET", f"/issues/{n}/comments?per_page=100") or []'
    assert _needs_all(exhaustive), "a comment read is an exhaustive read"


def test_the_scan_finds_the_reads_it_claims_to():
    """Anchor the result so a scanner that silently narrows its own pattern fails here rather than
    passing an empty set to the rule above."""
    reads = exhaustive_reads()
    assert 3 <= len(reads) <= 8, (
        f"{len(reads)} exhaustive single-page reads, expected 4. If this moved, re-read the numbers in "
        f"the module docstring and update them — they are claims about this repository that someone "
        f"will rely on.")
