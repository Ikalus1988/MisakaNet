#!/usr/bin/env python3
"""Version alignment for MisakaNet's multi-channel version lines (audit T2.1).

MisakaNet deliberately runs THREE version channels with independent cadence
(see docs/maintenance.md → 版本通道):

* registry line  — server.json/glama.json ``version`` (MCP-registry listing
  version; currently 2.29.x). Bumped together with the repo release tags, the
  docs that advertise them (API.md header, JOIN.md) and the agent-discovery
  cards under docs/.well-known/ (they declare the *server* version; their
  ``supportedInterfaces.protocolVersion`` is a different fact and is left alone).
* source line    — pyproject.toml + package.json + .release-please-manifest
  (the repo's own "next release" line, currently 2.23.x). package.json and
  the manifest must match; pyproject may lag it by design (bumped when the
  PyPI package is actually published).
* pypi channel   — the version actually on pypi.org (currently far behind,
  2.18.0): publishes have not run since; server.json's pypi packages[] entry
  tracks the source line (== pyproject) as the *next* pypi version.

Usage:
  python3 scripts/align_versions.py --check
      Print every declared version + pass/fail against the policy below.
      Exit 1 when a policy invariant breaks (CI / release gate).
  python3 scripts/align_versions.py --source 2.24.0
      Bump the repo release line: pyproject.toml, package.json,
      .release-please-manifest.json ("."), README npm claims.
  python3 scripts/align_versions.py --registry 2.28.0
      Bump the registry line: server.json + glama.json + API.md + JOIN.md
      + the docs/.well-known cards' server version.

Policy invariants (mirrored by tests/test_version_consistency.py):
  R1 registry pair equal:        server.json.version == glama.json.version
  R2 npm-bundle never ahead:     package.json <= manifest "."  (npm bundle
                                 line lags the repo release line)
  R3 pypi-source equal:          server.json pypi-package.version == pyproject
  R4 lag allowed:                pyproject <= manifest
  R5 docs never ahead:           API.md / JOIN.md / README claims
  R6 cards equal registry:       docs/.well-known/*.json server version
                                 <= max(registry, manifest)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


# Agent-discovery documents: what crawlers and MCP clients read before the site.
# Nothing wrote their top-level ``version``, so it sat at 2.16.0 while the
# registry listing reached 2.29.0 — the same "one fact, no writer" defect as the
# lesson counts (handoff-2026-09-12). They belong to the registry line.
WELL_KNOWN_CARDS = (
    "docs/.well-known/agent.json",
    "docs/.well-known/agent-card.json",
    "docs/.well-known/mcp.json",
)


def _read_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _write_json(rel: str, data: dict) -> None:
    (REPO / rel).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def _bump_card_version(rel: str, version: str) -> None:
    """Set a well-known card's top-level ``version`` without reformatting it.

    ``_write_json`` re-serialises the whole document, which turns a one-character
    version bump into a 46-line diff. Try a surgical edit first and accept it only
    if the result parses to exactly the intended document; otherwise fall back.
    """
    path = REPO / rel
    before = _read_json(rel)
    if "version" not in before:
        return
    expected = dict(before)
    expected["version"] = version
    text = path.read_text(encoding="utf-8")
    edited, hits = re.subn(r'(?m)^(\s*"version"\s*:\s*")[^"]*(")',
                           rf"\g<1>{version}\g<2>", text, count=1)
    if hits:
        try:
            if json.loads(edited) == expected:
                path.write_text(edited, encoding="utf-8")
                return
        except json.JSONDecodeError:
            pass
    _write_json(rel, expected)


def _ver(raw: str) -> tuple[int, int, int]:
    raw = raw.strip().lstrip("v")
    assert SEMVER.match(raw), f"not X.Y.Z: {raw!r}"
    return tuple(int(p) for p in raw.split("."))


def locations() -> dict[str, str]:
    server = _read_json("server.json")
    pypi = next(p for p in server["packages"] if p.get("registryType") == "pypi")
    api = (REPO / "API.md").read_text(encoding="utf-8")
    api_v = re.search(r"\*\*Version:\*\*\s*([0-9.]+)", api)
    join = (REPO / "JOIN.md").read_text(encoding="utf-8")
    join_v = re.search(r"MisakaNet v?([0-9.]+)", join)
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    readme_claims = sorted(set(re.findall(r"misakanet(?:@| == )([0-9.]+)", readme)))
    manifest = _read_json(".release-please-manifest.json")
    pyproject_v = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (REPO / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    ).group(1)
    return {
        "server.json (registry)": str(server["version"]),
        "glama.json (registry)": str(_read_json("glama.json")["version"]),
        "pyproject.toml": pyproject_v,
        "package.json": str(_read_json("package.json")["version"]),
        '.release-please-manifest.json (".")': str(manifest["."]),
        "server.json pypi-package": str(pypi["version"]),
        "API.md header": api_v.group(1) if api_v else "",
        "JOIN.md version": join_v.group(1) if join_v else "",
        "README misakanet@ claims": ", ".join(readme_claims),
        ".codex-plugin/plugin.json": str(_read_json(".codex-plugin/plugin.json").get("version", "")),
        "docs/.well-known cards": ", ".join(
            sorted({str(_read_json(rel).get("version", "")) for rel in WELL_KNOWN_CARDS})),
    }


def check() -> int:
    loc = locations()
    registry = loc["server.json (registry)"]
    source = loc["package.json"]
    manifest = loc['.release-please-manifest.json (".")']
    pyproject = loc["pyproject.toml"]
    pypi_entry = loc["server.json pypi-package"]
    manifest_v = _ver(manifest)
    ceiling = max(_ver(registry), manifest_v)

    print("— version lines —")
    for label, value in loc.items():
        print(f"  {label}: {value}")

    problems = []
    glama = loc["glama.json (registry)"]
    if registry != glama:
        problems.append(f"R1 registry pair drifted: server={registry} glama={glama}")
    plugin_version = loc[".codex-plugin/plugin.json"]
    if plugin_version and plugin_version != source:
        problems.append(
            f"R7 codex plugin manifest drifted: .codex-plugin/plugin.json={plugin_version} "
            f"package.json={source}")
    if _ver(source) > manifest_v:
        problems.append(
            f"R2 npm-bundle ahead of release line: package.json={source} > "
            f"manifest={manifest}"
        )
    if pyproject != pypi_entry:
        problems.append(f"R3 pypi-source drifted: pyproject={pyproject} pypi-entry={pypi_entry}")
    if _ver(pyproject) > manifest_v:
        problems.append(f"R4 pyproject ahead of manifest: {pyproject} > {manifest}")
    for label in ("API.md header", "JOIN.md version"):
        if loc[label] and _ver(loc[label]) > ceiling:
            problems.append(f"R5 {label} claims {loc[label]} newer than max({registry},{manifest})")
    for rel in WELL_KNOWN_CARDS:
        card = str(_read_json(rel).get("version", ""))
        if card != registry:
            problems.append(f"R6 {rel} declares server version {card or '(none)'} != registry {registry}")
    for claim in loc["README misakanet@ claims"].split(","):
        c = claim.strip()
        if c and _ver(c) > manifest_v:
            problems.append(f"R5 README claims {c} newer than release line {manifest}")

    for p in problems:
        print(f"  ❌ {p}")
    if problems:
        print(f"\n{len(problems)} problem(s): run --source / --registry to align")
    else:
        print("\nOK — all version invariants hold")
    return 0 if not problems else 1


def bump_source(version: str) -> None:
    assert SEMVER.match(version), version
    py = REPO / "pyproject.toml"
    text = re.sub(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{version}"',
                  py.read_text(encoding="utf-8"))
    py.write_text(text, encoding="utf-8")
    pkg = _read_json("package.json")
    pkg["version"] = version
    _write_json("package.json", pkg)
    # The Codex plugin manifest ships with the npm bundle, so it belongs to this
    # line; nothing wrote it before, which is how it reached 2.28.1 independently
    # (2026-09-12).
    _bump_card_version(".codex-plugin/plugin.json", version)
    man = _read_json(".release-please-manifest.json")
    man["."] = version
    _write_json(".release-please-manifest.json", man)
    for rel in ("README.md", "README.zh-CN.md"):
        p = REPO / rel
        if not p.exists():
            continue
        text = re.sub(
            r"(misakanet(?:@| == ))\d+\.\d+\.\d+",
            rf"\g<1>{version}",
            p.read_text(encoding="utf-8"),
        )
        p.write_text(text, encoding="utf-8")
    print(f"source line bumped to {version}: pyproject, package.json, manifest, README npm claims")


def bump_registry(version: str) -> None:
    assert SEMVER.match(version), version
    server = _read_json("server.json")
    server["version"] = version
    # The pypi packages[] entry advertises the repo's release line as the
    # installable pypi version; release-please moves pyproject/manifest to the
    # same number, so keep R3 (entry == pyproject) satisfied in one step.
    for pkg in server.get("packages", []):
        if pkg.get("registryType") == "pypi":
            pkg["version"] = version
    _write_json("server.json", server)
    glama = _read_json("glama.json")
    glama["version"] = version
    _write_json("glama.json", glama)
    api = REPO / "API.md"
    text = re.sub(r"(\*\*Version:\*\*\s*)[0-9.]+", rf"\g<1>{version}",
                  api.read_text(encoding="utf-8"))
    api.write_text(text, encoding="utf-8")
    join = REPO / "JOIN.md"
    text = re.sub(r"(MisakaNet v?)[0-9.]+", rf"\g<1>{version}",
                  join.read_text(encoding="utf-8"))
    join.write_text(text, encoding="utf-8")
    for rel in WELL_KNOWN_CARDS:
        _bump_card_version(rel, version)
    print(f"registry line bumped to {version}: server.json(+pypi entry), glama.json, API.md, JOIN.md, "
          f"{len(WELL_KNOWN_CARDS)} well-known cards")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        return check()
    if "--source" in args:
        v = args[args.index("--source") + 1]
        bump_source(v)
        return check()
    if "--registry" in args:
        v = args[args.index("--registry") + 1]
        bump_registry(v)
        return check()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
