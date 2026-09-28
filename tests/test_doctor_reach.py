#!/usr/bin/env python3
"""Every check `doctor.py` defines must have a CI call site that actually runs it (#1822).

`scripts/doctor.py` had three checks and one CI caller. `deploy-worker.yml` ran
`doctor.py --kv-only …`, and `--kv-only` **returned before `CHECKS`** — so `check_remote_endpoint`,
the only check that talks to the deployed service, ran nowhere. It was not that the check was wrong:
its bar had already been tightened twice, with the reasoning written out in the code. It was that
nobody ran it, and nothing said so.

The fix is a call site (`deploy-worker.yml`, post-deploy). This is the part that keeps it: the test
does not assert "the workflow contains the string `--remote-only`" — it parses the real command lines
out of the workflows and asks `doctor.selection()` which checks each one runs, then fails if any check
in `CHECKS` is unclaimed. Add a fourth check and this goes red until something runs it.

The ordering assertion is the other half. A reachability probe placed *before* the deploy proves
nothing about what was deployed, and moving the step would otherwise look harmless.
"""
from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
sys.path.insert(0, str(REPO / "scripts"))

import doctor  # noqa: E402  (after sys.path, and deliberately the real module)

DOCTOR_RE = re.compile(r"python3\s+scripts/doctor\.py([^\n|>;&]*)")


def _joined_runs() -> list[tuple[str, int, str]]:
    """(workflow, line number, command) for every `doctor.py` invocation in a `run:` block.

    Continuations are joined first: `python3 scripts/doctor.py \\\n  --remote-only` is one command,
    and a parser that reads single lines would miss exactly the multi-flag forms this gate exists for.
    """
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        text = text.replace("\\\n", " ")          # shell line continuation
        for match in DOCTOR_RE.finditer(text):
            line = text[: match.end()].count("\n") + 1
            found.append((path.name, line, ("python3 scripts/doctor.py" + match.group(1)).strip()))
    return found


def test_the_gate_can_see_the_invocations_it_is_about():
    """A regex that matches nothing would make every assertion below vacuous."""
    invocations = _joined_runs()
    assert invocations, "no workflow invokes scripts/doctor.py — this gate would pass on anything"
    assert any("--kv-only" in cmd for _, _, cmd in invocations), invocations


def test_every_check_is_either_run_in_ci_or_declared_local_only():
    """Both halves are required: a check with no CI caller must be *declared* local-only, with a
    reason. The defect in #1822 was the silence — nothing distinguished "CI does not run this
    because it cannot mean anything there" from "nobody ever wired it up"."""
    claimed: dict[str, list[str]] = {}
    for name, _, cmd in _joined_runs():
        for selected in doctor.selection(shlex.split(cmd)[2:]):
            claimed.setdefault(selected, []).append(f"{name}: {cmd}")

    unaccounted = [name for name, _ in doctor.CHECKS
                   if name not in claimed and name not in doctor.LOCAL_ONLY]
    assert unaccounted == [], (
        f"these doctor.py checks are run by nothing in CI and are not declared local-only: "
        f"{unaccounted}.\n"
        + "\n".join(f"  claimed: {k} ← {v[0]}" for k, v in sorted(claimed.items()))
        + "\nA check with no call site and no declaration is a comment. Give it a workflow step, or "
          "add it to LOCAL_ONLY in scripts/doctor.py with the reason it cannot mean anything in CI "
          "(`--kv-only` returned before CHECKS, which is how check 3 had no reader for months)."
    )


def test_a_local_only_exemption_names_a_real_check_and_says_why():
    """An exemption is a decision, and a decision has to survive being read: a typo in the name would
    silently exempt nothing (green forever), and an empty reason would exempt without an argument."""
    names = {n for n, _ in doctor.CHECKS}
    for name, reason in doctor.LOCAL_ONLY.items():
        assert name in names, f"LOCAL_ONLY names {name!r}, which is not a check — the exemption is dead"
        assert len(reason) > 40, f"{name} is exempted without a real reason: {reason!r}"


def test_no_flag_is_the_only_way_to_reach_a_check_silently():
    """Every selection must name its checks: bare `doctor.py` is everything except the post-deploy-only
    ones, and each flag selects exactly the checks it declares."""
    assert doctor.selection([]) == [name for name, _ in doctor.CHECKS
                                    if name not in doctor.POST_DEPLOY_ONLY]
    for flag, names in doctor.FLAG_CHECKS.items():
        for name in names:
            assert name in [n for n, _ in doctor.CHECKS], (flag, name)
        assert doctor.selection([flag]) == list(names), flag
    # Flags compose rather than override — `--kv-only --post-deploy` is a legitimate request.
    both = doctor.selection(["--kv-only", "--post-deploy"])
    assert set(both) == {"config", "remote", "deployed-version"}, both


def test_the_deploy_probe_runs_after_the_deploy():
    """Ordering is load-bearing: probing before the deploy measures the *previous* worker."""
    text = (WORKFLOWS / "deploy-worker.yml").read_text(encoding="utf-8")
    deploy_at = text.index("npx wrangler deploy")
    probe_at = text.index("--post-deploy")
    assert probe_at > deploy_at, (
        "the handshake + version probe is placed before `npx wrangler deploy`, so it verifies the "
        "worker that is about to be replaced"
    )
    # The version read-back only makes sense against what actually landed, so it has to be in the
    # same post-deploy probe rather than a separate pre-deploy one.
    assert "--post-deploy" in text, text[:200]


def test_the_deploy_probe_retries_before_calling_the_service_broken():
    """Measured while wiring this: three consecutive probes from one machine gave 200, a connection
    timeout, and 200. A single-attempt gate on a flaky path is the expensive kind of red."""
    text = (WORKFLOWS / "deploy-worker.yml").read_text(encoding="utf-8")
    assert re.search(r"ATTEMPTS=\d+", text), "no retry budget"
    attempts = int(re.search(r"ATTEMPTS=(\d+)", text).group(1))
    assert attempts >= 3, f"{attempts} attempts is not enough to survive an intermittent timeout"
    assert "sleep" in text, "the retries need a gap, or they are one attempt with extra steps"


def test_main_runs_exactly_what_selection_promises(monkeypatch):
    """The reach test reads `selection()` out of the workflow command lines, so `selection()` has to
    describe `main()` rather than a hopeful model of it.

    This replaces an earlier assertion that the old `--kv-only` early return was absent from the
    source: that pinned a string, and the mutation run showed it was checking nothing useful — the
    early return's *shape* was never the defect. Its real defect was that it was the only call site,
    which is what the reach test above now catches.
    """
    ran: list[str] = []

    def recorder(name):
        def _run(*_args):
            ran.append(name)
            return True, name
        return _run

    monkeypatch.setattr(doctor, "CHECKS", tuple((n, recorder(n)) for n, _ in doctor.CHECKS))

    for argv in ([], ["--kv-only"], ["--remote-only"], ["--kv-only", "--remote-only"]):
        ran.clear()
        assert doctor.main(list(argv)) == 0, argv
        assert ran == doctor.selection(list(argv)), (
            f"{argv}: main() ran {ran} but selection() promised {doctor.selection(list(argv))}"
        )


def test_a_failing_check_still_fails_the_run_through_a_subset(monkeypatch):
    """`--remote-only` is the deploy gate: its exit code is what turns "deployed" into "verified"."""
    def broken():
        return False, "handshake failed"

    monkeypatch.setattr(doctor, "CHECKS", (("remote", broken),))
    assert doctor.main(["--remote-only"]) == 1


@pytest.mark.parametrize("flag,expected", [("--kv-only", "config"), ("--remote-only", "remote")])
def test_each_flag_selects_exactly_one_named_check(flag, expected, monkeypatch):
    """The CLI contract, executed rather than described: a fake check records what ran."""
    ran: list[str] = []

    def fake(name):
        def _run(*_args):
            ran.append(name)
            return True, name
        return _run

    monkeypatch.setattr(doctor, "CHECKS", tuple((n, fake(n)) for n, _ in doctor.CHECKS))
    assert doctor.main([flag]) == 0
    assert ran == [expected], ran
