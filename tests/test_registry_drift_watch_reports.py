#!/usr/bin/env python3
"""`registry-drift-watch.yml` must be able to report the drift it exists to detect.

The workflow has never done so. `scripts/verify-glama-listing.py` exits 1 today (13 tools on the
Glama listing, 8 served), the last runs are all `success` (2026-10-10 … 2026-10-15), the step's own
log ends `##[error]Process completed with exit code 1.` with no `### Attempt` line and no
`::warning::attempt … was not OK` ever executed, and

    gh issue list --state all \
      --search "The Glama MCP listing no longer matches the tools we serve in:title"

is empty — the tracking issue has never existed.

The cause is the interpreter, not the loop. Actions runs a `run:` block as `bash -e {0}` (the run
log says `shell: /usr/bin/bash -e {0}`), and `set -uo pipefail` adds `u` and `o` **without clearing
`-e`**. So the first probe that exited 1 ended the script at that line: `status=$?` never ran,
`compare_exit` never reached `$GITHUB_OUTPUT`, every `if: steps.compare.outputs.compare_exit == '1'`
was false, and `continue-on-error: true` turned the abort into a green run. `set +e` before the loop
is the fix; this file is what keeps it there.

Why the step body is *executed* rather than pattern-matched, or extracted into `scripts/`
------------------------------------------------------------------------------------------
A static assertion for the substring `set +e` is satisfied by the comment that explains `set +e` —
the trap `test_shell_invocations_are_portable.py` and `test_lesson_quality_gate_can_fail.py` both
had to strip comments to avoid. And extracting the loop into a `scripts/` helper would test it
*outside* the shell that carries `-e`: a child bash does not inherit errexit (`SHELLOPTS` is not
exported), so the helper would run in an environment where the original silence cannot reproduce.
The defect lives in the interaction between the step text and the interpreter Actions launches it
with, so the fixture below takes the step's actual `run:` text out of the YAML, hands it to
`bash -e`, and reads the outputs back — the same execution the runner performs, with the network
replaced by a stub probe at the script's own path.

It goes red against the bytes from before the fix, which is the only reason to trust it:

    git show fe55c7d6^:.github/workflows/registry-drift-watch.yml > /tmp/pre-fix.yml
    MISAKANET_DRIFT_WATCH_YML=/tmp/pre-fix.yml \
      python3 -m pytest tests/test_registry_drift_watch_reports.py -q
    # → 2 failed, 4 passed

`fe55c7d6` is the commit that fixed the step, so `fe55c7d6^` is the last revision that still had the
defect. This recipe used to say `git show origin/main:…`, which stopped being the pre-fix bytes the
moment the fix merged: a reproduction step that names a moving ref expires without saying so. It names
a commit now.

`MISAKANET_DRIFT_WATCH_YML` exists for that proof; CI never sets it.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest

yaml = pytest.importorskip("yaml", reason="the step body is read out of the workflow YAML")

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = REPO / ".github" / "workflows" / "registry-drift-watch.yml"
PROBE = "scripts/verify-glama-listing.py"

sys.path.insert(0, str(REPO / "tests"))
from posix_shell import candidates, works  # noqa: E402

#: What a drift report looks like on stdout; the stub writes it so the `report` output is read from
#: something shaped like the real probe's output rather than from a placeholder.
_STUB_PROBE = """\
import os
import sys

print("Local MCP tools: 8 (register, search, get_lesson, submit_intake, write_lesson, ...)")
print("Glama tools:     13")
print("Stale on Glama (removed locally): ['misakanet_cli', 'misakanet_get_my_events']")
sys.exit(int(os.environ["STUB_PROBE_EXIT"]))
"""


def _workflow_path() -> pathlib.Path:
    override = os.environ.get("MISAKANET_DRIFT_WATCH_YML")
    return pathlib.Path(override) if override else DEFAULT_WORKFLOW


def _compare_step(path: pathlib.Path) -> dict:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(s for s in workflow["jobs"]["glama"]["steps"] if s.get("id") == "compare")


def _require_bash() -> str:
    """A bash that runs, because the step uses the bashism `set -o pipefail` and Actions uses bash.

    `posix_shell` is the repository's owner of "which shell is real"; this narrows its candidate
    list to bash rather than accepting the `/bin/sh` fallback, which would fail on `pipefail` for a
    reason that has nothing to do with the step.
    """
    for candidate in candidates():
        if "bash" in pathlib.Path(candidate).name.lower() and works(candidate):
            return candidate
    pytest.skip("no usable bash in this environment; the step under test is bash-specific")


def _outputs(text: str) -> dict:
    """`$GITHUB_OUTPUT`: `key=value` lines, plus `key<<DELIM` … `DELIM` for multi-line values.

    The step publishes the report through a heredoc, so the flat `key=value` split the other
    harnesses in this suite use would swallow it into the wrong key.
    """
    parsed: dict = {}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if "<<" in line:
            key, delimiter = line.split("<<", 1)
            body = []
            index += 1
            while index < len(lines) and lines[index] != delimiter:
                body.append(lines[index])
                index += 1
            parsed[key.strip()] = "\n".join(body)
        elif "=" in line:
            key, value = line.split("=", 1)
            parsed[key.strip()] = value.strip()
        index += 1
    return parsed


def _run_body(tmp_path: pathlib.Path, body: str, probe_exit: int):
    """Execute a step body the way Actions does: `bash -e`, real `$GITHUB_OUTPUT`, a stub probe."""
    root = tmp_path / f"repo-exit-{probe_exit}"
    (root / "scripts").mkdir(parents=True)
    (root / PROBE).write_text(_STUB_PROBE, encoding="utf-8")

    # The retry budget is two 30-second pauses on the all-fail path; the subject here is the
    # reporting, not the pacing, so `sleep` is shimmed rather than waited on.
    shim = root / "bin"
    shim.mkdir()
    (shim / "sleep").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (shim / "sleep").chmod(0o755)

    script = root / "step.sh"
    script.write_text(body, encoding="utf-8")

    outputs = root / "gh_output"
    summary = root / "gh_summary"
    outputs.write_text("", encoding="utf-8")
    summary.write_text("", encoding="utf-8")

    env = dict(os.environ)
    env["PATH"] = f"{shim}{os.pathsep}{env['PATH']}"
    env["GITHUB_OUTPUT"] = str(outputs)
    env["GITHUB_STEP_SUMMARY"] = str(summary)
    env["STUB_PROBE_EXIT"] = str(probe_exit)

    done = subprocess.run(
        [_require_bash(), "-e", str(script)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return done, _outputs(outputs.read_text(encoding="utf-8")), summary.read_text(encoding="utf-8")


def _run_compare_step(tmp_path: pathlib.Path, probe_exit: int):
    return _run_body(tmp_path, _compare_step(_workflow_path())["run"], probe_exit)


# ── the invocation the fixture reproduces ───────────────────────────────────────────────────────

def test_the_compare_step_takes_the_runner_default_shell():
    assert "shell" not in _compare_step(_workflow_path()), (
        "the fixture executes the step under the runner's default `bash -e {0}`; a custom `shell:` "
        "would mean the invocation under test is not the one Actions uses, and `bash -e {0}` is "
        "exactly the interaction this gate exists for"
    )


# ── the step actually runs, and actually reports ────────────────────────────────────────────────

def test_drift_publishes_the_outputs_the_reporting_branches_read(tmp_path):
    done, outputs, summary = _run_compare_step(tmp_path, probe_exit=1)

    assert outputs.get("compare_exit") == "1", (
        f"exit 1 from the probe must reach `compare_exit`, or the annotate and issue branches "
        f"cannot fire: outputs={outputs!r}\nstdout={done.stdout}\nstderr={done.stderr}"
    )
    assert outputs.get("attempts") == "3", (
        "one failing probe is weather — the three-attempt budget has to be spent before the verdict"
    )
    assert "Stale on Glama" in outputs.get("report", ""), (
        f"the issue body is built from token `report`: outputs={outputs!r}"
    )
    assert done.stdout.count("::warning::attempt") == 3, (
        f"each failed attempt must surface its own annotation: stdout={done.stdout!r}"
    )
    assert "### Attempt 3/3" in summary, f"the job summary lost its verdict: {summary!r}"


def test_a_matching_listing_publishes_exit_0_and_stops_at_one_attempt(tmp_path):
    done, outputs, summary = _run_compare_step(tmp_path, probe_exit=0)

    assert outputs.get("compare_exit") == "0", f"outputs={outputs!r}\nstderr={done.stderr}"
    assert outputs.get("attempts") == "1", "a first-attempt success must not sleep and retry"
    assert "::warning::" not in done.stdout, f"nothing was wrong: stdout={done.stdout!r}"
    assert "### Attempt 1/3" in summary


def test_a_probe_that_could_not_answer_is_not_recorded_as_0_or_1(tmp_path):
    done, outputs, _ = _run_compare_step(tmp_path, probe_exit=2)

    assert outputs.get("compare_exit") == "2", (
        f"'Glama unreachable' must stay distinguishable from both agreement and drift — the issue "
        f"branch keys on exactly 1: outputs={outputs!r}\nstderr={done.stderr}"
    )
    assert outputs.get("attempts") == "3", "an unreachable host is also retried to the budget"


def test_the_fixture_goes_red_on_the_shape_that_shipped(tmp_path):
    """Guard the guard: the shape that shipped reported nothing, so the assertions above cannot be
    passing for a reason unrelated to the defect.

    The historical shape is rebuilt by deleting the `-e` guard from the step. Against the bytes on
    `main` there is no guard to delete, so the mutation is a no-op and this becomes a direct
    statement about the text that shipped (see the module docstring for that invocation).
    """
    body = _compare_step(_workflow_path())["run"]
    guards = ("set +e", "set +o errexit")
    mutated = "\n".join(line for line in body.splitlines() if line.strip() not in guards) + "\n"

    done, outputs, _ = _run_body(tmp_path, mutated, probe_exit=1)

    assert done.returncode == 1 and not outputs, (
        f"a compare step that aborts under `-e` on the first bad probe published a verdict it "
        f"never reached (exit={done.returncode}, outputs={outputs!r}). If the guard is spelled "
        f"differently now, teach this mutation that spelling {guards} — an unmutable fixture is "
        f"the shape this test rules out."
    )


# ── the branches that consume those outputs ─────────────────────────────────────────────────────

def _condition(step: dict) -> str:
    return " ".join(str(step.get("if", "")).replace("${{", "").replace("}}", "").split())


_COMPARE_EXIT = "steps.compare.outputs.compare_exit"
_CLAUSE = re.compile(r"^(?P<ref>[A-Za-z_][\w.]*)\s*(?P<op>==|!=)\s*'(?P<literal>[^']*)'$")


def _clause(clause: str, values: dict[str, str]) -> bool:
    """One `<ref> == '<literal>'` (or `!=`) clause, taken from the branch's real `if:` text."""
    match = _CLAUSE.match(clause.strip())
    if match is None:
        raise AssertionError(
            "this evaluator knows only `<ref> == '<literal>'` and `<ref> != '<literal>'` clauses. "
            "The branch's real condition is neither, and the test will not guess at it — teach the "
            f"evaluator the new shape on purpose. Offending clause: {clause!r}")
    if match["ref"] not in values:
        raise AssertionError(
            f"the branch reads {match['ref']!r}, which this test does not model. It exists to prove "
            "the branches key off the compare step's exit output, so another output here is a change "
            "that should be looked at rather than evaluated.")
    return ((values[match["ref"]] == match["literal"]) if match["op"] == "=="
            else (values[match["ref"]] != match["literal"]))


def _fires(condition: str, compare_exit: str) -> bool:
    """Whether an `if:` fires for a given value of the compare step's exit output.

    The conditions compare `steps.compare.outputs.compare_exit` against string literals, and this
    reads that **real text** rather than a hand-copied second statement, so a branch that stops
    keying off `compare_exit` fails here instead of drifting away from it.

    Two clauses are interpreted here instead of handing the text to Python's `eval`. That is a
    deliberate trade, not a dodge: `eval` accepts *any* expression the workflow later grows — 
    including one this test does not model — and then reports a verdict about it that it cannot
    justify. A shape the interpreter below does not know fails loudly, which is the direction that
    gets a human to look, and a code scanner is right to flag `eval` in a test even when the input
    is repository-owned.
    """
    if "(" in condition or ")" in condition:
        raise AssertionError(
            "the condition grew parentheses; this evaluator implements no precedence rules and will "
            f"not guess at them: {condition!r}")
    values = {_COMPARE_EXIT: compare_exit}
    # `&&` binds tighter than `||`, which is the only precedence these conditions use.
    for alternative in condition.split("||"):
        if all(_clause(part, values) for part in alternative.split("&&")):
            return True
    return False


def test_the_branches_still_key_off_compare_exit():
    steps = yaml.safe_load(_workflow_path().read_text(encoding="utf-8"))["jobs"]["glama"]["steps"]
    by_name = {s["name"]: s for s in steps if "name" in s}
    annotate = by_name["Annotate the divergence"]
    issue = by_name["Open or update the drift issue"]
    fail = by_name["Fail when the comparison could not be made"]

    # 0 — they agree: nothing annotated, nothing opened, green.
    assert not _fires(_condition(annotate), "0") and not _fires(_condition(issue), "0")
    assert not _fires(_condition(fail), "0"), "agreement is not a reason to redden the run"

    # 1 — they differ: annotated, one tracking issue, and still green (the header's choice: a watch
    # that is red every day for a tracked defect is the one people mute).
    assert _fires(_condition(annotate), "1") and _fires(_condition(issue), "1")
    assert not _fires(_condition(fail), "1")

    # 2 — could not probe: red, and no issue, because "we could not ask" is not "the listing is
    # wrong" and an issue saying so sends a maintainer to re-publish a correct listing.
    assert _fires(_condition(fail), "2") and not _fires(_condition(issue), "2")

    # '' — the compare step never wrote its outputs (an abort): red, the fail-closed direction that
    # `!= '0' && != '1'` was written for.
    assert _fires(_condition(fail), "") and not _fires(_condition(issue), "")
