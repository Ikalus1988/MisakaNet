#!/usr/bin/env python3
"""Audit the dependency set on a schedule, not only when a dependency file changes (#2684).

The pull-request gate in `pr-checks.yml` runs `pip-audit` and `npm audit` **only when the pull
request touches `requirements.txt`, `pyproject.toml` or `package.json`**. That answers *"did this
pull request introduce a bad dependency?"*. It does not answer *"has a dependency that was already
in the tree become bad?"* — and that is the question that arrives on its own schedule, when a CVE
is published against a version the repository is already using. Nothing in a pull request changes at
that moment, so nothing goes red.

This script is the second half: it runs unconditionally, and reports a digest. It follows
`audit_intake_kinds.py`'s shape, including the string the workflow greps for, so the two scheduled
audits behave identically from the workflow's point of view.

**What is actually being audited, stated honestly.** `requirements.txt` uses lower bounds
(`mcp>=2.2.0`, `jsonschema>=4.26.0`, `pyyaml>=6.0`, `misakanet-core>=2.7.0`) and the repository has
no Python lockfile. So `pip-audit --requirement requirements.txt` resolves the constraint to the
newest version PyPI currently offers and audits **that**, not the version any particular CI run
happened to install. Two consequences worth knowing before trusting a clean report:

* This is not a scan of a pinned set, and cannot be while there is no lockfile. A green digest
  means "nothing in the currently resolvable set is known-vulnerable", not "the exact artifacts we
  deployed are known-clean".
* Because resolution always picks the newest satisfying version, a repository constrained with `>=`
  cannot *choose* to stay on a vulnerable release. That is a genuine strength of the current
  constraints and it is why this audit is a tripwire for newly-published advisories rather than a
  check for a bad pin that was merged by hand.

`package-lock.json` does pin the JavaScript side, so `npm audit` there is an exact scan.

The digest is advisory. It never edits a manifest, never opens a pull request, and never fails the
build on a finding — see `dependency-vuln-audit.yml` for why a scheduled job that can only turn a
tab red is worth nothing.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The workflow greps for this exact sentence to decide whether to post a digest at all. Changing it
# means changing the workflow's grep, which is why it lives here rather than in the workflow.
CLEAN_LINE = "No known-vulnerable dependencies found. ✅"

# `pip-audit` exit codes: 0 clean, 1 vulnerabilities found. Anything else means it could not run,
# which is a different answer from "clean" and must never be reported as clean.
AUDIT_CLEAN = 0
AUDIT_FINDINGS = 1


@dataclass
class Finding:
    ecosystem: str
    package: str
    version: str
    advisory: str
    severity: str = "unknown"
    fixed_in: str = ""


@dataclass
class AuditResult:
    ecosystem: str
    tool: str
    status: str                      # "clean" | "findings" | "unavailable"
    detail: str = ""                 # why it is unavailable, when that is the case
    findings: list[Finding] = field(default_factory=list)
    raw: str = ""


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=REPO)


# ── pip-audit ──────────────────────────────────────────────────────────────────────────────────

# `pip-audit -f json` emits one object per dependency. `name`/`version` are the *resolved* versions,
# not the constraint in requirements.txt, which is the whole caveat in the module docstring.
_PIP_JSON_LINE = re.compile(r"^\s*\{.*\}\s*$")


def parse_pip_audit_json(stdout: str) -> list[Finding]:
    findings: list[Finding] = []
    decoder = json.JSONDecoder()
    index = 0
    text = stdout
    while index < len(text):
        if text[index] != "{":
            index += 1
            continue
        try:
            obj, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            index += 1
            continue
        index = end
        if not isinstance(obj, dict):
            continue
        name = obj.get("name") or obj.get("package")
        version = obj.get("version") or ""
        if not name:
            continue
        vulns = obj.get("vulns") or []
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            fix_versions = [f for f in (vuln.get("fix_versions") or []) if f]
            findings.append(Finding(
                ecosystem="pypi",
                package=str(name),
                version=str(version),
                advisory=str(vuln.get("id") or "unknown"),
                severity=str(vuln.get("severity") or "unknown"),
                fixed_in=", ".join(str(v) for v in fix_versions),
            ))
    return findings


def audit_pip(timeout: int = 300) -> AuditResult:
    if shutil.which("pip-audit") is None:
        return AuditResult("pypi", "pip-audit", "unavailable",
                           "pip-audit is not on PATH in this runner")
    proc = _run(["pip-audit", "--requirement", "requirements.txt", "--format", "json"], timeout)
    if proc.returncode == AUDIT_CLEAN:
        return AuditResult("pypi", "pip-audit", "clean", raw=proc.stdout)
    if proc.returncode == AUDIT_FINDINGS:
        return AuditResult("pypi", "pip-audit", "findings",
                           findings=parse_pip_audit_json(proc.stdout), raw=proc.stdout)
    return AuditResult("pypi", "pip-audit", "unavailable",
                       f"pip-audit exited {proc.returncode}: {(proc.stderr or '').strip()[:200]}",
                       raw=proc.stdout)


# ── npm audit ───────────────────────────────────────────────────────────────────────────────────

def parse_npm_audit_json(stdout: str) -> list[Finding]:
    try:
        data = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return []
    findings: list[Finding] = []
    vulns = data.get("vulnerabilities") or {}
    if isinstance(vulns, dict):
        for name, entry in vulns.items():
            if not isinstance(entry, dict):
                continue
            via = entry.get("via") or []
            advisory = "unknown"
            for item in via:
                if isinstance(item, dict):
                    advisory = str(item.get("title") or item.get("url") or advisory)
                    break
                if isinstance(item, str):
                    advisory = item
                    break
            findings.append(Finding(
                ecosystem="npm",
                package=str(name),
                version="",
                advisory=advisory,
                severity=str(entry.get("severity") or "unknown"),
                fixed_in=str(entry.get("fixAvailable") or ""),
            ))
    return findings


def audit_npm(timeout: int = 300) -> AuditResult:
    if shutil.which("npm") is None:
        return AuditResult("npm", "npm audit", "unavailable", "npm is not on PATH in this runner")
    if not (REPO / "package-lock.json").is_file():
        return AuditResult("npm", "npm audit", "unavailable", "no package-lock.json to audit")
    proc = _run(["npm", "audit", "--json"], timeout)
    # npm audit exits non-zero whenever it finds anything, so the exit code carries no signal here
    # and the JSON is the answer. A non-JSON body means it could not run.
    if not parse_npm_audit_json(proc.stdout) and proc.returncode != 0:
        body = (proc.stderr or proc.stdout or "").strip()
        if "0 vulnerabilities" not in body:
            return AuditResult("npm", "npm audit", "unavailable",
                               f"npm audit exited {proc.returncode}: {body[:200]}", raw=proc.stdout)
    findings = parse_npm_audit_json(proc.stdout)
    if findings:
        return AuditResult("npm", "npm audit", "findings", findings=findings, raw=proc.stdout)
    return AuditResult("npm", "npm audit", "clean", raw=proc.stdout)


# ── digest ──────────────────────────────────────────────────────────────────────────────────────

def render_digest(results: list[AuditResult]) -> str:
    unavailable = [r for r in results if r.status == "unavailable"]
    findings = [f for r in results if r.status == "findings" for f in r.findings]
    ran = [r for r in results if r.status == "clean"]

    if not findings and not unavailable:
        return CLEAN_LINE

    lines: list[str] = []

    if findings:
        lines += [f"Dependency audit found {len(findings)} known-vulnerable package(s).", ""]
        lines += ["| ecosystem | package | version | advisory | severity | fixed in |",
                  "|---|---|---|---|---|---|"]
        for f in sorted(findings, key=lambda x: (x.ecosystem, x.package, x.advisory)):
            lines.append(
                f"| {f.ecosystem} | `{f.package}` | {f.version or '—'} | {f.advisory} | "
                f"{f.severity} | {f.fixed_in or '—'} |"
            )
        lines.append("")
    elif unavailable:
        # Deliberately not "found 0". A tool that never ran has not found nothing — it has answered
        # nothing, and a digest that opens by saying "0" is read as a clean audit by anyone skimming
        # it, which is the entire failure mode this script exists to avoid. The first sentence says
        # what is actually true: the audit did not complete.
        lines += [
            f"**Dependency audit did not complete.** {len(ran)} of {len(results)} ecosystem(s) "
            f"were audited and reported clean; {len(unavailable)} could not run. This is **not** a "
            "clean result.",
            "",
        ]
        for r in ran:
            lines.append(f"- {r.ecosystem} (`{r.tool}`): clean")
        lines.append("")

    if unavailable:
        lines += ["**Could not run — treat as unknown, not as clean:**", ""]
        for r in unavailable:
            lines.append(f"- {r.ecosystem} (`{r.tool}`): {r.detail}")
        lines.append("")

    lines += [
        "---",
        "",
        "Advisory only. This audit does not edit a manifest and does not open a pull request.",
        "",
        "`requirements.txt` uses lower bounds and this repository has no Python lockfile, so "
        "`pip-audit` audits the version the constraint resolves to *now*, not a pinned set. "
        "`package-lock.json` does pin the JavaScript side. See the script's docstring.",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Scheduled dependency vulnerability audit")
    ap.add_argument("--digest", action="store_true", help="print the markdown digest to stdout")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON instead")
    ap.add_argument("--offline", action="store_true",
                    help="report every tool as unavailable; used by the tests")
    args = ap.parse_args()

    if args.offline:
        results = [
            AuditResult("pypi", "pip-audit", "unavailable", "offline mode"),
            AuditResult("npm", "npm audit", "unavailable", "offline mode"),
        ]
    else:
        results = [audit_pip(), audit_npm()]

    if args.json:
        print(json.dumps({
            "results": [
                {
                    "ecosystem": r.ecosystem, "tool": r.tool, "status": r.status,
                    "detail": r.detail,
                    "findings": [f.__dict__ for f in r.findings],
                }
                for r in results
            ],
        }, indent=2))
        return 0

    digest = render_digest(results)
    if args.digest:
        print(digest)
    else:
        for r in results:
            print(f"{r.ecosystem:6} {r.status:12} {r.tool}")
            for f in r.findings:
                print(f"       {f.package} {f.version} {f.advisory} ({f.severity})")
            if r.status == "unavailable":
                print(f"       {r.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
