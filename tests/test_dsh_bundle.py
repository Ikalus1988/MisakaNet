#!/usr/bin/env python3
"""Contract tests for the MisakaNet dsh bundle declaration (PR #1484 review).

Guards the packaging contract that the dsh.so / MCP-registry verification and
`dsh plugin` rely on:

* package.json declares ``dsh.bundle.patch`` pointing at ``cordis.patch.yml``
  and ships the patch in its npm ``files`` whitelist;
* the patch contains exactly one insert row (id ``misakanet-mcp``) whose
  config is a valid @deepseek-ai/dsh-mcp-client stdio declaration
  (serverName matching ^[A-Za-z0-9_-]{1,32}$, command python3, args pointing
  at the repo's scripts/mcp_server.py, failOnStartupError false);
* the row id is unique across the repo (no double-insert drift).
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
    assert row["name"] == "@deepseek-ai/dsh-mcp-client"
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


if __name__ == "__main__":
    sys.exit(0)
