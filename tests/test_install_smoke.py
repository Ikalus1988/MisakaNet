#!/usr/bin/env python3
"""The install smoke's two claims must be checkable without running a workflow (owner D3 = A, 2026-09-30).

`.github/workflows/install-smoke.yml` exists because every previous green about installing MisakaNet came
from metadata (npm `dist-tags`, the MCP registry read-back, our own CI on a checkout) and a reader reported
treating "automatic check passed" as "it works" (intake #2486, point 3). A workflow that only runs on a
runner would be untestable here — the same shape as a gate nobody can make go red — so the two probes'
decision logic lives in `scripts/install_smoke.py` as pure functions, and this file mutates them.

What is pinned, and why each one is a *fact* rather than prose:

* the npm tarball's member list (missing entry point, or a leaked `scripts/` — the intake #2486 confusion);
* the MCP row's URL (a local row means an npm install has no server to reach, #1734);
* the stdio tool set, measured against `docs/mcp.md` rather than against the server's own `TOOLS` (#1822's
  lesson: an expectation read from the file under test cannot disagree with it);
* the badge's verdict rules — red names the failing form, absent evidence publishes nothing;
* the workflow's *shape*: the two probe jobs are independent and the git+ job measures the runner's own
  `python3`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.install_smoke import (  # noqa: E402
    HOSTED_URL,
    documented_stdio_tools,
    mcp_row_problems,
    tarball_problems,
)
from scripts.update_install_badge import FORM_FILES, badge_for, load_results  # noqa: E402

WORKFLOW = REPO / ".github" / "workflows" / "install-smoke.yml"


# ── the npm form: what a tarball may and may not contain ──────────────────────────────────────────

GOOD_MEMBERS = ["package/SKILL.md", "package/skills/misakanet/SKILL.md", "package/index.js",
                "package/cordis.patch.yml", "package/package.json"]


def test_a_skill_only_tarball_passes():
    assert tarball_problems(GOOD_MEMBERS) == []


def test_a_missing_entry_point_is_caught():
    problems = tarball_problems([m for m in GOOD_MEMBERS if m != "package/index.js"])
    assert problems and "package/index.js" in problems[0], problems


def test_the_local_server_leaking_into_the_npm_tarball_is_caught():
    """The intake #2486 fact: the npm form has no `scripts/`, so its row points at the hosted endpoint."""
    problems = tarball_problems(GOOD_MEMBERS + ["package/scripts/mcp_server.py"])
    assert problems and "package/scripts/" in problems[0], problems


# ── the npm form: the row that makes the tools reachable ──────────────────────────────────────────

def _real_patch_and_index() -> tuple[str, str]:
    return ((REPO / "cordis.patch.yml").read_text(encoding="utf-8"),
            (REPO / "index.js").read_text(encoding="utf-8"))


def test_the_shipped_row_wires_the_hosted_endpoint():
    assert mcp_row_problems(*_real_patch_and_index()) == []


def test_a_row_pointing_somewhere_else_is_caught():
    patch, index = _real_patch_and_index()
    broken = patch.replace(HOSTED_URL, "http://127.0.0.1:8765/mcp")
    assert broken != patch, "the mutation did not take"
    problems = mcp_row_problems(broken, index)
    assert any("cordis.patch.yml" in p for p in problems), problems


def test_a_local_command_row_is_caught():
    """A stdio row in the patch would make the npm install depend on a process the tarball omits."""
    patch, index = _real_patch_and_index()
    broken = patch.replace("        transport: streamable-http",
                           "        transport: stdio\n        command: python3")
    assert broken != patch, "the mutation did not take"
    problems = mcp_row_problems(broken, index)
    assert any("command:" in p for p in problems), problems


def test_a_url_inside_a_comment_is_not_read_as_the_row():
    """`cordis.patch.yml` explains the old arrangement in comments; a parser that accepted a commented URL
    would pass a patch whose real row pointed anywhere."""
    patch = ("# url: https://misakanet.org/mcp  (what the comments mention)\n"
             "        url: http://127.0.0.1:8765/mcp\n")
    index = "  url: 'https://misakanet.org/mcp',\n"
    problems = mcp_row_problems(patch, index)
    assert any("cordis.patch.yml" in p for p in problems), problems


# ── the git+ form: the tool set is a document's claim, not the server's ───────────────────────────

def test_the_documented_stdio_tool_set_is_read_from_the_document():
    documented = documented_stdio_tools((REPO / "docs" / "mcp.md").read_text(encoding="utf-8"))
    # 10 since 2026-09-30 (intake #2486, D4): `misakanet_me_events` was hosted-only, so the skill's own
    # reuse-evidence step failed on a local install. The local server now proxies it, which makes the hosted
    # set a strict subset of the local one — the mirror image of the old asymmetry.
    assert len(documented) == 10, sorted(documented)
    assert "misakanet_search" in documented
    assert "misakanet_me_events" in documented, (
        "the local surface must include me_events now that it proxies it; the probe's whole point is that "
        "the documented set and the measured set agree")
    # …and the three local-only tools are what still distinguishes the surfaces.
    assert {"misakanet_submit_usage", "misakanet_usage_status", "misakanet_memory_context"} <= documented


def test_the_documented_set_matches_what_the_server_actually_registers():
    """Document (expectation) vs `misakanet/server/TOOLS` (measurement) — two files, so they can disagree."""
    pytest.importorskip("misakanet.server", reason="the local server package is the measurement leg")
    from misakanet.server import TOOLS  # noqa: PLC0415

    registered = {tool["name"] for tool in TOOLS}
    documented = documented_stdio_tools((REPO / "docs" / "mcp.md").read_text(encoding="utf-8"))
    assert documented == registered, {
        "documented only": sorted(documented - registered),
        "registered only": sorted(registered - documented),
    }


def test_a_missing_stdio_row_is_an_error_not_an_empty_set():
    with pytest.raises(ValueError, match="local stdio"):
        documented_stdio_tools("| something else | nothing |\n")


# ── the badge: red names the form, absent evidence publishes nothing ──────────────────────────────

def _payload(ok: bool, form: str = "npm") -> dict:
    return {"form": form, "ok": ok, "result_count": 3, "tool_count": 7, "timestamp": "2026-09-30T06:43:00Z"}


def test_both_forms_ok_is_green_with_the_date():
    badge = badge_for({"npm": _payload(True, "npm"), "git": _payload(True, "git")}, "2026-09-30")
    assert badge == {"schemaVersion": 1, "label": "install verified",
                     "message": "verified 2026-09-30", "color": "brightgreen"}


def test_a_failed_form_publishes_red_and_names_it():
    badge = badge_for({"npm": _payload(False, "npm"), "git": _payload(True, "git")}, "2026-09-30")
    assert badge["color"] == "red" and "npm" in badge["message"], badge


@pytest.mark.parametrize("present", [{}, {"npm": _payload(True, "npm")}, {"git": _payload(True, "git")}])
def test_half_the_evidence_publishes_nothing(present):
    """Green off one form would be "green from metadata" in miniature: the missing form is not a pass."""
    assert badge_for(present, "2026-09-30") is None


def test_a_measured_failure_wins_over_a_missing_form():
    """Absent evidence keeps yesterday's badge; a *measured* failure must replace it with red."""
    badge = badge_for({"git": _payload(False, "git")}, "2026-09-30")
    assert badge["color"] == "red" and "git" in badge["message"], badge


def test_results_are_read_from_the_artifact_names_the_workflow_uploads():
    assert set(FORM_FILES.values()) == {"install-npm.json", "install-git.json"}


def test_a_missing_result_file_is_not_an_error(tmp_path):
    assert load_results(tmp_path) == {}


def test_an_unparseable_result_file_fails_instead_of_publishing(tmp_path):
    """A file the probe wrote but this script cannot read is a shape change, not a missing measurement."""
    (tmp_path / FORM_FILES["npm"]).write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit, match="cannot be read"):
        load_results(tmp_path)


def test_a_result_without_a_verdict_fails_instead_of_publishing(tmp_path):
    (tmp_path / FORM_FILES["git"]).write_text(json.dumps({"form": "git"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="no `ok` field"):
        load_results(tmp_path)


# ── the workflow's shape is part of the design, so it is asserted rather than remembered ──────────

@pytest.fixture()
def workflow() -> dict:
    yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_workflow_runs_daily_and_on_demand(workflow):
    triggers = workflow.get("on") or workflow.get(True) or {}
    assert "schedule" in triggers and "workflow_dispatch" in triggers, sorted(triggers)
    assert [entry["cron"] for entry in triggers["schedule"]] == ["43 6 * * *"]


def test_the_two_probes_are_independent(workflow):
    """The hosted call is burst-limited: a throttled npm job must not be able to fail the stdio job."""
    jobs = workflow["jobs"]
    assert not (jobs["npm-form"].get("needs") or []), "the npm probe must not wait on anything"
    assert not (jobs["git-stdio"].get("needs") or []), "the stdio probe must not wait on the hosted call"
    assert sorted(jobs["publish-install-badge"]["needs"]) == ["git-stdio", "npm-form"]


def test_the_git_probe_measures_the_runners_own_python(workflow):
    """`python3 >= 3.10` is the documented prerequisite; a setup-python step would assert the pin instead."""
    steps = workflow["jobs"]["git-stdio"]["steps"]
    assert not any(str(step.get("uses", "")).startswith("actions/setup-python") for step in steps), (
        "setup-python would replace the interpreter the probe is supposed to measure")
    assert any("install_smoke.py git-stdio" in (step.get("run") or "") for step in steps)


def test_both_probe_jobs_keep_their_evidence_even_when_they_fail(workflow):
    """The publisher's red-vs-nothing distinction depends on the artifact existing after a failed probe."""
    for job_name in ("npm-form", "git-stdio"):
        uploads = [step for step in workflow["jobs"][job_name]["steps"]
                   if str(step.get("uses", "")).startswith("actions/upload-artifact")]
        assert len(uploads) == 1, f"{job_name} must upload exactly one artifact"
        assert uploads[0].get("if") == "always()", f"{job_name}'s upload must run on failure too"
        assert uploads[0]["with"]["if-no-files-found"] == "warn", (
            "a failed upload would turn one failure into a different one")


def test_the_install_guide_references_the_badge_instead_of_a_hand_written_status():
    """The guide's "What verified means here" table must *point at* the measurement, not claim one.

    Asserted on filenames (a fact a reader can resolve), not on prose: `badges/install.json` is the
    shields endpoint the badge lives at, and `install-smoke.yml` is the workflow that writes it.
    """
    guide = (REPO / "docs" / "dsh-installation.md").read_text(encoding="utf-8")
    assert "data/badges/install.json" in guide, "the install guide does not reference the smoke badge"
    assert "install-smoke.yml" in guide, "the install guide does not name what produces the badge"
