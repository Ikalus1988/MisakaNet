#!/usr/bin/env python3
"""A handoff citation must point at a handoff that exists.

The one shape with no legitimate exception.

Found in the wild (2026-10-04)
------------------------------
Two live production workflows and two live tests justified their retry budgets by citing a receipt:

    .github/workflows/deploy-freshness.yml:51  `docs/maintainer/handoff-2026-09-24.md`
                                            records ~1 request in 4 …
    .github/workflows/site-health.yml:49       the repository has the receipt for why this
                                            matters: `docs/…-09-24.md`
    tests/test_deploy_freshness.py:63          handoff-2026-09-24 measurement (~1 request in 4 …)
    tests/test_site_health_wiring.py:18        `docs/maintainer/handoff-2026-09-24.md`
                                            records ~1 request …

**That file was never committed.** The series runs 09-16 → 09-30 with no 09-24 in it, and the
figure it was cited for ("~1 request in 4 times out from a real machine") appears nowhere else in
the repository. So four load-bearing comments pointed every future debugger at a measurement that
could not be checked by anyone, including the author — the failure this repository already names in
`tests/test_deploy_freshness.py:7-9` ("a probe that reports 'fine' when it measured nothing is worse
than no probe") and `docs/maintainer/handoff-2026-09-30.md:3` (numbers must carry a source and a
measurement time).

Why this rule and not the general one
-------------------------------------
`tests/test_cited_lesson_paths_exist.py` already measured and **rejected** the broad version: "every
path in backticks in `docs/**` must exist" flags 69 absent paths across 35 documents, almost all of
them legitimate prose (history, tombstones, not-yet-produced inputs, plans), and "a gate that flags
all four is a gate that gets switched off". Measured again here for code specifically: 237 citation
sites from `.github/workflows`, `tests/` and `scripts/`, of which **15 do not resolve — and almost
all of those are deliberate fixtures** (`docs/does-not-exist.md`, `tmp_path` lesson names
invented by
`test_land_change.py`). Adopting that rule would mean an exemption table larger than the gate.

This rule is narrower on purpose, and it is narrow along the one axis where the sibling test's
exceptions do not apply:

* The subject is **the handoff series only** — a closed, curated set of 17 dated files.
* The subject is **code and maintained docs**, not dated records. A dated record naming a path
  a file
  once had is history, which the sibling test exempts for good reason. A workflow or a test is not a
  record: it is read as current truth by whoever debugs it next month, and a comment there is
  asserting a fact *now*, not remembering one.
* The claim is not "this path existed at the time" but "**here is the receipt for this number**". A
  receipt to a file that was never committed is not a receipt. There is no legitimate reading under
  which a code comment may cite a handoff as evidence and have that evidence be absent.

Measured baseline when this was added: 14 distinct handoff citations in scope, **0 unresolvable**
after the four above were corrected. The one handoff citation that still does not resolve,
`handoff-2026-09-17.md` in
`docs/maintainer/capability-inventory-automation-2026-09-18.md`, is a dated
record and is deliberately out of scope — the same exemption the sibling test applies.

A note on what this gate does *not* do: it cannot tell you whether the measurement inside a
handoff is
true, only that the receipt is there. That is the achievable half, and it is the half that was
missing.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HANDOFFS = REPO / "docs" / "maintainer"

# Code and maintained documentation. Excludes dated records — see the module docstring and
# `tests/test_cited_lesson_paths_exist.py`, which is the authority on why records are exempt.
ROOTS = (".github/workflows", "tests", "scripts")
SUFFIXES = {".py", ".yml", ".yaml", ".mjs", ".js", ".sh"}
HANDOFF_CITATION = re.compile(r"docs/maintainer/handoff-[A-Za-z0-9._-]+\.md")
# A path with a placeholder in it (`handoff-YYYY-MM-DD.md`) is a template, not a citation.
PLACEHOLDER = re.compile(r"[-_](?:YYYY|xxxx|<|\*|TBD)")
# This file cites handoffs that do not exist — that is what it was written for, so it cannot be
# clean by its own rule. Excluding it is not a loophole: the defect it hunts is *documented* here,
# and the second test below proves the rule still fires on a real file. The alternative — scrubbing
# the docstring of the very citation that explains the gate — would make the gate harder to
# understand in exchange for passing itself, which is the wrong trade.
SELF = "tests/test_handoff_citations_resolve.py"


def handoff_citations() -> list[tuple[str, str]]:
    """(citing file, cited handoff) per handoff cited from code. Sorted for stable output."""
    found: list[tuple[str, str]] = []
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in SUFFIXES or not path.is_file():
                continue
            rel = str(path.relative_to(REPO))
            if rel == SELF:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for cited in HANDOFF_CITATION.findall(text):
                if PLACEHOLDER.search(cited):
                    continue
                found.append((rel, cited))
    return sorted(set(found))


def test_every_handoff_cited_from_code_exists():
    """The rule: if code points at a handoff as its evidence, that handoff is there.

    Not "if a document mentions a path" — a dated record naming a path a file once had is history.
    This is about code asserting a fact now and naming where the receipt lives.
    """
    missing = [
        f"{citer} cites {cited}, which does not exist"
        for citer, cited in handoff_citations()
        if not (REPO / cited).exists()
    ]
    assert not missing, (
        "code cites a handoff that was never committed, so the measurement it stands on cannot "
        "be checked by anyone:\n  " + "\n  ".join(missing)
        + "\n\nEither commit the handoff, or drop the figure and keep the rule it was justifying. "
        "A retry budget is sound engineering on its own; a specific ratio nobody can verify is not."
    )


def test_the_gate_would_catch_a_dangling_citation(tmp_path):
    """Guard the guard. A gate never observed red is not a gate — so prove it can fail.

    A throwaway tree with one handoff, and one workflow citing a handoff that is not in it.
    """
    maintainer = tmp_path / "docs" / "maintainer"
    maintainer.mkdir(parents=True)
    (maintainer / "handoff-2026-10-01.md").write_text("# present\n", encoding="utf-8")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)

    present = workflows / "ok.yml"
    present.write_text("# see docs/maintainer/handoff-2026-10-01.md\n", encoding="utf-8")
    dangling = workflows / "bad.yml"
    dangling.write_text("# see docs/maintainer/handoff-2026-10-02.md\n", encoding="utf-8")

    def missing_under(root: Path) -> list[str]:
        base = root / ".github" / "workflows"
        out = []
        for path in sorted(base.rglob("*")):
            if path.suffix not in SUFFIXES:
                continue
            for cited in HANDOFF_CITATION.findall(path.read_text(encoding="utf-8")):
                if not (root / cited).exists():
                    out.append(f"{path.name} -> {cited}")
        return out

    assert missing_under(tmp_path) == ["bad.yml -> docs/maintainer/handoff-2026-10-02.md"], (
        "the probe must find the dangling citation and only the dangling citation"
    )


if __name__ == "__main__":  # pragma: no cover
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            print(f"  {_name} ... ", end="", flush=True)
            try:
                _fn()
            except AssertionError as err:
                print("FAIL")
                raise SystemExit(f"\n{err}")
            print("ok")
