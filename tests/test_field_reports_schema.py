#!/usr/bin/env python3
"""Both directions of `scripts/check_field_reports.py` (issue #2042).

Why this file exists
--------------------
On 2026-09-21 three field reports were closed for carrying **zero executable evidence**, and #1976
claimed a verified run whose quoted `tools/list` returned **1** tool against a live endpoint that
returns **7**, on the host `misakanet.com` (ours is `misakanet.org`). Every one of those was caught by
a human reading carefully. A gate replaces that with a machine that reads the same things, so the two
things that can go wrong have to be pinned here:

* **a compliant report must pass** — otherwise the gate is a toll booth, and the next submission is
  written to please it rather than to be checkable;
* **every rule must be able to go red** — a rule that cannot fail is not a rule. That is what the
  `RED_CASES` table below is for, and `test_every_gating_rule_has_a_red_case` fails if a rule is ever
  added without one, so the table cannot rot into decoration.

The third case is the mutation criterion in the issue itself ("删掉一个必填字段能让它红"): deleting a
required field from an otherwise valid report must turn the gate red. Concretely that is FR7 —
`test_deleting_a_required_field_turns_the_gate_red`.

Nothing here reads or writes the real `docs/field-reports/` corpus except the one test that proves
the checker can parse it; the corpus's own violations are a finding to report, not a test to make
green (weakening a rule until the legacy prose passes is the defect this issue is about).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_field_reports.py"
CORPUS = REPO / "docs" / "field-reports"


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_field_reports", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Registering it is not optional: `@dataclass` resolves annotations through `sys.modules`, and a
    # module that is only half-loaded dies with "'NoneType' object has no attribute '__dict__'".
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()

# A report that satisfies every rule: the client and the installer in versions, the config file it
# wrote, the live host, `tools/list` with the number the endpoint actually returns, and the search
# envelope rather than a description of it. This is the shape a submission is asked to have.
COMPLIANT = """\
# Field report: codex against the live endpoint

> **Client**: codex 0.154.0 (installer `@misaka-net/misakanet-setup@0.5.5`)
> **Config**: `~/.codex/config.toml` (`streamable-http`)
> **Endpoint**: https://misakanet.org/mcp

`codex mcp list` shows the server enabled, and `tools/list` returned 7 tools:
`misakanet_register`, `misakanet_search`, `misakanet_get_lesson`, `misakanet_submit_intake`,
`misakanet_write_lesson`, `misakanet_preflight`, `misakanet_me_events`.

The search call came back as this envelope (query `pip install timeout`):

```json
{"jsonrpc":"2.0","id":1,"result":{"results":[{"id":"pip-timeout-proxy","score":0.91}]}}
```
"""

# rule id -> (what was mutated, the report text). Each entry must trip *its* rule.
RED_CASES: dict[str, tuple[str, str]] = {
    "FR1-endpoint-host": (
        "the endpoint is spelled `misakanet.com` (the #1976 mistake)",
        COMPLIANT.replace("https://misakanet.org/mcp", "https://misakanet.com/mcp"),
    ),
    "FR2-tool-count": (
        "`tools/list` is reported as returning 1 tool",
        COMPLIANT.replace("returned 7 tools", "returned 1 tool"),
    ),
    "FR3-home-path": (
        "an unredacted home path is pasted in",
        COMPLIANT + "\nI ran this from `/home/eric_jia/work` (WSL).\n",
    ),
    "FR4-search-envelope": (
        "the search result is paraphrased instead of quoted",
        COMPLIANT.replace(
            '```json\n{"jsonrpc":"2.0","id":1,"result":{"results":[{"id":"pip-timeout-proxy",'
            '"score":0.91}]}}\n```',
            "It returned a structured result with one hit.\n",
        ),
    ),
    "FR5-tools-list-count": (
        "`tools/list` is quoted but no count is stated",
        COMPLIANT.replace("returned 7 tools", "returned the tool list"),
    ),
    "FR6-client-version": (
        "the client/installer version is deleted",
        COMPLIANT.replace(
            "> **Client**: codex 0.154.0 (installer `@misaka-net/misakanet-setup@0.5.5`)\n",
            "> **Client**: codex\n",
        ),
    ),
    "FR7-config-path": (
        "the config path the client wrote is deleted",
        COMPLIANT.replace("> **Config**: `~/.codex/config.toml` (`streamable-http`)\n", ""),
    ),
}

# Rules that only annotate scope. FR8 must never gate: a frontend health check is not a setup report,
# and failing it for not being one would train people to stop writing honest reports. It still gets a
# case here, in both directions, because "info" must not become "unchecked".
INFO_RULES = {"FR8-no-run-claim"}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def _corpus(tmp_path: Path, **files: str) -> Path:
    """A throw-away field-report directory, so no test can touch the real corpus."""
    corpus = tmp_path / "field-reports"
    corpus.mkdir(exist_ok=True)
    for name, text in files.items():
        (corpus / f"{name}.md").write_text(text, encoding="utf-8")
    return corpus


def test_a_compliant_report_passes(tmp_path: Path):
    result = _run("--dir", str(_corpus(tmp_path, good=COMPLIANT)))
    assert result.returncode == 0, f"a compliant report must pass:\n{result.stdout}{result.stderr}"
    assert "verdict=PASS" in result.stdout, result.stdout
    for rule in CHECKER.RULES:
        assert rule not in result.stdout, f"{rule} fired on a compliant report:\n{result.stdout}"


def test_every_gating_rule_has_a_red_case():
    """Guard the guard: a rule with no red case in `RED_CASES` is an unenforced promise."""
    gating_rules = {r for r, (severity, _) in CHECKER.RULES.items() if severity != "info"}
    missing = gating_rules - set(RED_CASES)
    assert not missing, (
        f"{sorted(missing)} would never be shown to fail by this file; add a mutation to RED_CASES "
        f"(a check that cannot go red is a defect)")
    assert set(CHECKER.RULES) - gating_rules == INFO_RULES, (
        "info rules changed: pin the new ones with their own two-direction tests")


@pytest.mark.parametrize("rule", sorted(RED_CASES))
def test_each_rule_goes_red(tmp_path: Path, rule: str):
    what, text = RED_CASES[rule]
    assert text != COMPLIANT, f"the {rule} mutation changed nothing — it cannot prove anything"
    result = _run("--dir", str(_corpus(tmp_path, bad=text)))
    assert result.returncode == 1, f"{rule} ({what}) did not turn the gate red:\n{result.stdout}"
    assert rule in result.stdout, f"{rule} ({what}) reported something else:\n{result.stdout}"
    assert "verdict=FAIL" in result.stdout, result.stdout


@pytest.mark.parametrize("rule", sorted(RED_CASES))
def test_each_rule_is_silent_on_the_compliant_report(tmp_path: Path, rule: str):
    """The other direction, per rule: green input must not produce that finding."""
    result = _run("--dir", str(_corpus(tmp_path, good=COMPLIANT)))
    assert rule not in result.stdout, f"{rule} fires on valid input:\n{result.stdout}"


def test_deleting_a_required_field_turns_the_gate_red(tmp_path: Path):
    """The issue's own mutation criterion: one field removed, gate red, nothing else changed."""
    corpus = _corpus(tmp_path, good=COMPLIANT)
    clean = _run("--dir", str(corpus))
    assert clean.returncode == 0, clean.stdout

    (corpus / "good.md").write_text(
        COMPLIANT.replace("> **Config**: `~/.codex/config.toml` (`streamable-http`)\n", ""),
        encoding="utf-8",
    )
    mutated = _run("--dir", str(corpus))
    assert mutated.returncode == 1, f"removing the config path left the gate green:\n{mutated.stdout}"
    assert "FR7-config-path" in mutated.stdout, mutated.stdout


def test_a_report_that_declines_a_surface_is_not_punished_for_honesty(tmp_path: Path):
    """`2026-09-20-gemini-cli-mcp-headless.md` is the model: it says what it could not test.

    A gate that fails "I could not verify this" gets reports that stop saying it, which is strictly
    worse than the state this issue is fixing.
    """
    honest = """\
# Field report: gemini CLI headless

Endpoint https://misakanet.org/mcp answered `tools/list` with 7 tools.

I could not run the client session: the `gemini` CLI is not installed on this host, so the
`misakanet_search` live call is **未验证 (unverified)**. `~/.gemini/settings.json` parsing is
**not verified** either — the recipe below is from the docs, not from a local run.
"""
    result = _run("--dir", str(_corpus(tmp_path, honest=honest)))
    assert result.returncode == 0, (
        f"an honest 'unverified' report was failed:\n{result.stdout}")
    for rule in ("FR4-search-envelope", "FR6-client-version", "FR7-config-path"):
        assert rule not in result.stdout, f"{rule} fired inside a declined window:\n{result.stdout}"


def test_the_declined_escape_hatch_cannot_launder_a_wrong_claim(tmp_path: Path):
    """Saying "unverified" must not make a wrong host or a wrong number acceptable."""
    text = """\
# Field report

Endpoint https://misakanet.com/mcp — unverified, could not be tested.
`tools/list` returned 1 tool (未验证, not from a local run).
"""
    result = _run("--dir", str(_corpus(tmp_path, bad=text)))
    assert result.returncode == 1, result.stdout
    assert "FR1-endpoint-host" in result.stdout, result.stdout
    assert "FR2-tool-count" in result.stdout, result.stdout


def test_a_report_with_no_endpoint_claim_is_reported_as_out_of_scope(tmp_path: Path):
    """No live-endpoint claim: the schema's fields do not apply, and that is *stated*, not silent."""
    result = _run("--dir", str(_corpus(tmp_path, frontend="# Frontend health check\n\nAll green.\n")))
    assert result.returncode == 0, result.stdout
    assert "FR8-no-run-claim" in result.stdout, result.stdout
    assert "verdict=PASS" in result.stdout, result.stdout


def test_info_findings_never_gate_even_corpus_wide(tmp_path: Path):
    """An out-of-scope report inside a diff must not fail somebody's PR."""
    corpus = _corpus(tmp_path, good=COMPLIANT, frontend="# Frontend health check\n")
    result = _run("--dir", str(corpus), "--changed", str(corpus / "good.md"))
    assert result.returncode == 0, result.stdout
    assert "legacy:" in result.stdout and "FR8-no-run-claim" in result.stdout, result.stdout


def test_changed_only_mode_reports_legacy_findings_without_gating_them(tmp_path: Path):
    """The `lesson-gate.yml` precedent: legacy debt is visible on every run, gating only on touch."""
    corpus = _corpus(tmp_path, good=COMPLIANT, legacy=RED_CASES["FR7-config-path"][1])
    untouched = _run("--dir", str(corpus), "--changed", str(corpus / "good.md"))
    assert untouched.returncode == 0, f"a legacy file gated an unrelated diff:\n{untouched.stdout}"
    assert "legacy: legacy.md" in untouched.stdout, untouched.stdout

    strict = _run("--dir", str(corpus))
    assert strict.returncode == 1, "the same corpus must fail when every file is in scope"


def test_a_wrong_host_gates_even_when_the_file_is_untouched(tmp_path: Path):
    """FR1 is the one rule the issue says to judge red outright, so it is not diff-scoped."""
    corpus = _corpus(tmp_path, good=COMPLIANT, bad=RED_CASES["FR1-endpoint-host"][1])
    result = _run("--dir", str(corpus), "--changed", str(corpus / "good.md"))
    assert result.returncode == 1, f"`misakanet.com` survived in an untouched file:\n{result.stdout}"
    assert "FR1-endpoint-host" in result.stdout, result.stdout


def test_a_directory_that_does_not_exist_is_cannot_run_not_pass(tmp_path: Path):
    """"Could not run" must never look like a clean pass (repo convention: exit 2)."""
    result = _run("--dir", str(tmp_path / "nope"))
    assert result.returncode == 2, result.stdout
    assert "cannot run" in result.stderr, result.stderr


def test_an_unresolvable_base_ref_is_cannot_run_not_pass():
    """A bad `--base` silences every finding, which is the worst possible way to fail open.

    Run against the real corpus on purpose: the point is that an unusable ref exits 2 *whatever* the
    reports say, so this cannot be satisfied by finding nothing.
    """
    result = _run("--dir", str(CORPUS), "--base", "no-such-ref-9f3c1")
    assert result.returncode == 2, f"an unresolvable base reported a verdict:\n{result.stdout}"
    assert "cannot run" in result.stderr, result.stderr
    assert "verdict=" not in result.stdout, "a run that could not resolve its base must not print one"


def test_the_instruction_page_is_not_judged_as_a_submission(tmp_path: Path):
    """`README.md` holds the template and the redaction examples; it is not a report.

    The `/home/<user>/` it tells authors to write must not be read as the leak the rule forbids.
    """
    readme = ("# Field Reports\n\nNo home paths: redact them to `/home/<user>/` or `C:\\Users\\<user>`.\n"
              "\n> **Date**: YYYY-MM-DD\n> **Author**: Your Name\n")
    corpus = _corpus(tmp_path, good=COMPLIANT)
    (corpus / "README.md").write_text(readme, encoding="utf-8")
    result = _run("--dir", str(corpus))
    assert result.returncode == 0, f"the instruction page was judged as a report:\n{result.stdout}"
    assert "README.md" not in result.stdout, result.stdout


def test_yaml_and_json_submissions_are_validated_too(tmp_path: Path):
    """The schema is emitted as YAML *or* JSON (#1784), so a submission may arrive in either.

    A checker that only ever opens `*.md` would pass a `report.yaml` by never reading it — the
    failure mode this repository keeps rediscovering.
    """
    corpus = tmp_path / "field-reports"
    corpus.mkdir()
    (corpus / "report.yaml").write_text(
        "endpoint: https://misakanet.com/mcp\nendpoint-tools: 1\n", encoding="utf-8")
    (corpus / "report.json").write_text(
        '{"endpoint": "https://misakanet.org/mcp", "note": "tools/list returned 3 tools"}',
        encoding="utf-8")
    result = _run("--dir", str(corpus))
    assert result.returncode == 1, result.stdout
    assert "report.yaml:1: FR1-endpoint-host" in result.stdout, result.stdout
    assert "report.yaml:2: FR2-tool-count" in result.stdout, result.stdout
    assert "report.json:1: FR2-tool-count" in result.stdout, result.stdout


def test_the_real_corpus_is_readable():
    """The checker runs over `docs/field-reports/` for real — this pins "it parses", not "it passes".

    Asserting the corpus is green would invert the point of the issue: a rule that the existing
    reports cannot satisfy is either a wrong rule or a finding, and both are for a human to decide.
    The maintainer's standard is that the gate must be able to fail, so an exit code of 1 here is a
    legitimate answer; a crash, a traceback or a missing summary is not.
    """
    result = _run("--dir", str(CORPUS))
    assert result.returncode in (0, 1), f"the checker could not read the corpus:\n{result.stderr}"
    assert "SUMMARY" in result.stdout, result.stdout
    assert "Traceback" not in result.stderr, result.stderr
    assert "verdict=" in result.stdout, result.stdout
    # Every file in the directory is scanned, so a rename cannot silently drop one from scope.
    on_disk = {p.name for p in CORPUS.iterdir() if p.is_file() and p.suffix in CHECKER.SUFFIXES}
    summary = next(line for line in result.stdout.splitlines() if line.startswith("SUMMARY"))
    scanned = int(summary.split("files=", 1)[1].split()[0])
    assert scanned == len(on_disk), f"scanned {scanned} of {len(on_disk)} files: {summary}"
    named = {line.split(":", 1)[0] for line in result.stdout.splitlines() if ": FR" in line}
    assert named <= on_disk, f"findings name files that do not exist: {named - on_disk}"


def test_rule_ids_are_unique_and_namespaced():
    """A finding has to be greppable back to the rule that produced it."""
    for rule, (severity, purpose) in CHECKER.RULES.items():
        assert rule.startswith("FR") and "-" in rule, rule
        assert severity in {"truth", "evidence", "info"}, rule
        assert purpose.strip(), f"{rule} has no documented purpose"
