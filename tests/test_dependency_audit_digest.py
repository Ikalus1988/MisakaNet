#!/usr/bin/env python3
"""The scheduled dependency audit (#2684) has one job beyond finding CVEs: not lying when it cannot
answer.

`pr-checks.yml` runs `pip-audit` and `npm audit` only when a pull request touches a dependency file.
That answers "did this pull request introduce a bad dependency?" and never answers "has a dependency
that was already in the tree become bad?" — the CVE arrives on its own schedule, nothing in a pull
request moves, and nothing goes red. The scheduled half exists for that case.

So the contract under test is narrow and specific:

* **"could not run" is not "clean".** A tool that never executed has not found nothing; it has
  answered nothing. A digest that opens with "found 0" while listing failures underneath is read as
  a clean audit by anyone skimming it, and that is how a gate quietly stops meaning anything. This is
  the same `查不了 ≠ 文档错了` distinction the ratchet work landed on, in a different script.
* **A real finding is a real finding.** The table has to name the package and the advisory, because
  a digest that cannot be acted on is a notification, not a report.
* **The clean path may claim clean, and only the clean path.**

Network calls are not exercised here. `pip-audit` and `npm audit` are subprocesses, and a test that
depends on either one is a test that fails when the network does.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "audit_dependencies", REPO / "scripts" / "audit_dependencies.py"
)
assert _spec and _spec.loader
audit = importlib.util.module_from_spec(_spec)
# `dataclasses` resolves annotations through `sys.modules[cls.__module__]`, and a module built by
# `module_from_spec` is not registered there. Without this line every `@dataclass` in the script
# raises `AttributeError: 'NoneType' object has no attribute '__dict__'` at import — a failure that
# looks like a dataclasses bug and is not one.
sys.modules[_spec.name] = audit
_spec.loader.exec_module(audit)


def _result(status, ecosystem="pypi", tool="pip-audit", findings=(), detail=""):
    return audit.AuditResult(ecosystem, tool, status, detail=detail, findings=list(findings))


def _finding(**kw):
    base = dict(ecosystem="pypi", package="mcp", version="2.2.0",
                advisory="GHSA-xxxx-yyyy-zzzz", severity="high", fixed_in="2.3.1")
    base.update(kw)
    return audit.Finding(**base)


# ── the contract: could not run is not clean ────────────────────────────────────────────────────

def test_both_unavailable_never_reports_clean():
    """The failure this whole script exists to avoid, and the one an earlier draft of the digest
    got wrong: it opened with "found 0 known-vulnerable package(s)" and only then listed two tools
    that had not run."""
    digest = audit.render_digest([
        _result("unavailable", "pypi", detail="pip-audit is not on PATH"),
        _result("unavailable", "npm", tool="npm audit", detail="registry has no audit endpoint"),
    ])
    assert audit.CLEAN_LINE not in digest
    # A count of zero is the specific lie. Checking only that CLEAN_LINE is absent is not enough:
    # a digest can avoid the green checkmark and still open with "found 0", which reads the same way
    # to anyone skimming it. Mutation-testing found this — the first version of this test passed
    # against a `render_digest` that emitted exactly that headline.
    assert "found 0" not in digest, f"the digest claims a clean count it did not earn: {digest!r}"
    assert "did not complete" in digest
    assert "not** a clean result" in digest


def test_partially_available_does_not_report_clean_either():
    """One ecosystem answered. That is not a clean audit of two."""
    digest = audit.render_digest([
        _result("clean", "npm", tool="npm audit"),
        _result("unavailable", "pypi", detail="pip-audit is not on PATH"),
    ])
    assert audit.CLEAN_LINE not in digest
    assert "found 0" not in digest, f"the digest claims a clean count it did not earn: {digest!r}"
    assert "1 of 2 ecosystem(s) were audited" in digest
    # ...and the one that did run is named, so a reader knows what was actually covered.
    assert "npm (`npm audit`): clean" in digest


def test_only_the_all_clean_case_claims_clean():
    assert audit.render_digest([
        _result("clean", "pypi"),
        _result("clean", "npm", tool="npm audit"),
    ]) == audit.CLEAN_LINE


def test_an_unavailable_tool_states_why():
    """A digest that says "could not run" without saying why sends the reader to the same dead end
    this file is trying to close."""
    digest = audit.render_digest([_result("unavailable", detail="pip-audit is not on PATH")])
    assert "pip-audit is not on PATH" in digest


# ── a real finding has to be actionable ─────────────────────────────────────────────────────────

def test_a_finding_is_named_with_its_advisory_and_fix():
    digest = audit.render_digest([_result("findings", findings=[_finding()])])
    assert "`mcp`" in digest
    assert "2.2.0" in digest
    assert "GHSA-xxxx-yyyy-zzzz" in digest
    assert "high" in digest
    assert "2.3.1" in digest


def test_findings_from_both_ecosystems_are_reported_not_collapsed():
    digest = audit.render_digest([
        _result("findings", "pypi", findings=[_finding()]),
        _result("findings", "npm", tool="npm audit",
                findings=[_finding(ecosystem="npm", package="wrangler", advisory="npm-1")]),
    ])
    assert "2 known-vulnerable package(s)" in digest
    assert "`mcp`" in digest
    assert "`wrangler`" in digest


def test_a_finding_with_no_fix_available_still_renders():
    """`fixed_in` empty is the case that most needs to survive rendering: a table cell that breaks is
    a finding nobody acts on."""
    digest = audit.render_digest([_result("findings", findings=[_finding(fixed_in="")])])
    assert "`mcp`" in digest
    assert "—" in digest


# ── the parsers, against shapes real tools emit ─────────────────────────────────────────────────

def test_parses_pip_audit_json():
    """One JSON document per dependency, printed on its own line — this is the shape
    `pip-audit --format json` produces, and the reason the parser scans rather than `json.loads`."""
    payload = json.dumps({
        "name": "mcp", "version": "2.2.0",
        "vulns": [{"id": "GHSA-aaaa-bbbb-cccc", "fix_versions": ["2.3.1"], "severity": "high"}],
    })
    findings = audit.parse_pip_audit_json(payload + "\n")
    assert len(findings) == 1
    assert findings[0].package == "mcp"
    assert findings[0].version == "2.2.0"
    assert findings[0].advisory == "GHSA-aaaa-bbbb-cccc"
    assert findings[0].fixed_in == "2.3.1"


def test_parses_several_pip_audit_documents_and_ignores_noise():
    text = (
        "WARNING: pip-audit is currently in beta\n"
        + json.dumps({"name": "mcp", "version": "2.2.0",
                      "vulns": [{"id": "GHSA-1", "fix_versions": []}]}) + "\n"
        + "not json at all\n"
        + json.dumps({"name": "pyyaml", "version": "6.0.3",
                      "vulns": [{"id": "GHSA-2", "fix_versions": ["6.1"]}]}) + "\n"
    )
    findings = audit.parse_pip_audit_json(text)
    assert [f.package for f in findings] == ["mcp", "pyyaml"]


def test_a_dependency_with_no_vulns_contributes_nothing():
    assert audit.parse_pip_audit_json(
        json.dumps({"name": "clean", "version": "1.0", "vulns": []})
    ) == []


def test_parses_npm_audit_json():
    payload = json.dumps({"vulnerabilities": {
        "wrangler": {
            "severity": "critical",
            "via": [{"title": "Prototype pollution", "url": "https://npmjs.com/advisories/1"}],
            "fixAvailable": {"name": "wrangler", "version": "4.13.0"},
        },
    }})
    findings = audit.parse_npm_audit_json(payload)
    assert len(findings) == 1
    assert findings[0].package == "wrangler"
    assert findings[0].severity == "critical"
    assert findings[0].advisory == "Prototype pollution"


def test_npm_audit_json_that_is_not_json_yields_nothing_rather_than_raising():
    """`npm audit --json` prints a bare error object on some failures. That has to be a silent
    empty list so `audit_npm` can fall through to its "unavailable" branch instead of crashing."""
    assert audit.parse_npm_audit_json("npm error audit endpoint returned an error") == []


# ── the offline path the workflow and the tests both rely on ────────────────────────────────────

def test_offline_mode_reports_both_as_unavailable():
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "audit_dependencies.py"), "--digest", "--offline"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr
    assert audit.CLEAN_LINE not in proc.stdout
    assert "offline mode" in proc.stdout


def test_the_digest_is_what_the_workflow_greps_for():
    """`dependency-vuln-audit.yml` decides whether to post a digest by grepping for `CLEAN_LINE`.
    If the two ever drift, the workflow posts a digest on every clean week and nobody reads it."""
    workflow = (REPO / ".github" / "workflows" / "dependency-vuln-audit.yml").read_text()
    assert audit.CLEAN_LINE in workflow, (
        "the workflow does not grep for the sentence this module defines; the two have drifted"
    )
