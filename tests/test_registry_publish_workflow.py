#!/usr/bin/env python3
"""The MCP registry listing is published by CI, not by a maintainer's memory (#1820).

`registry.modelcontextprotocol.io` is the authoritative listing every other directory mirrors, and
its `isLatest` had drifted to 2.29.0 while the repository, PyPI and the GitHub release were all at
2.30.2 — because publishing was a manual step (`mcp-publisher login github` → `publish server.json`)
that nothing watched, and that a sandboxed agent environment cannot perform at all (measured
2026-09-19: `github.com` unreachable, `registry.modelcontextprotocol.io` reachable).

These assertions are about the shape that makes it self-maintaining: OIDC identity instead of a
stored secret, a dispatch from the release flow instead of a human, a version check before the
identity step, and a read-back that fails when the registry disagrees. Each one was a specific
failure mode of the manual path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
REGISTRY = WORKFLOWS / "publish-mcp-registry.yml"
RELEASE_PLEASE = WORKFLOWS / "release-please.yml"


def _steps(path: Path) -> list[dict]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps: list[dict] = []
    for job in workflow["jobs"].values():
        steps.extend(job.get("steps", []))
    return steps


def _step(path: Path, needle: str) -> dict:
    for step in _steps(path):
        if needle in (step.get("name") or ""):
            return step
    raise AssertionError(f"no step matching {needle!r} in {path.name}")


def test_the_registry_publish_uses_oidc_identity_not_a_stored_secret():
    workflow = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    # `on:` is read back as the boolean True by YAML 1.1.
    assert "workflow_dispatch" in (workflow.get("on") or workflow.get(True) or {}), (
        "dispatch-only on purpose: release-please tags with GITHUB_TOKEN, and a GITHUB_TOKEN push "
        "cannot trigger a `push: tags` workflow — that trigger would look right and never fire"
    )
    # Declared at workflow level here; read whichever scope carries it.
    job = workflow["jobs"]["publish"]
    perms = job.get("permissions") or workflow.get("permissions") or {}
    assert perms.get("id-token") == "write", "OIDC needs id-token: write"
    assert perms.get("contents") == "read", "publishing a listing needs no write access to the repo"
    login = _step(REGISTRY, "Authenticate")["run"]
    assert "login github-oidc" in login, (
        "the GitHub device flow cannot run in CI (and not in a sandbox at all); OIDC is the "
        "documented method for Actions"
    )
    assert "NODE_AUTH_TOKEN" not in REGISTRY.read_text(encoding="utf-8")


def test_the_publish_is_checked_before_and_read_back_after():
    steps = _steps(REGISTRY)
    names = [s.get("name") or "" for s in steps]
    validate = next(i for i, n in enumerate(names) if "Validate" in n)
    version = next(i for i, n in enumerate(names) if "version being published" in n)
    login = next(i for i, n in enumerate(names) if "Authenticate" in n)
    readback = next(i for i, n in enumerate(names) if "registry now says" in n)
    # The version guard must come before the identity step: publishing whatever happens to be on disk
    # under a number nobody checked is how a listing ends up describing an older release.
    assert version < login, "check server.json's version before authenticating"
    assert validate < login, "validate before authenticating"
    assert readback > login, "the publish must be read back from the registry, not assumed"
    assert "isLatest" in _step(REGISTRY, "registry now says")["run"], (
        "the read-back must assert isLatest — 'the version is listed' is not the claim #1820 makes"
    )


def test_the_release_flow_dispatches_it_and_only_when_it_tagged_a_release():
    dispatch = _step(RELEASE_PLEASE, "Dispatch the MCP registry publish")
    assert dispatch["if"] == "steps.release_tag.outputs.created == 'true'", (
        "an unconditional dispatch would republish the same version on every push to main"
    )
    assert "gh workflow run publish-mcp-registry.yml" in dispatch["run"]
    assert "version=${{ steps.release_tag.outputs.version }}" in dispatch["run"], (
        "the release flow knows the version it just tagged; pass it so the workflow can refuse a "
        "mismatch instead of publishing the file as-is"
    )
    # The PyPI dispatch is the precedent this follows — both tokens are the built-in one, which is
    # the only one carrying `actions: write` (see the comment there about the PAT's 403).
    assert dispatch["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
