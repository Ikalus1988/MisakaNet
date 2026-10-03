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
* **What this file is *not* allowed to police.** The gate count only has to live in one place, and
  it is `docs/ci-gates.md`. Two classes of writing are explicitly out of scope, and a sweep that
  takes them in is wrong rather than thorough:

  * **Dated records** — `CHANGELOG.md`, and the `2026-09-22 会话交接` appendix in
    `docs/maintainer/state-of-the-repo.md`. Their sentences describe *the day they were written*.
    "0 条变为 3 条（DCO / test / gate）" is a fact about 2026-09-22 and cannot go stale; rewriting
    it to "从无到有（清单见 §2.1）" deletes the fact and points at a *different date's* list, which
    is a loss dressed as a cleanup. A hand-maintained count is only a bug when it claims to be
    current.
  * **Live sections that merely mention the set.** The same file's §2.1 is a current-state
    statement, and its count *is* the bug this change exists to remove — the ruleset has four
    contexts now and the text that says so by hand is what a reader trusts.

  The prose scanner this file replaced had an `EXCLUDED_FILES` map with a one-line reason per
  entry. That map went away with it, and its absence is what let a dated appendix be edited twice
  in one sitting — so the exclusion is written down here instead.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import string
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
#
# The Chinese branch is anchored on the same noun, and it has to be. `三条建议` ("three suggestions")
# and `一条命令` ("one command") are counts of something else — and an unanchored
# `[一二三四五六七八九十]\s*条` is *broader* than the repo-wide scanner it replaced, which anchored on
# `required|sign-off|status check|context`. A narrower scope does not pay for a looser anchor.
#
# The gap between the numeral and the noun is markdown, and it is the gap that matters: `**four**`
# checks, `四个门禁`, `四项必需检查`, `4 条检查`. The first version of this pattern allowed only
# whitespace and a four-word adjective list there, which meant it missed **the sentence this very
# branch deleted** from the section it guards — and a test that misses the real text is worse than
# no test, because it reads as coverage. Every phrase below is taken from this repository, not
# invented for the test.
COUNT_CLAIM = re.compile(
    r"(\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b|\d+)\s*"
    r"(?:\*\*|__|`)*\s*"                          # emphasis and code marks around the numeral
    r"(?:mandatory|required|hard|deterministic|blocking|enforced|main\s+branch\s+)?\s*"
    r"(?:\*\*|__|`)*\s*"
    r"(?:required\s+|status\s+|mandatory\s+)?"
    r"(?:gates?|checks?|contexts?)\b"
    r"|[一二三四五六七八九十\d]+\s*[条个项]\s*"
    r"(?:必需|必须|硬性|强制|状态)?\s*"
    r"(?:门禁|检查|门禁检查|必需检查|状态检查|硬门禁)"
    r"|(?:必需检查|状态检查|门禁)\s*(?:有|共|为)\s*[一二三四五六七八九十\d]+\s*[条个项]",
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


def test_the_marker_lookup_pages_and_cannot_match_a_pull_request() -> None:
    """The two ways "open or update one issue" turns into "open a new one every Monday".

    * **No pagination.** The repository carries ~160 open issues and intake adds more every day.
      An unpaginated `per_page: 100` sees roughly the last week — against a weekly schedule the
      marker issue leaves page 1 on the second or third run, `find` returns `undefined`, and the
      workflow opens a duplicate. The issue body itself promises "re-running the workflow
      refreshes this issue", so that is a broken promise rather than a cosmetic one.
    * **Pull requests are not issues.** `listForRepo` returns both, and `PATCH /issues/<n>`
      addresses a pull request number — so a PR whose description happened to contain this marker
      (plausible for any PR touching this very workflow) would have its body replaced.

    Read off the **parsed call arguments**, not off the script text. The first version asserted
    `"per_page: 100" in script`, and the workflow's own explanatory comment contains that literal
    string — so changing the code to `per_page: 50` left the test green. This is the anti-pattern
    `tests/test_workflow_env_is_used.py` records as having happened five times in this repository's
    gates, and it bit a test in a file whose docstring claimed "deleting either guard reddens this".
    """
    _, script = next(
        (name, body) for name, body in _script_bodies(WORKFLOW.read_text(encoding="utf-8"))
        if "documented-gates-ratchet" in body
    )
    assert "github.paginate(" in script, (
        "the marker lookup is not paginated, so it only ever sees the first 100 open items"
    )
    assert "issue.pull_request" in script, (
        "`listForRepo` returns pull requests too, and a PR's description is addressable as an "
        "issue — one containing this marker would be overwritten"
    )

    # The call, with its comments gone. A substring search over the raw script cannot tell the
    # two apart, and the comment is the one that is easy to leave behind when the code changes.
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("//"))
    call = code[code.index("listForRepo"):]
    call = call[:call.index(")") + 1]
    assert re.search(r"per_page:\s*100\b", call), (
        f"the paginated call's own page size was not found in {call!r}"
    )


def test_the_compare_step_keeps_continue_on_error() -> None:
    """The load-bearing assumption nobody could verify from the repository.

    Both later steps carry `if:` conditions with no status function, so GitHub evaluates the
    **implicit `success()`** — and an `if:` on a step that was skipped is false. `continue-on-error`
    is the only thing giving the compare step a `success` *conclusion* while its `outcome` is
    `failure`, which is what makes the two downstream steps run at all. Remove it and the job ends
    at the compare step: a real drift goes red with **no issue opened and no reason shown**, which
    is the one outcome this whole branch exists to prevent.

    This is a configuration value, not behaviour, so no test of the script can catch it losing.
    """
    yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's steps")
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    compare = next(
        step for step in workflow["jobs"]["ratchet"]["steps"] if step.get("id") == "compare"
    )
    assert compare.get("continue-on-error") is True, (
        "the compare step must keep continue-on-error: the downstream `if:` conditions have no "
        "status function, so they inherit the implicit success() and are skipped entirely "
        "without it — a drift would go red with no issue and no reason"
    )


def test_the_count_pattern_catches_the_claims_it_claims_to() -> None:
    """A guard on the guard: a pattern that matches nothing would pass the test above forever.

    Every phrase here is one this repository has used or could plausibly use. If a future edit
    makes the pattern narrower, this goes red instead.
    """
    for phrase in ("the 4 required checks", "four hard gates", "all three gates",
                   "五条必需检查", "四条门禁", "the Four required checks", "三条状态检查",
                   # Verbatim from the base commit of this branch — the sentences it deleted.
                   "Measured that way on 2026-09-29, **four** checks block a merge:",
                   "requires **four** status checks",
                   "三个必需检查",
                   "the 4 required status checks", "4 blocking checks", "the 4 contexts",
                   "四项必需检查", "四个门禁", "4 条检查", "必需检查有 4 条"):
        assert re.search(COUNT_CLAIM, phrase), f"the pattern misses a real claim: {phrase!r}"
    for phrase in ("Two notes on what those commands measure",
                   "Three notes that have each cost someone an afternoon",
                   "out of the nine test (…) legs", "the 3.11 leg", "9-leg matrix",
                   # The Chinese arm used to be unanchored, so it fired on any count of 条 —
                   # strictly broader than the scanner this replaced.
                   "三条建议", "这三条命令都很快", "一条命令即可", "读了五篇文章"):
        assert not re.search(COUNT_CLAIM, phrase), f"the pattern fires on a non-claim: {phrase!r}"


def test_advisory_tables_below_the_heading_are_not_counted() -> None:
    """A check that reports but cannot block is not one of the gates."""
    documented = checker.parse_documented(DOC)
    assert "PR Quality Gate" not in documented
    assert "coverage" not in documented
    for context in documented:
        assert "Hard Gates" not in context


def test_a_duplicate_heading_refuses_to_guess_which_table_is_authoritative() -> None:
    """The natural edit to this file is the dangerous one.

    The document's subject is now "this table is parsed by a ratchet", so the most natural
    documentation change is a fenced example of the table format in the preamble. A substring search
    for the heading finds that example, reads its placeholder cells as contexts, and reports that
    **all four gates are missing and one invented** — on a document whose table is byte-for-byte
    correct. Refusing on ambiguity is the only safe answer: two headings means the tool cannot know
    which one is authoritative, and guessing is how it opened an issue about a correct file.
    """
    with tempfile.TemporaryDirectory() as tmp:
        original = DOC.read_text(encoding="utf-8")
        example = (
            "## 门禁在哪里\n\n"
            "表格长这样：\n\n"
            f"```\n{checker.SECTION}\n\n| Check | Workflow |\n|---|---|\n| **example** | `x.yml` |\n```\n"
        )
        document = Path(tmp) / "d.md"
        document.write_text(original + "\n" + example, encoding="utf-8")
        saved = Path(tmp) / "r.json"
        saved.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        code, out, err = run_cli(["--from-file", str(saved), "--doc", str(document)])

    assert code == checker.EXIT_CANNOT_CHECK
    assert out == "", "an example in the preamble was read as the real table"
    assert "appears as a heading" in err


def test_a_preamble_mention_of_the_heading_is_not_another_heading() -> None:
    """The safe variant of the shape above, and it must still pass.

    Writing the section name inside a sentence — "the table under `## Hard Gates (must pass)` is the
    single statement of the set" — is the documentation edit somebody will actually make, and it
    leaves exactly one heading. A substring search would have found the sentence and parsed
    nothing; the line match ignores it and the document still verifies.
    """
    with tempfile.TemporaryDirectory() as tmp:
        document = Path(tmp) / "d.md"
        document.write_text(
            f"The table under `{checker.SECTION}` below is the single statement of the set.\n\n"
            + DOC.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        saved = Path(tmp) / "r.json"
        saved.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        code, out, _ = run_cli(["--from-file", str(saved), "--doc", str(document)])

    assert code == checker.EXIT_AGREE
    assert out.startswith(checker.OK_PREFIX)


def test_a_readable_ruleset_that_is_not_enforcing_is_not_a_match() -> None:
    """`docs/ci-gates.md` is titled *Hard Gates (must pass)*. A disabled ruleset is decorative.

    A set comparison asks *which* checks are named. It cannot tell a ruleset that blocks a merge
    from one that is switched off, aimed at tags, or exempted for some actors — and all three are
    stated in the document's own second paragraph, so all three are claims a reader relies on. With
    them unchecked, turning the ruleset off left the ratchet reporting a cheerful green.
    """
    for field, value, expected in (
        ("enforcement", "disabled", "enforcement"),
        ("enforcement", "evaluate", "enforcement"),
        ("target", "tag", "target"),
    ):
        payload = dict(RULESET_RESPONSE, **{field: value})
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / "r.json"
            saved.write_text(json.dumps(payload), encoding="utf-8")
            code, out, err = run_cli(["--from-file", str(saved), "--doc", str(DOC)])
        assert code == checker.EXIT_CANNOT_CHECK, f"{field}={value!r} reported a match"
        assert out == "", f"{field}={value!r} rendered a verdict"
        assert expected in err

    payload = dict(RULESET_RESPONSE, bypass_actors=[{"actor_id": 136884451, "actor_type": "Integration"}])
    with tempfile.TemporaryDirectory() as tmp:
        saved = Path(tmp) / "r.json"
        saved.write_text(json.dumps(payload), encoding="utf-8")
        code, out, err = run_cli(["--from-file", str(saved), "--doc", str(DOC)])
    assert code == checker.EXIT_CANNOT_CHECK
    assert "bypass_actors" in err


def test_decoration_is_stripped_from_both_sides_of_the_comparison() -> None:
    """One-sided normalisation made some live context permanently undocumentable.

    The document's cells were stripped of `` ` ``, `*`, `_` and the ruleset's contexts were not, so
    a context ending in `_` — markdown's emphasis marker — could never be written down in the table
    and the comparison failed forever with no edit that could fix it.
    """
    # The enforcement fields are carried even though they are not the point here: a payload
    # without them is refused by design, and weakening that check to suit a fixture would be the
    # wrong trade for a check whose whole job is failing closed.
    payload = {
        **RULESET_RESPONSE,
        "rules": [{"type": "required_status_checks", "parameters": {
            "required_status_checks": [{"context": "gate_"}]}}],
    }
    assert checker.contexts_from_ruleset(payload) == ["gate"], (
        "the ruleset side was not normalised"
    )
    with tempfile.TemporaryDirectory() as tmp:
        document = Path(tmp) / "d.md"
        document.write_text(
            f"# x\n\n{checker.SECTION}\n\n| Check | W |\n|---|---|\n| `gate_` | `a.yml` |\n",
            encoding="utf-8",
        )
        saved = Path(tmp) / "r.json"
        saved.write_text(json.dumps(payload), encoding="utf-8")
        code, out, _ = run_cli(["--from-file", str(saved), "--doc", str(document)])
    assert code == checker.EXIT_AGREE, f"a documented `gate_` did not match the live `gate_`: {out}"


def test_an_integer_one_from_the_script_cannot_become_a_verdict() -> None:
    """`sys.exit(1)` inside `main` would exit 1 — this script's own drift code.

    The guard was written as "an integer code is argparse talking", which is true of 0 and 2 and
    false of 1. Latent today because `main` has no `sys.exit(1)`, and that is exactly the kind of
    fact that stops being true when someone adds an argument.
    """
    for code in (1, 3, 99):
        original = checker.main
        checker.main = lambda argv=None: (_ for _ in ()).throw(SystemExit(code))
        try:
            got, out, _ = run_cli(["--doc", str(DOC)])
        finally:
            checker.main = original
        assert got == checker.EXIT_BROKEN, f"SystemExit({code}) escaped as {got}"
        assert out == ""


def test_the_detector_survives_a_regex_literal_containing_a_quote() -> None:
    """Third route to the same miss, and the one that hides best.

    `/['"]/` is not a string. A quote-naive scanner opens one at the `[`, never closes it, and the
    phantom state blinds the detector for the **rest of the body** — a three-line script reports
    zero offenders. Same failure as the escaped-quote defect, reached through a different door.
    """
    body = "const q = /['\"]/;\nconst a = 1;\nconst b = '${{ steps.x.outputs.d }}';"
    assert _quoted_substitutions(body), (
        "a regex literal opened a phantom string and hid a real splice two lines later"
    )
    # Both tokenizers must know about regex literals, and that redundancy is deliberate: the stripper
    # and the detector are two independent walks over the same line, and an earlier version taught
    # only one of them — which is how the same defect got in twice.
    #
    # The input here is a regex that *contains a comment marker*, which is the only case where the
    # stripper's handling changes its output. Asserting on `/['"]/` alone would pass either way,
    # because a line with no `//` survives the naive walk unchanged — a test that passes for the
    # wrong reason is the thing this branch keeps having to undo.
    slashes = "const u = /https?:\\/\\//;"
    assert _strip_js_comments(slashes) == slashes, (
        f"a // inside a regex literal was read as a comment: {_strip_js_comments(slashes)!r}"
    )
    assert not _quoted_substitutions(slashes + "\nconst b = process.env.DIFF;")
    # ...and division is not mistaken for a regex
    assert not _quoted_substitutions("const r = (n) / 2;\nconst b = process.env.DIFF;")
    assert not _quoted_substitutions("const r = 4 / 2;\nconst b = process.env.DIFF;")


def test_the_output_heredoc_terminators_are_not_a_fixed_string() -> None:
    """A context whose name contains the terminator would otherwise discard every output.

    `report()` renders each difference as `    + <context>`, so no ordinary line can equal
    `DIFF_EOF` — but a context *containing a newline* could, the heredoc would close early, the
    runner would reject the whole output file as malformed, and **every** output would be
    discarded including `compare_exit`. A real drift would then go red with no issue and no reason.
    Randomising the terminator costs two lines and removes the possibility rather than reasoning
    about it.
    """
    # The heredoc lives in the compare step's `run:` block, not in a github-script body, so the
    # script extractor is the wrong reader here.
    yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's steps")
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    compare = next(
        step for step in workflow["jobs"]["ratchet"]["steps"] if step.get("id") == "compare"
    )
    script = compare["run"]
    code_lines = [line for line in script.splitlines() if "<<" in line or "EOF=" in line]
    assert code_lines, "the heredoc block was not found in the compare step"
    assert not any(re.search(r"<<\s*['\"]?[A-Z_]*EOF\b", line) for line in code_lines), (
        f"a fixed heredoc terminator is still in use: {code_lines}"
    )
    assert "urandom" in script, "the terminators must be randomised per run"


def test_a_renamed_or_missing_section_fails_loudly() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        broken = Path(tmp) / "ci-gates.md"
        broken.write_text("# something else\n\nno section here\n", encoding="utf-8")
        try:
            checker.parse_documented(broken)
        except checker.GateDocumentUnreadable as error:
            assert checker.SECTION in str(error)
        else:  # pragma: no cover - only reached if the guard is removed
            raise AssertionError("a missing section must fail, not parse to an empty set")


def test_a_renamed_section_exits_cannot_check_and_never_the_drift_code() -> None:
    """The test above passed for the wrong reason, and the exit code is what the workflow reads.

    `parse_documented` raised `SystemExit` **with a string**, and CPython exits **1** for a
    non-integer `SystemExit` code — 1 being this script's own "the document has drifted". So a
    renamed heading produced `compare_exit=1` with an empty stdout, the report step fired, the
    guard step (which fires for anything that is not 0 or 1) was skipped, and the job went **green
    with a confidently wrong issue open**. That is the exact defect the previous commit claimed to
    eliminate, re-entering through a one-word change to a heading.

    Asserting the exception in-process cannot see this. Only the process's exit code can.
    """
    with tempfile.TemporaryDirectory() as tmp:
        renamed = Path(tmp) / "ci-gates.md"
        renamed.write_text(
            DOC.read_text(encoding="utf-8").replace(checker.SECTION, "## Hard Gates (required)"),
            encoding="utf-8",
        )
        saved = Path(tmp) / "ruleset.json"
        saved.write_text(json.dumps(RULESET_RESPONSE), encoding="utf-8")
        code, out, err = run_cli(["--from-file", str(saved), "--doc", str(renamed)])

    assert code == checker.EXIT_CANNOT_CHECK, (
        f"a renamed section exited {code}; {code} is the drift code, and the workflow opens an "
        "issue for it"
    )
    assert code != checker.EXIT_DIVERGED
    assert out == "", "a verdict reached stdout that was never rendered"
    assert checker.SECTION in err


def test_a_system_exit_with_a_string_can_never_become_a_verdict() -> None:
    """The mechanism, pinned — because the fix is a guard, and a guard needs a test.

    `SystemExit("...")` is not an error code; CPython prints it and exits **1**. That is the same
    exit code `report()` returns for a real divergence, and nothing downstream can tell them
    apart. The guard maps a non-integer code to `EXIT_BROKEN`.
    """
    original = checker.main
    checker.main = lambda argv=None: (_ for _ in ()).throw(SystemExit("a string, not a code"))
    try:
        code, out, err = run_cli(["--doc", str(DOC)])
    finally:
        checker.main = original
    assert code == checker.EXIT_BROKEN
    assert code != checker.EXIT_DIVERGED
    assert out == ""
    assert "a string, not a code" in err


def test_argparses_own_exit_codes_still_pass_through() -> None:
    """The guard must not swallow `--help` or a bad flag.

    `argparse` raises `SystemExit(0)` for `--help` and `SystemExit(2)` for a bad argument, and both
    are *intentional* exit codes. A guard that treated every `SystemExit` as a crash would turn
    `check_documented_gates.py --help` into a failure.
    """
    for argv, expected in ((["--help"], 0), (["--no-such-flag"], 2)):
        with pytest.raises(SystemExit) as raised:
            run_cli(argv)
        assert raised.value.code == expected, f"{argv} should exit {expected}"


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

    Escapes are honoured, and that is not optional. Comparing `line[index] == in_string` raw means
    `"x \" // not a comment"` closes the string at the escaped quote, the `//` is then read as a
    comment, the line truncates, and a **real** splice later on the same line goes unseen. Both
    halves of that were reproduced before this was fixed.

    **Regex literals** are the third route to the same miss, and the one that hides best: `/['"]/`
    is not a string, but a quote-naive scanner opens one that never closes, and the phantom state
    then blinds the detector for the *rest of the body* — a three-line script reports zero
    offenders. So a `/` is only treated as a regex when a regex can actually start there and end on
    this line; otherwise it stays an ordinary character and a division sign is not mistaken for one.
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
                if line[index] == "\\" and index + 1 < len(line):
                    result.append(line[index + 1])  # an escaped char cannot close the string
                    index += 2
                    continue
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
            # A regex literal, checked *after* the comment forms: `//` reads as an empty regex
            # to a scanner that looks for a closing slash first, and swallowing it means the rest
            # of the line is parsed as code.
            if line[index] == "/" and result[-1:] not in (")", "]", "}", *string.digits):
                end = _regex_end(line, index)
                if end < len(line):  # a regex that closes on this line, not a division
                    result.append(line[index:end + 1])
                    index = end + 1
                    continue
            char = line[index]
            if char in "'\"`":
                in_string = char
            result.append(char)
            index += 1
        out.append("".join(result))
    return "\n".join(out)


def _regex_end(line: str, start: int) -> int:
    """Where a regex literal opened at `start` closes on this line, or `len(line)`."""
    index = start + 1
    in_class = False
    while index < len(line):
        char = line[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return index
        index += 1
    return len(line)


def _quoted_substitutions(body: str) -> list[str]:
    """Where a `${{ }}` sits inside a `'…'` or `"…"` string — including across lines.

    A template literal may span lines, so `` `${{ x }}` `` is fine and must not be reported, which
    is why the check tracks quote state rather than searching for a pattern. Resetting that state
    at every newline is the obvious simplification and it is wrong: a `github-script` body that
    opens a quoted string on one line and splices a value into it on the next is *precisely* the
    F1 shape, and it parses as a `SyntaxError` under `node --check` — verified, not assumed.
    """
    offenders = []
    state = ""
    for number, line in enumerate(_strip_js_comments(body).splitlines(), start=1):
        stripped = line.strip()
        if state in ("'", '"') and stripped.startswith("${{"):
            offenders.append(f"{state}-quoted across lines: {stripped}")
            state = ""
            continue
        index = 0
        while index < len(line):
            if line.startswith("${{", index) and state in ("'", '"'):
                offenders.append(f"{state}-quoted: {line.strip()}")
                break
            # The same regex-literal skip as the comment stripper. Two independent tokenizers over
            # the same line is how this defect got in twice: the stripper learned about regexes and
            # the detector, which re-walks the stripped text with its own state machine, did not.
            if state == "" and line[index] == "/" and line[index:index + 2] not in ("//", "/*") \
                    and line[index - 1:index] not in (")", "]", "}", *string.digits):
                end = _regex_end(line, index)
                if end < len(line):
                    index = end + 1
                    continue
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


def test_the_detector_survives_an_escaped_quote_earlier_on_the_line() -> None:
    """Reproduced false negative: the escaped quote closed the string, then `//` ate the rest.

    `_strip_js_comments` compared the closing quote with `==`, so the `\"` inside
    `"x \" // not a comment"` ended the string, the `//` was then read as a comment, the line was
    truncated, and a real splice on the same line was never seen. Both halves of that are guarded
    here: the escape is honoured, and the comment marker inside a string is not one.
    """
    assert _quoted_substitutions(
        'const a = "x \\" // not a comment"; const b = \'${{ steps.x.outputs.d }}\';'
    ), "an escaped quote must not let a later splice on the same line go unseen"
    # ...and the inverse: with the escape honoured, that `//` stays inside the string
    assert not _quoted_substitutions('const a = "x \\" // not a comment";')


def test_the_detector_survives_a_quote_opened_on_one_line_and_spliced_on_the_next() -> None:
    """Reproduced false negative, and the *realistic* form of F1.

    Resetting quote state at each newline is the obvious simplification, and it misses exactly the
    shape that broke the first version of this workflow:

        const diff = '
        ${{ steps.compare.outputs.diff }}
        '.trim();

    That is a genuine `SyntaxError` under `node --check`, and it is what the mutation below
    reconstructs — so "the one-line shape is caught" was never enough on its own.
    """
    body = "const diff = '\n${{ steps.compare.outputs.diff }}\n'.trim();"
    assert _quoted_substitutions(body)
    node = shutil.which("node")
    if node:  # pragma: no branch - node is present in this repository's CI
        rendered = "async function run() {\n" + body + "\n}\n"
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "m.mjs"
            script.write_text(rendered, encoding="utf-8")
            result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
        assert result.returncode != 0, "the premise is a script node rejects"


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
