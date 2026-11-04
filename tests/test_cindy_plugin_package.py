#!/usr/bin/env python3
"""The Cindy package is a shipped artifact; its manifest and the docs that cite it must agree.

`.cindy-plugin/` landed in #4397 and got its first follow-up ten minutes later (#4401: 1.1.0 →
1.2.0, `summary_plain` passed through). The integration page and the status matrix name the version
a reader is being asked to install — a version there that no longer matches `ghost.json` is the same
class of bug as a stale tool count: a number a reader trusts that nothing maintains.

Measured 2026-11-04: both docs still said 1.1.0 after the 1.2.0 bump, and no gate noticed. The
second test is the one that would have gone red.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / ".cindy-plugin"
MANIFEST = PLUGIN / "ghost.json"
#: Where each page states the plugin version, and the sentence that carries it. Scoped to the
#: sentence rather than the file: `status.md` legitimately names other clients' versions (v1.3.1,
#: 0.154.0), and a whole-file scan would call those drift.
DOC_VERSION_PATTERNS = {
    # The repo's version is the one this gate is about; the market copy can be one release behind
    # while its review is pending (2026-11-04: repo 1.2.3, submitted 1.2.2).
    "docs/integrations/cindy.md": r"仓库已到 \*\*(\d+\.\d+\.\d+)\*\*",
    "docs/integrations/status.md": r"plugin bundle `misakanet`\s+(\d+\.\d+\.\d+)",
}
#: The tools the plugin's own MANUAL and the integration page promise. A tool removed from the
#: manifest without the docs moving is the drift these two files exist to prevent.
EXPECTED_TOOLS = {
    "misakanet_search",
    "misakanet_get_lesson",
    "misakanet_preflight",
    "misakanet_submit_intake",
}


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def named_paths(entry: dict) -> dict[str, Path]:
    """Every file or directory the manifest names, under the labels a failure should print."""
    paths = {"entry": PLUGIN / entry["entry"], "icon": PLUGIN / entry["icon"]}
    paths.update({f"locale:{lang}": PLUGIN / rel for lang, rel in entry["locales"].items()})
    paths.update({
        f"manual:{item['name']}": PLUGIN / item["dir"] for item in entry["manual"]["items"]
    })
    return paths


def documented_versions(texts: dict[str, str]) -> dict[str, list[str]]:
    """The plugin version each page states, read from the sentence that states it.

    Missing is as wrong as different: a page that stops saying which version it is asking the
    reader to install has lost the claim, not just the number.
    """
    return {
        name: re.findall(DOC_VERSION_PATTERNS[name], text)
        for name, text in texts.items()
    }


def version_mismatches(texts: dict[str, str], version: str) -> list[str]:
    problems = []
    for name, found in documented_versions(texts).items():
        if not found:
            problems.append(f"{name}: no longer states the plugin version")
        for one in found:
            if one != version:
                problems.append(f"{name}: names {one}, the manifest is {version}")
    return problems


def test_the_manifest_is_a_package_this_repository_ships():
    entry = manifest()
    assert entry["schemaVersion"] == 3, "the Cindy manifest schema moved; update this gate with it"
    assert entry["id"] == "misakanet"
    assert re.fullmatch(r"\d+\.\d+\.\d+", entry["version"]), entry["version"]
    # The one external host the market review asked to be declared (and the user-facing boundary).
    assert entry["network"]["hosts"] == ["misakanet.org"], entry["network"]
    names = [tool["name"] for tool in entry["tools"]]
    assert len(names) == len(set(names)), f"duplicate tool names: {names}"
    assert EXPECTED_TOOLS <= set(names), f"missing tools: {sorted(EXPECTED_TOOLS - set(names))}"
    for tool in entry["tools"]:
        assert tool.get("description"), f"{tool['name']} has no description"
        assert tool.get("parameters", {}).get("type") == "object", tool["name"]


def test_every_file_the_manifest_names_exists():
    for label, path in named_paths(manifest()).items():
        assert path.exists(), f"{label} → {path} does not exist"
        if path.is_dir():
            assert any(path.iterdir()), f"{label} → {path} is empty"


def test_the_version_the_docs_name_is_the_manifest_version():
    version = manifest()["version"]
    texts = {name: (REPO / name).read_text(encoding="utf-8") for name in DOC_VERSION_PATTERNS}
    problems = version_mismatches(texts, version)
    assert not problems, (
        "the docs name a plugin version the manifest does not have (the 1.1.0 → 1.2.0 bump went "
        "through the package and not through its readers):\n  " + "\n  ".join(problems)
    )


def test_a_stale_version_in_a_doc_is_reported():
    """The gate can fail on the defect it forbids — measured live on 2026-11-04."""
    stale = {"docs/integrations/cindy.md": "仓库已到 **1.1.0**"}
    assert version_mismatches(stale, "1.2.0") == [
        "docs/integrations/cindy.md: names 1.1.0, the manifest is 1.2.0"
    ]
    same = {"docs/integrations/status.md": "plugin bundle `misakanet` 1.2.0, pending market review"}
    assert version_mismatches(same, "1.2.0") == []
    # A page that drops the sentence has lost the claim, not just the number.
    assert version_mismatches({"docs/integrations/cindy.md": "插件在审核中"}, "1.2.0") == [
        "docs/integrations/cindy.md: no longer states the plugin version"
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is what parses the entry point")
def test_the_entry_point_parses():
    node = shutil.which("node")
    done = subprocess.run([node, "--check", str(PLUGIN / "main.js")],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
