#!/usr/bin/env python3
"""Contract tests for the MisakaNet dsh bundle declaration (PR #1484 review).

Guards the packaging contract that the dsh.so / MCP-registry verification and
`dsh plugin` rely on:

* package.json declares ``dsh.bundle.patch`` pointing at ``cordis.patch.yml``
  and ships the patch in its npm ``files`` whitelist;
* the patch contains exactly one insert row (id ``misakanet-mcp``) whose
  config is a valid stdio declaration (serverName matching
  ^[A-Za-z0-9_-]{1,32}$, command python3, args pointing at the repo's
  scripts/mcp_server.py, failOnStartupError false);
* the row id is unique across the repo (no double-insert drift);
* **the patch never names a protected ``@deepseek-ai/*`` component** — DSH STORE
  hard-blocks that as ``SUBMISSION_PATCH_PROTECTED`` and rates the listing
  ``route: blocked``. Our own test asserted the opposite until 2026-09-12, which
  is exactly how the violation survived (see below).
"""
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _pkg() -> dict:
    return json.loads((REPO / "package.json").read_text(encoding="utf-8"))


def test_bundle_patch_declared_and_shipped():
    pkg = _pkg()
    patch_rel = pkg["dsh"]["bundle"]["patch"]
    assert patch_rel == "./cordis.patch.yml", patch_rel
    assert (REPO / "cordis.patch.yml").exists()
    assert "cordis.patch.yml" in pkg.get("files", []), "patch must ship in npm files"


def test_patch_single_insert_row_with_mcp_client_stdio_config():
    patch = yaml.safe_load((REPO / "cordis.patch.yml").read_text(encoding="utf-8"))
    inserts = [row for op in patch for row in op.get("insert", [])]
    assert len(inserts) == 1, f"expected exactly one insert row, got {len(inserts)}"
    row = inserts[0]
    assert row["id"] == "misakanet-mcp"
    assert row["name"] == "misakanet", "the patch may only name our own component"
    cfg = row["config"]
    assert cfg["transport"] == "stdio"
    assert cfg["serverName"] == "misakanet"
    assert SERVER_NAME_RE.match(cfg["serverName"]), cfg["serverName"]
    assert cfg["command"] == "python3"
    assert cfg["args"] == ["scripts/mcp_server.py"]
    assert (REPO / "scripts" / "mcp_server.py").exists()
    assert cfg.get("failOnStartupError") is False


def test_row_id_unique_across_repo():
    id_hits = []
    for p in (REPO / "cordis.patch.yml").parent.rglob("*.patch.yml"):
        try:
            doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for op in doc or []:
            for row in op.get("insert", []):
                if row.get("id") == "misakanet-mcp":
                    id_hits.append(str(p.relative_to(REPO)))
    assert id_hits == ["cordis.patch.yml"], id_hits


# The exact rules from AI-Scarlett/DSH-Store scripts/check-plugin-submission.mjs
# (function patchEntryIds). Reproduced here so we cannot re-break them silently:
# the listing went to `route: blocked` for two weeks because nothing in this repo
# knew about them — the previous version of this very test asserted the pattern
# that DSH STORE rejects.
PROTECTED_COMPONENT_NAME_RE = re.compile(r"\bname:\s*['\"]?@deepseek-ai/", re.IGNORECASE)
DISABLE_OFFICIAL_RE = re.compile(r"@deepseek-ai/")
DISABLED_TRUE_RE = re.compile(r"disabled:\s*true", re.IGNORECASE)


def test_patch_never_impersonates_the_protected_namespace():
    raw = (REPO / "cordis.patch.yml").read_text(encoding="utf-8")
    assert not PROTECTED_COMPONENT_NAME_RE.search(raw), (
        "DSH STORE rejects a bundle patch that names a @deepseek-ai/* component "
        "(SUBMISSION_PATCH_PROTECTED -> route: blocked). Mount the official "
        "component from index.js instead of naming it in the patch."
    )
    assert not (DISABLE_OFFICIAL_RE.search(raw) and DISABLED_TRUE_RE.search(raw)), (
        "DSH STORE rejects a bundle patch that appears to disable an official component"
    )


def test_entry_mounts_the_official_client_instead_of_naming_it():
    """The behaviour did not disappear — it moved into our own component.

    index.js resolves @deepseek-ai/dsh-mcp-client at runtime and mounts it, so the
    patch can stay free of protected names without losing the MCP row.
    """
    entry = (REPO / "index.js").read_text(encoding="utf-8")
    assert "await import('@deepseek-ai/dsh-mcp-client')" in entry, "index.js must mount the client"
    assert "ctx.plugin(" in entry, "index.js must mount it as a child plugin"
    assert "failOnStartupError" in entry, "degradation must stay configurable"
    pkg = _pkg()
    assert pkg.get("peerDependencies", {}).get("@deepseek-ai/dsh-mcp-client"), (
        "the client must be an optional peer dependency, never a bundled copy "
        "(DSH STORE: do not duplicate-install official components)"
    )
    assert pkg["peerDependenciesMeta"]["@deepseek-ai/dsh-mcp-client"].get("optional") is True


if __name__ == "__main__":
    sys.exit(0)