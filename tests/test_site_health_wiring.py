#!/usr/bin/env python3
"""`site-health.yml` must actually probe, and it must not report one bad probe as an outage.

`scripts/site_health_check.py` (#783) had no CI call site: the newest snapshot in `docs/maintainer/`
was dated 2026-08-10, so the public surface went six weeks without a measurement between releases. The
workflow added here is the call site, and this file is what keeps it honest — the step's shell is
**executed**, against a stub probe whose verdicts the test chooses, rather than scanned for keywords.

What that buys, in the four things that would otherwise rot silently:

* the step's verdict comes from `--strict` (a step that runs the probe and ignores its exit code looks
  exactly like a passing one);
* a single failed probe is retried, and a healthy one is not (retrying unconditionally would make the
  daily job a burst of requests for nothing);
* attempts are *bounded* — a real outage must fail the run, not loop;
* a `workflow_dispatch` input reaches the probe as one argument, not as shell code.

The retry budget matters more than it looks. `docs/maintainer/handoff-2026-09-24.md` records ~1 request
in 4 to misakanet.org timing out from a real machine while the service was fine — so "unhealthy once"
is weather, and a probe that reddens the day on weather is a probe people mute.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from posix_shell import require_posix_shell
from subprocess_env import POSIX_PATH, child_env

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "site-health.yml"
SCRIPT = "scripts/site_health_check.py"

pytestmark = pytest.mark.skipif(
    not WORKFLOW.exists(), reason="site-health.yml does not exist (yet?) — nothing to wire"
)

FAKE_PROBE = '''#!/usr/bin/env python3
"""Stand-in for the real probe: records its argv and exits with the verdict it was told to."""
import json, os, pathlib, sys

calls = pathlib.Path(os.environ["FAKE_CALLS"])
seen = json.loads(calls.read_text()) if calls.exists() else []
seen.append(sys.argv[1:])
calls.write_text(json.dumps(seen))
verdicts = json.loads(os.environ["FAKE_VERDICTS"])
print(f"fake probe: call {len(seen)}, argv={sys.argv[1:]}")
sys.exit(verdicts[min(len(seen) - 1, len(verdicts) - 1)])
'''


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def probe_step() -> dict:
    """The step that runs the probe — found by what it runs, not by its name."""
    for step in workflow()["jobs"]["probe"]["steps"]:
        if SCRIPT in (step.get("run") or ""):
            return step
    raise AssertionError(f"no step in {WORKFLOW.name} runs {SCRIPT}")


def run_probe(tmp_path: Path, verdicts: list[int], base_url: str = "") -> dict:
    """Execute the workflow's probe step against a stub probe. Returns what happened."""
    step = probe_step()
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "site_health_check.py").write_text(FAKE_PROBE, encoding="utf-8")

    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    # `sleep` is a no-op: the *delay* between attempts is not the contract under test, the number of
    # attempts and the verdict they produce are. Without this the retry tests would take a real minute.
    (bindir / "sleep").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    (bindir / "sleep").chmod(0o755)
    # `python3` must exist for the step's own spelling of the command, whatever the interpreter here is.
    (bindir / "python3").write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    (bindir / "python3").chmod(0o755)

    calls = tmp_path / "calls.json"
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    env = child_env({
        "PATH": f"{bindir}:{POSIX_PATH}",
        "HOME": str(tmp_path),
        "GITHUB_STEP_SUMMARY": str(summary),
        "FAKE_CALLS": str(calls),
        "FAKE_VERDICTS": json.dumps(verdicts),
        "BASE_URL": base_url,
    })
    proc = subprocess.run(
        [require_posix_shell(), "-c", step["run"]],
        cwd=tmp_path, capture_output=True, text=True, env=env,
    )
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "calls": json.loads(calls.read_text()) if calls.exists() else [],
        "summary": summary.read_text(encoding="utf-8"),
        "tmp_path": tmp_path,
    }


# ── the wiring, executed ────────────────────────────────────────────────────────────
def test_a_transient_failure_is_retried_and_the_run_still_succeeds(tmp_path):
    """Two bad probes then a good one: the service is up, and the job must not cry outage."""
    result = run_probe(tmp_path, verdicts=[1, 1, 0])
    assert result["returncode"] == 0, result["stdout"] + result["stderr"]
    assert len(result["calls"]) == 3, f"expected a third attempt, got {result['calls']}"
    assert "Attempt 3/3" in result["summary"], result["summary"]


def test_a_healthy_probe_is_not_retried(tmp_path):
    """Retrying a passing probe would spend requests to learn what one already said."""
    result = run_probe(tmp_path, verdicts=[0])
    assert result["returncode"] == 0, result["stdout"] + result["stderr"]
    assert len(result["calls"]) == 1, f"healthy probe ran {len(result['calls'])} times"


def test_a_persistent_failure_fails_the_run_without_looping(tmp_path):
    """The other half: a real outage must fail — bounded, not for ever."""
    result = run_probe(tmp_path, verdicts=[1])
    assert result["returncode"] != 0, "a permanently unhealthy surface reported success"
    assert len(result["calls"]) == 3, f"attempts must be bounded: {len(result['calls'])}"
    report = result["tmp_path"] / "site-health-report.md"
    assert report.exists(), "no report kept for the failing run"
    assert "fake probe" in report.read_text(encoding="utf-8"), "the kept report is not the probe's output"


def test_the_verdict_comes_from_the_probe_not_from_the_step(tmp_path):
    """`--strict` is the difference between running the probe and *checking* with it."""
    result = run_probe(tmp_path, verdicts=[0])
    assert result["calls"], "the step did not run the probe at all"
    for argv in result["calls"]:
        assert "--strict" in argv, f"probe ran without --strict: {argv}"


def test_a_dispatch_input_reaches_the_probe_as_one_argument(tmp_path):
    """A `workflow_dispatch` input is free text; interpolated into `run:` it becomes shell code."""
    hostile = "https://example.invalid/; touch pwned"
    result = run_probe(tmp_path, verdicts=[0], base_url=hostile)
    assert result["returncode"] == 0, result["stdout"] + result["stderr"]
    assert result["calls"] == [["--base-url", hostile, "--strict"]], result["calls"]
    assert not (tmp_path / "pwned").exists(), "the input was executed as shell, not passed as an argument"


def test_no_base_url_argument_when_the_input_is_empty(tmp_path):
    """The scheduled run has no inputs; passing an empty `--base-url` would override the default with ''."""
    result = run_probe(tmp_path, verdicts=[0])
    assert result["calls"], "the step did not run the probe at all"
    assert "--base-url" not in result["calls"][0], result["calls"][0]


def test_the_dispatch_input_is_not_interpolated_into_the_shell():
    """The other half of the test above, which only sees the shell: *how* the value gets there.

    `run_probe` hands the value in as an environment variable the way GitHub does, so it cannot notice
    a step that writes `${{ inputs.base-url }}` straight into the script — GitHub substitutes that
    before bash ever sees it, and the stub would never be the wiser. So the wiring is checked here
    instead: the value travels in `env`, and no `${{ }}` expression appears in the script at all.
    """
    step = probe_step()
    assert "${{" not in step["run"], "an expression in `run:` is substituted into shell code before bash runs"
    assert "base-url" in str(step.get("env") or {}), "the dispatch input is not reaching the step through `env`"


def test_the_step_does_not_expand_an_array_under_set_u():
    """bash 3.2 is `/bin/bash` on macOS, and there `"${arr[@]}"` on an **empty** array is `unbound variable`
    under `set -u` (bash 4.4+ expanded it happily). Both macos legs went red on exactly that — five tests in
    this file, run 36108206753 — and the step would have died before its first probe on any 3.2 bash.
    Positional parameters (`set -- …`, `"$@"`) behave the same on both.
    """
    run = probe_step()["run"]
    assert "set -u" in run or "set -euo" in run, (
        "this rule exists because the step runs under `set -u`; if that changed, revisit the rule")
    # Comments are stripped: the comment explaining this bug quotes the spelling it bans, and a rule that
    # cannot tell code from prose flags its own documentation (the raw-field rule learned the same thing).
    offenders = [line for line in run.splitlines()
                 if "[@]" in line and not line.lstrip().startswith("#")]
    assert not offenders, (
        "an array expansion under `set -u` is a bash-3.2 error when the array is empty — use `set --` and "
        '`"$@"` instead:\n' + "\n".join(offenders))


# ── the schedule itself ─────────────────────────────────────────────────────────────
def test_the_workflow_is_scheduled_and_dispatchable():
    """A call site nobody triggers is still no call site."""
    # YAML 1.1 reads a bare `on:` as the boolean True, so both spellings are checked.
    triggers = workflow().get("on") or workflow().get(True) or {}
    assert triggers.get("schedule"), f"{WORKFLOW.name} has no schedule — the probe would only run by hand"
    assert triggers.get("workflow_dispatch"), f"{WORKFLOW.name} cannot be run on demand"


def test_the_probe_job_asks_for_no_write_permissions():
    """It is a read-only GET probe; anything beyond `contents: read` is authority it does not need."""
    permissions = workflow()["jobs"]["probe"].get("permissions") or workflow().get("permissions") or {}
    assert permissions == {"contents": "read"}, permissions


def test_the_command_the_step_runs_exists_in_this_repository():
    """Guard the guard: the wiring test above substitutes a stub for this path."""
    assert (REPO / SCRIPT).is_file(), f"{SCRIPT} is gone but {WORKFLOW.name} still claims to probe with it"
    argv = shlex.split(probe_step()["run"])
    assert SCRIPT in argv, f"the step mentions {SCRIPT} only inside a comment: {argv}"
