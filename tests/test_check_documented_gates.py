#!/usr/bin/env python3
"""The documented gate set must match the ruleset that enforces it — and be checkable offline.

The live half needs a token, so it is exercised against a saved response rather than the network.
That is deliberate: a test that calls GitHub is a test that goes red when GitHub is unreachable,
and this repository has already spent three rounds learning that a gate people cannot satisfy
gets deleted rather than fixed.

What is pinned here, and why each one is worth a test:

* **The Hard Gates table is the only thing read.** The document also lists advisory checks that
  deliberately do not block a merge, several of them in tables that look identical. A parser
  that wandered past the heading would count those too and invert the document's own point.
* **Table decoration is not part of a context name.** A cell written `**gate**` and a cell
  written `` `gate` `` are the same requirement; a mismatch here would report a divergence that
  does not exist, and the workflow would open an issue every week.
* **The separator row is not a context.** `|---|---|` parses as a cell too.
* **A missing section is a failure, not an empty set.** An empty documented set compared against
  a live one is a divergence — but silently parsing to nothing would make a renamed heading look
  like "the document lists no gates", which is a different and much more confusing message.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_documented_gates", REPO / "scripts" / "check_documented_gates.py"
)
assert _spec and _spec.loader
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

DOC = REPO / "docs" / "ci-gates.md"
WORKFLOW = REPO / ".github" / "workflows" / "check-documented-gates.yml"

# "a count **of the gates**", not a count of anything. The trailing noun is what makes it a claim;
# without it this pattern is the prose scanner, and it fires on "Three notes" in this very section.
COUNT_CLAIM = re.compile(
    r"(\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b|\d+)\s*"
    r"(?:mandatory\s+|required\s+|hard\s+|deterministic\s+)*(?:gates?|checks?)\b"
    r"|[一二三四五六七八九十]\s*条",
    re.IGNORECASE,
)


def run_cli(argv: list[str]) -> tuple[int, str, str]:
    """Run the CLI exactly as the workflow does, and keep both streams separate.

    Which stream a line lands on is the whole contract — the workflow reads the exit code and the
    issue body reads stdout, while "I could not check" has to stay on stderr so it can never be
    mistaken for a diff. A helper that merges them would test something the real caller never sees.
    """
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = checker.run_cli(argv)
    return code, out.getvalue(), err.getvalue()

RULESET_RESPONSE = {
    "id": 23826057,
    "name": "main: the deterministic gates",
    "enforcement": "active",
    "bypass_actors": [],
    "rules": [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "DCO / Signed-off-by"},
                    {"context": "test (ubuntu-latest, 3.11)"},
                    {"context": "gate"},
                    {"context": "audit"},
                ]
            },
        }
    ],
}


def test_the_real_document_and_the_live_ruleset_agree() -> None:
    """The point of the script, run against the repository as it stands."""
    documented = checker.parse_documented(DOC)
    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    assert sorted(documented) == sorted(live), (
        f"docs/ci-gates.md lists {documented}, ruleset 23826057 requires {live}"
    )


def test_the_document_carries_no_count_of_its_own_gates() -> None:
    """The count must be a property of the table, not a sentence that can drift.

    This is the whole reason the prose was de-numbered. It fails the moment somebody helpfully
    writes "the four required checks" above the table — which is exactly what happened in this file
    before the ratchet existed.

    **Why the pattern is anchored rather than a word list.** The first two versions of this test
    each looked like a reasonable idea and each broke on the same section:

    * a bare word list (`four`, `three`, `five`, …) fires on "**Two** notes on what those commands
      measure" and "**Three** notes that have each cost someone an afternoon" — counts of *notes*,
      in the very section it is meant to protect;
    * widening the list to `two`/`six`/`nine` to catch more phrasings is how a four-line assertion
      becomes the two-thousand-file prose scanner this change exists to delete. It went looking for
      more shapes to catch and stopped describing anything.

    So it matches the claim, not the numeral: a number immediately qualifying *gates*, *checks* or
    `条`. Every way this repository has actually written that claim matches; "the nine matrix legs"
    and "Three notes" do not, and must not. It is deliberately not a general ban on numbers — a
    section that documents a matrix, a version and four pull requests cannot be held to that.
    """
    text = DOC.read_text(encoding="utf-8")
    start = text.index(checker.SECTION)
    end = text.find("\n## ", start)
    section = text[start:end if end > 0 else len(text)]
    claims = re.findall(COUNT_CLAIM, section)
    assert not claims, f"the Hard Gates section states a count of the gates: {claims}"


def test_the_count_pattern_catches_the_claims_it_claims_to() -> None:
    """A guard on the guard: a pattern that matches nothing would pass the test above forever.

    Every phrase here is one this repository has used or could plausibly use. If a future edit
    makes the pattern narrower, this goes red instead.
    """
    for phrase in ("the 4 required checks", "four hard gates", "all three gates",
                   "五条必需检查", "the Four required checks"):
        assert re.search(COUNT_CLAIM, phrase), f"the pattern misses a real claim: {phrase!r}"
    for phrase in ("Two notes on what those commands measure",
                   "Three notes that have each cost someone an afternoon",
                   "out of the nine test (…) legs", "the 3.11 leg", "9-leg matrix"):
        assert not re.search(COUNT_CLAIM, phrase), f"the pattern fires on a non-claim: {phrase!r}"


def test_advisory_tables_below_the_heading_are_not_counted() -> None:
    """A check that reports but cannot block is not one of the gates."""
    documented = checker.parse_documented(DOC)
    assert "PR Quality Gate" not in documented
    assert "coverage" not in documented
    for context in documented:
        assert "Hard Gates" not in context


def test_a_renamed_or_missing_section_fails_loudly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "ci-gates.md"
        broken.write_text("# something else\n\nno section here\n", encoding="utf-8")
        try:
            checker.parse_documented(broken)
        except SystemExit as error:
            assert checker.SECTION in str(error)
        else:  # pragma: no cover - only reached if the guard is removed
            raise AssertionError("a missing section must fail, not parse to an empty set")


def test_divergence_is_reported_as_a_difference_not_a_count() -> None:
    """A drift must name what is missing and what is invented, so the fix is obvious."""
    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    documented = [context for context in live if context != "audit"]
    documented.append("quality-labels")

    stream = io.StringIO()
    code = checker.report(documented, live, stream)
    output = stream.getvalue()
    assert code == 1
    assert "+ audit" in output
    assert "- quality-labels" in output
    # and it must not tell the reader what the count is — they can count the table
    assert "4" not in output.split("Read the ruleset")[0]


def test_agreement_reports_nothing_and_exits_zero() -> None:
    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    stream = io.StringIO()
    assert checker.report(list(live), live, stream) == 0
    assert stream.getvalue() == ""


def test_the_cli_works_from_a_saved_response_without_a_token() -> None:
    """The offline path is the one the test suite depends on; it must not require credentials."""
    with tempfile.TemporaryDirectory() as tmp:
        saved = Path(tmp) / "ruleset.json"
        saved.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        assert checker.main(["--from-file", str(saved), "--doc", str(DOC), "--quiet"]) == 0

        # ...and a document that has fallen behind exits non-zero
        stale = Path(tmp) / "stale.md"
        text = DOC.read_text(encoding="utf-8")
        stale.write_text(
            text.replace("| **audit** |", "| **removed-gate** |"), encoding="utf-8"
        )
        assert checker.main(["--from-file", str(saved), "--doc", str(stale)]) == 1


def test_a_missing_token_is_an_explicit_error_not_a_pass() -> None:
    """A ratchet that cannot reach GitHub must not report success."""
    for name in ("SHELDON_PAT", "GITHUB_TOKEN"):
        if name in sys.modules:  # pragma: no cover - defensive
            del sys.modules[name]
    saved = {name: None for name in ("SHELDON_PAT", "GITHUB_TOKEN") if name in __import__("os").environ}
    try:
        for name in saved:
            __import__("os").environ.pop(name, None)
        assert checker.main(["--doc", str(DOC)]) == 2
    finally:
        __import__("os").environ.update(saved)


# ── "could not check" is not "the document is wrong" ────────────────────────────────────────────
#
# The failure this section exists to prevent: a workflow that reads this script's exit code, treats
# anything non-zero as drift, and opens a titled, marker-bearing, weekly-refreshed issue telling a
# maintainer their documentation is out of date — when the truth is that a token had expired. It
# is worse than silence, because the issue is confident, recurring, and closes against a document
# that needs no change.

@pytest.mark.parametrize("payload, why", [
    ({"id": 23826057, "name": "main: the deterministic gates"},
     "a 404 body: no `rules` key at all"),
    ({"id": 23826057, "name": "x", "rules": []}, "an empty rule list"),
    ({"id": 23826057, "name": "x", "rules": [{"type": "branch_restriction"}]},
     "a ruleset whose rules are not status checks"),
    ({"id": 23826057, "rules": [{"type": "required_status_checks", "parameters": {}}]},
     "the rule is there but names no checks"),
])
def test_a_ruleset_that_names_no_checks_is_unreadable_not_drift(payload, why) -> None:
    """The exact inversion that produced a confidently wrong issue.

    Every one of these decodes as JSON and yields an empty context list. Compared against a
    documented table of four, an empty list reads as "the document invented four gates" and exits
    with the drift code — so the workflow, which is wired to that code, would do exactly what it is
    supposed to do about a real drift, and point at a document that was right.

    The last assertion is the one that matters most: the reason may *mention* the document, but it
    must not carry the drift message's instruction, because an issue built from it is titled
    "the documented gates no longer match" whatever the body says underneath.
    """
    with tempfile.TemporaryDirectory() as tmp:
        saved = Path(tmp) / "ruleset.json"
        saved.write_text(json.dumps(payload), encoding="utf-8")
        code, out, err = run_cli(["--from-file", str(saved), "--doc", str(DOC)])
    assert code == checker.EXIT_CANNOT_CHECK, f"{why} must be 'cannot check', not drift"
    assert out == "", f"{why}: a verdict reached stdout that should not have been rendered"
    assert "no longer matches" not in err, f"{why}: reported as drift"
    assert "update the table" not in err, f"{why}: told the reader to edit the document"
    assert "Check the ruleset by hand" in err, f"{why}: says what to do instead"


def test_a_crash_is_its_own_outcome_not_a_verdict() -> None:
    """A traceback used to exit 1, which is this script's 'the document has drifted'.

    Nothing distinguishes the two from the outside, so a one-character typo would have produced a
    recurring, authoritative-looking issue about a correct document.
    """
    original = checker.main
    checker.main = lambda argv=None: (_ for _ in ()).throw(RuntimeError("simulated typo"))
    try:
        code, out, _ = run_cli(["--doc", str(DOC)])
    finally:
        checker.main = original
    assert code == checker.EXIT_BROKEN
    assert code != checker.EXIT_DIVERGED
    assert out == ""


def test_only_a_real_comparison_ever_returns_the_drift_code() -> None:
    """The invariant, stated once: the drift code comes from `report()` and nowhere else."""
    live = checker.contexts_from_ruleset(RULESET_RESPONSE)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        readable = tmp / "ruleset.json"
        readable.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        assert run_cli(["--from-file", str(readable), "--doc", str(DOC)])[0] == checker.EXIT_AGREE

        unreadable = tmp / "empty.json"
        unreadable.write_text(json.dumps({"rules": []}), encoding="utf-8")
        assert run_cli(["--from-file", str(unreadable), "--doc", str(DOC)])[0] == (
            checker.EXIT_CANNOT_CHECK)

        # ...and a genuine divergence still is a divergence, with the diff on stdout
        stale = tmp / "stale.md"
        stale.write_text(DOC.read_text(encoding="utf-8").replace("| **audit** |", "| **gone** |"),
                         encoding="utf-8")
        code, out, _ = run_cli(["--from-file", str(readable), "--doc", str(stale)])
        assert code == checker.EXIT_DIVERGED
        assert out.startswith(checker.FAIL_PREFIX)
    assert live  # the fixture is not vacuously empty


def test_the_first_stdout_line_always_states_the_verdict() -> None:
    """What the workflow branches on.

    The workflow reads `compare_exit`, not the text — but a human reading the run log, and any
    future caller that greps, both depend on this: the first line of stdout is `OK:` or `FAIL:`, and
    anything else means the comparison did not happen.
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ruleset.json"
        path.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        _, agreed, _ = run_cli(["--from-file", str(path), "--doc", str(DOC)])
        assert agreed.splitlines()[0].startswith(checker.OK_PREFIX)

        stale = Path(tmp) / "stale.md"
        stale.write_text(DOC.read_text(encoding="utf-8").replace("| **audit** |", "| **gone** |"),
                         encoding="utf-8")
        _, diverged, _ = run_cli(["--from-file", str(path), "--doc", str(stale)])
        assert diverged.splitlines()[0].startswith(checker.FAIL_PREFIX)


def test_quiet_suppresses_agreement_and_nothing_else() -> None:
    """`--quiet` is for cron mail, not for hiding a verdict."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ruleset.json"
        path.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        assert run_cli(["--from-file", str(path), "--doc", str(DOC), "--quiet"])[1] == ""

        stale = Path(tmp) / "stale.md"
        stale.write_text(DOC.read_text(encoding="utf-8").replace("| **audit** |", "| **gone** |"),
                         encoding="utf-8")
        code, out, _ = run_cli(["--from-file", str(path), "--doc", str(stale), "--quiet"])
        assert code == checker.EXIT_DIVERGED
        assert out.startswith(checker.FAIL_PREFIX)


# ── the reporting step must survive the one value it exists to carry ────────────────────────────
#
# A `${{ steps.compare.stdout }}` sat inside a single-quoted JS string literal. The value is the
# newline-separated diff — always several lines — so the rendered script opened a quote on one line
# and closed it three lines later, and `node --check` returned `SyntaxError`. The consequence was
# not a broken issue body: it was that the step died *only* on the run that found drift, while the
# runs that found agreement skipped the step entirely and left the workflow looking healthy. A
# ratchet that cannot report is worse than one that reports nothing, because it looks fine.

def _script_bodies(text: str) -> list[tuple[str, str]]:
    """Every `script:` body in a workflow, as (step name, body)."""
    yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's steps")
    workflow = yaml.safe_load(text)
    found = []
    for job in (workflow.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            body = (step.get("with") or {}).get("script")
            if isinstance(body, str):
                found.append((step.get("name", "(unnamed)"), body))
    return found


def _strip_js_comments(body: str) -> str:
    """Remove `//` and `/* */` comments, keeping line count and column positions.

    Without this the detector fires on an apostrophe inside prose: `// don't splice ${{ x }}` opens
    a "string" at the apostrophe in *don't* and everything after it is inside one. A substitution in
    a comment is not code, and a lint that cries wolf on a comment gets switched off — which is
    worse than the bug it was looking for.
    """
    out: list[str] = []
    in_block = False
    for line in body.splitlines():
        result, index, in_string = [], 0, ""
        while index < len(line):
            if in_block:
                end = line.find("*/", index)
                if end < 0:
                    index = len(line)
                    break
                in_block = False
                index = end + 2
                continue
            if in_string:
                result.append(line[index])
                if line[index] == in_string:
                    in_string = ""
                index += 1
                continue
            if line.startswith("/*", index):
                in_block = True
                index += 2
                continue
            if line.startswith("//", index):
                break
            char = line[index]
            if char in "'\"`":
                in_string = char
            result.append(char)
            index += 1
        out.append("".join(result))
    return "\n".join(out)


def _quoted_substitutions(body: str) -> list[str]:
    """Lines where a `${{ }}` sits inside a `'…'` or `"…"` string, with the quote in effect.

    A template literal may span lines, so `` `${{ x }}` `` is fine and must not be reported — which
    is why the check tracks quote state rather than searching for a pattern. Walking each line
    independently is deliberate and sufficient: an unterminated quote cannot be *opened* mid-line
    from a previous one in a well-formed script, and a value spliced into one produces its own
    unterminated quote, which is the case reported.
    """
    offenders = []
    for line in _strip_js_comments(body).splitlines():
        state = ""
        index = 0
        while index < len(line):
            if line.startswith("${{", index) and state in ("'", '"'):
                offenders.append(f"{state}-quoted: {line.strip()}")
                break
            char = line[index]
            if char == "\\":
                index += 2
                continue
            if state == "":
                if char in "'\"`":
                    state = char
            elif char == state:
                state = ""
            index += 1
    return offenders


def test_no_workflow_splices_a_substitution_into_a_quoted_js_string() -> None:
    """`${{ }}` belongs in a template literal or in `env:`, never in `'…'` or `"…"`.

    Template literals may span lines, so the existing `lesson-quality.yml` interpolation is fine
    and this test says so. A quoted string may not, and one that receives a multi-line value is a
    `SyntaxError` waiting for the first time that value is longer than one line — which for a diff
    is always.
    """
    offenders = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.y*ml")):
        for step_name, body in _script_bodies(path.read_text(encoding="utf-8")):
            offenders += [f"{path.name}: {step_name}: {hit}" for hit in _quoted_substitutions(body)]
    assert not offenders, "these scripts interpolate into a quoted string:\n" + "\n".join(offenders)


def test_the_splice_detector_distinguishes_the_three_quote_kinds() -> None:
    """A guard on the guard, because this detector has to be *absent* to be useful.

    It has one job: report a value spliced into a single- or double-quoted string. Reporting a
    template literal would make it cry wolf on correct code — and the correct code is one line
    away, in `lesson-quality.yml`, written by somebody else.
    """
    assert _quoted_substitutions("const d = '${{ steps.x.outputs.d }}';")
    assert _quoted_substitutions('const d = "${{ steps.x.outputs.d }}";')
    assert not _quoted_substitutions("const d = `${{ steps.x.outputs.d }}`;")
    assert not _quoted_substitutions("const d = process.env.DIFF;")
    # An apostrophe in prose must not open a string and swallow the rest of the line. This is the
    # false positive that would have got this detector switched off: "don't" in a comment.
    assert not _quoted_substitutions("// don't splice ${{ steps.x.outputs.d }} here")
    assert not _quoted_substitutions("const apostrophe = \"it's fine\";")
    assert not _quoted_substitutions("/* don't ${{ steps.x.outputs.d }} */")
    # Deliberately conservative: a substitution inside a quoted string is reported whether or not
    # the value happens to contain a newline today. A URL fragment is the one shape that reads like
    # a false positive, and it is still a single-quoted splice — it just is not broken *yet*. The
    # alternative is a detector that reasons about which values are multi-line, which is exactly
    # the guessing this is meant to replace.
    assert _quoted_substitutions("const u = 'https://example.com/${{ steps.x.outputs.d }}';")


def test_the_reporting_step_still_parses_with_a_real_multi_line_diff() -> None:
    """End-to-end, with the value this workflow actually carries.

    This is the check that was missing: the gate suite was green, the workflow was green, and the
    one step that had anything to say was a syntax error. Rendering the real script with a real
    seven-line diff and asking node to parse it is the only version of the check that cannot be
    satisfied by a test that never renders anything.
    """
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is present in this repository's CI
        pytest.skip("node is not on PATH")

    step_name, body = next(
        (name, script) for name, script in _script_bodies(WORKFLOW.read_text(encoding="utf-8"))
        if "documented-gates-ratchet" in script
    )
    assert "${{" not in body, f"{step_name} must take the diff from the environment, not by splicing"

    diff = (
        "FAIL: the gate table in docs/ci-gates.md no longer matches ruleset 23826057.\n"
        "\n"
        "  the ruleset requires these, the document does not list them:\n"
        "    + security-scan\n"
        "\n"
        "  Read the ruleset back with the command in docs/ci-gates.md, update the table, and\n"
        "  keep the count out of the prose — the table's length is the count."
    )
    rendered = "async function run() {\n" + body.replace(
        "(process.env.DIFF || '')", repr(diff)) + "\n}\n"
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "report.mjs"
        script.write_text(rendered, encoding="utf-8")
        result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, f"the reporting step does not parse:\n{result.stderr}"


def test_the_workflow_opens_an_issue_only_for_a_real_divergence() -> None:
    """The branch structure is the fix for F2/F7, so it is pinned rather than described.

    Reads the conditions off the workflow itself: the report step must fire on exit 1 and on
    nothing else, and there must be a step that turns every other outcome red. A workflow that
    dropped the failure step would pass every other test in this file.
    """
    yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's steps")
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = (workflow["jobs"]["ratchet"]["steps"])
    report = next(s for s in steps if (s.get("with") or {}).get("script", "").find("documented-gates-ratchet") >= 0)
    guard = next(s for s in steps if s.get("name", "").startswith("Fail when the comparison"))

    assert report["if"] == "steps.compare.outputs.compare_exit == '1'", (
        "the report step must fire on the drift code and only on it — an expired token exits 2, "
        "and a 2 here opens a titled issue telling a maintainer to fix a correct document"
    )
    condition = guard["if"]
    assert "compare_exit != '0'" in condition and "compare_exit != '1'" in condition, (
        "the guard must be 'anything that is not a verdict', so an empty output from a step that "
        f"never ran is red too. Got: {condition!r}"
    )
    assert "steps.compare.outcome" not in str(report["if"]), (
        "`outcome` is success/failure/cancelled and cannot tell exit 1 from exit 2"
    )
