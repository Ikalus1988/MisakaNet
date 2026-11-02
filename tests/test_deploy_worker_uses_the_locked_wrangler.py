#!/usr/bin/env python3
"""The Wrangler that deploys has to be the Wrangler the repository declares.

Why (issue #2891)
-----------------
`deploy-worker.yml` ran `cd workers && npx wrangler deploy` with **no install step**. When nothing
is installed locally, `npx` resolves `latest` from the registry — so `package.json`'s declared range
and every dependabot PR that bumped it governed nothing about production, while looking like they
did: the bump was green, reviewed and merged, and the next deploy still used whatever the registry
served that morning.

The fix is two steps and one flag, and this test is here because a workflow is not covered by
anything else in the repository: `npm ci` installs `package-lock.json`'s version, and `--no-install`
turns a missing install into a failure instead of a silent fetch.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "deploy-worker.yml"


def test_the_deploy_installs_from_the_lockfile() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "npm ci" in text, (
        "deploy-worker.yml no longer runs `npm ci`; without it `npx wrangler` resolves the registry's "
        "latest and the declared version governs nothing (#2891)")
    assert "setup-node" in text, "`npm ci` needs a Node toolchain on the runner"


def test_the_deploy_cannot_fall_back_to_the_registry() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    deploy_lines = [line for line in text.splitlines()
                    if "wrangler deploy" in line and "npx" in line and not line.lstrip().startswith("#")]
    assert deploy_lines, "the deploy command moved — update this test rather than deleting it"
    for line in deploy_lines:
        assert "--no-install" in line, (
            f"`{line.strip()}` can fetch an unlisted Wrangler from the registry when the install step "
            "is skipped or broken; `npx --no-install` is what makes the lockfile authoritative")


def test_the_lockfile_still_pins_a_wrangler() -> None:
    lock = json.loads((REPO / "package-lock.json").read_text(encoding="utf-8"))
    entry = lock["packages"].get("node_modules/wrangler") or {}
    version = str(entry.get("version") or "")
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"package-lock.json pins wrangler as {version!r}; the deploy installs from this file, so it "
        "has to name an exact version")


def test_the_other_bare_uses_are_recorded_not_forgotten() -> None:
    """Three workflows still call `npx wrangler` with no install (#2891 lists them).

    They are pinned here as a *count* rather than fixed, so the number cannot grow without someone
    noticing that this class of defect is spreading — and so the next person sees that the omission
    is known rather than missed.
    """
    known = {"cf-diagnostics.yml", "d1-bootstrap.yml", "publish-dataset.yml"}
    found = set()
    for path in (REPO / ".github" / "workflows").glob("*.yml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"\bnpx\s+wrangler\b", line) and "--no-install" not in line and "#" not in line.split("npx")[0]:
                found.add(path.name)
    assert found <= known, (
        f"these workflows grew a bare `npx wrangler` call: {sorted(found - known)} — either install "
        "from the lockfile and pass --no-install, or add the file here with a reason")
