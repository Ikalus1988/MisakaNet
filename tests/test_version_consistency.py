#!/usr/bin/env python3
"""M0 safety net (audit 2026-09-05, T0.1): version-string consistency.

MisakaNet deliberately runs TWO version lines (see the "对齐" flow in
docs/maintainer/handoff-2026-09-05.md):

* registry / release line — ``server.json`` ``version`` + ``glama.json``
  ``version`` (MCP-registry listing version, bumped in lockstep per release)
* PyPI package line       — ``pyproject.toml`` + the ``packages[]`` entry with
  ``registryType: "pypi"`` inside ``server.json`` (the version actually
  published to PyPI)

Historical failure mode: a partial bump ships mismatched metadata (registry
says one version while the PyPI package entry / docs advertise another).
These tests pin the invariants so a partial bump fails CI with the actual
values instead of silently drifting.

Note: `.release-please-manifest.json` (`.` key) records the last
release-please release; it must never be *older* than the declared PyPI
version on main. JOIN.md/API.md/docs/index.html/README.md advertise
informational versions which must never claim something NEWER than the
authoritative lines (catches forward-typos; making them exactly equal is the
Milestone-2 version-source-of-truth task, not this safety net).
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _read_text(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _read_json(rel: str) -> dict:
    return json.loads(_read_text(rel))


def _ver(raw: str) -> tuple[int, int, int]:
    m = SEMVER.match(raw.strip().lstrip("v"))
    if not m:
        raise AssertionError(f"not a valid X.Y.Z version string: {raw!r}")
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]


def _version_locations() -> dict[str, str]:
    """Human label -> raw version string for every authoritative location."""
    pyproject = _read_text("pyproject.toml")
    pyproject_version = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    assert pyproject_version, "pyproject.toml has no [project] version"

    server = _read_json("server.json")
    pypi_entry = next(
        (p for p in server.get("packages", []) if p.get("registryType") == "pypi"),
        None,
    )
    assert pypi_entry, "server.json has no pypi packages[] entry"

    api_md = _read_text("API.md")
    api_version = re.search(r"\*\*Version:\*\*\s*([0-9.]+)", api_md)
    assert api_version, "API.md header has no Version: field"

    join_md = _read_text("JOIN.md")
    join_version = re.search(r"MisakaNet v?([0-9.]+)", join_md)
    assert join_version, "JOIN.md has no 'MisakaNet vX.Y.Z' line"

    index_html = _read_text("docs/index.html")
    html_versions = re.findall(r">v?(\d+\.\d+\.\d+)<", index_html)
    assert html_versions, "docs/index.html has no version badge"

    readme = _read_text("README.md")
    readme_versions = re.findall(r"misakanet(?:@| == )([0-9.]+)", readme)

    return {
        "pyproject.toml": pyproject_version.group(1),
        "server.json version (registry line)": str(server["version"]),
        "server.json pypi package version": str(pypi_entry["version"]),
        "glama.json version": str(_read_json("glama.json")["version"]),
        "package.json version": str(_read_json("package.json")["version"]),
        ".release-please-manifest.json (\".\")": str(
            _read_json(".release-please-manifest.json")["."]
        ),
        "API.md header": api_version.group(1),
        "JOIN.md version info": join_version.group(1),
        "docs/index.html badge(s)": ", ".join(sorted(set(html_versions))),
        "README.md misakanet@/== claims": ", ".join(sorted(set(readme_versions))),
    }


LOCATIONS = _version_locations()
REGISTRY_LINE = "server.json version (registry line)"
PYPI_LINE = "pyproject.toml"


def _test_fail(context: str, pairs: list[tuple[str, str]]) -> None:
    detail = "\n".join(f"  {label}: {value}" for label, value in pairs)
    raise AssertionError(f"{context}:\n{detail}")


def test_all_version_locations_are_valid_semver():
    """Every tracked version string must parse as X.Y.Z."""
    for label, raw in LOCATIONS.items():
        for part in raw.split(","):
            for single in part.strip().split():
                _ver(single)  # raises on garbage


def test_registry_line_lockstep():
    """server.json.version and glama.json.version must stay equal."""
    a = LOCATIONS[REGISTRY_LINE]
    b = LOCATIONS["glama.json version"]
    if a != b:
        _test_fail(
            "registry line drifted (server.json vs glama.json)",
            [(REGISTRY_LINE, a), ("glama.json version", b)],
        )


def test_pypi_line_lockstep():
    """pyproject.toml and the server.json pypi package entry must agree."""
    a = LOCATIONS[PYPI_LINE]
    b = LOCATIONS["server.json pypi package version"]
    if a != b:
        _test_fail(
            "PyPI line drifted (pyproject.toml vs server.json pypi entry)",
            [(PYPI_LINE, a), ("server.json pypi package version", b)],
        )


def test_manifest_not_older_than_pypi_line():
    """release-please manifest must never record a release older than the
    declared source version on main (catches uncoordinated manual bumps)."""
    manifest = LOCATIONS['.release-please-manifest.json (".")']
    pyproject = LOCATIONS[PYPI_LINE]
    if _ver(manifest) < _ver(pyproject):
        _test_fail(
            ".release-please-manifest.json is older than pyproject.toml",
            [('.release-please-manifest.json (".")', manifest), (PYPI_LINE, pyproject)],
        )


def test_npm_bundle_line_never_ahead_of_manifest():
    """package.json (npm bundle line) may lag the repo release line but must
    never claim a version newer than the release-please manifest (R2)."""
    package = LOCATIONS["package.json version"]
    manifest = LOCATIONS['.release-please-manifest.json (".")']
    if _ver(package) > _ver(manifest):
        _test_fail(
            "package.json npm-bundle line is ahead of the repo release line",
            [("package.json version", package), ('.release-please-manifest.json (".")', manifest)],
        )


def test_docs_never_claim_newer_than_authoritative_lines():
    """Informational doc claims must not exceed max(registry, manifest).

    Guards against forward-typos (e.g. a doc claiming v2.28.0 before it
    exists). Deliberately allows *older* claims — making docs exactly equal
    is the Milestone-2 unification task.
    """
    manifest = LOCATIONS['.release-please-manifest.json (".")']
    ceiling = max(_ver(LOCATIONS[REGISTRY_LINE]), _ver(manifest))
    ceiling_str = ".".join(str(p) for p in ceiling)
    for label in ("API.md header", "JOIN.md version info", "docs/index.html badge(s)",
                  "README.md misakanet@/== claims"):
        for raw in LOCATIONS[label].split(","):
            for single in raw.strip().split():
                if _ver(single) > ceiling:
                    _test_fail(
                        f"{label} claims a version newer than {ceiling_str}",
                        [(label, LOCATIONS[label]), ("current ceiling", ceiling_str)],
                    )
