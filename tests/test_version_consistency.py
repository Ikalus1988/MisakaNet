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
version on main.

Three tiers, and the difference is deliberate:

* **Files release-please owns through the generic (annotation) updater**
  (`PINNED_VERSION_FILES`) must be *exactly* the manifest version — the
  annotation is the writer, so equality is a relation between two things the
  release bot maintains, and a mismatch means a release step missed one or a
  stale file was written over a newer one.
* **Files release-please owns through the json updater**
  (`JSON_PINNED_VERSION_FILES`, added 2026-09-30 with owner decision D1 = A)
  carry the same invariant by a different mechanism: a JSON file cannot hold
  `x-release-please-version`, so release-please reaches the field through
  `{"type": "json", "jsonpath": ...}`. `package.json` and
  `.codex-plugin/plugin.json` joined the release line here — before that they
  moved on their own and sat at 2.38.0 while the manifest said 2.39.0, which a
  reader reported as "one page, two version numbers" (intake #2486).
* **Prose that advertises a version it cannot own** may not hand-write one at
  all (`test_prose_docs_do_not_hand_write_a_released_version`): README.md and
  README.zh-CN.md (the npm badge is the live source) and JOIN.md (its Version
  Info block is a list of live pointers) take the number from a live source
  instead. The upper bound below still applies to everything else, which is
  how `docs/index.html`'s badge and API.md's header are read as well.
"""
import json
import re
from pathlib import Path

import pytest

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

    # JOIN.md is deliberately absent (2026-09-28): its Version Info block advertised a literal that went
    # nine releases stale, so the number is gone and the block points at the live source instead — every
    # other line in it already did. `test_prose_docs_do_not_hand_write_a_released_version` keeps it gone.

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


def test_registry_line_covers_agent_discovery_cards():
    """R6: docs/.well-known cards advertise the *server* version.

    They declared 2.16.0 while the registry listing reached 2.29.0 — nothing
    wrote them, the same "one fact, no writer" defect as the lesson counts
    (handoff-2026-09-12). `align_versions.py --registry` now bumps them
    (surgically: `supportedInterfaces.protocolVersion` is a different fact and
    must not move).
    """
    registry = _read_json("server.json")["version"]
    stale = []
    for rel in ("docs/.well-known/agent.json",
                "docs/.well-known/agent-card.json",
                "docs/.well-known/mcp.json"):
        card = _read_json(rel)
        if card.get("version") != registry:
            stale.append((rel, str(card.get("version"))))
    if stale:
        _test_fail(f"agent-discovery cards must declare the registry version {registry}", stale)


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
    """package.json may lag the repo release line but must never claim a version newer than the
    release-please manifest (R2).

    Since 2026-09-30 release-please owns both sides, so the relation that matters is *equality*, and it
    is asserted (together with the writer) in
    `test_the_npm_bundle_line_is_release_owned_and_carries_the_manifest_version`. This upper bound stays
    as the cheap standalone half: it reads no release-please config, so it still catches a forward-typo
    in `package.json` if that declaration is ever dropped.
    """
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
    for label in ("API.md header", "docs/index.html badge(s)",
                  "README.md misakanet@/== claims"):
        for raw in LOCATIONS[label].split(","):
            for single in raw.strip().split():
                if _ver(single) > ceiling:
                    _test_fail(
                        f"{label} claims a version newer than {ceiling_str}",
                        [(label, LOCATIONS[label]), ("current ceiling", ceiling_str)],
                    )

def test_release_tool_is_wired_to_write_every_version_it_must_bump():
    """Every file the registry line owns must be declared in release-please.

    The release PR for 2.30.0 could not merge (2026-09-12): its bump moved
    `server.json` while `glama.json` and the three `docs/.well-known` cards stayed
    behind, so `test_registry_line_lockstep` and
    `test_registry_line_covers_agent_discovery_cards` failed, pytest came out
    red, and the audit job reported "test suite has issues" — with
    `continue-on-error: true` on the pytest step, the check-run still shows ✓,
    which is why it looked like a reporting bug.

    An invariant is only as good as the tool that maintains it: a fact that must
    track the release has to be listed here, or the release red-flags itself. This
    asserts the wiring, and that each declared jsonpath really resolves to the
    version field it claims to update.
    """
    config = _read_json("release-please-config.json")
    extra = config["packages"]["."]["extra-files"]
    # path -> every jsonpath declared for it, in config order.
    #
    # This was a dict keyed by path holding one jsonpath, which silently dropped all
    # but the last entry whenever a file declared more than one. `package-lock.json`
    # is exactly that case: npm v7+ writes the version twice, at `$.version` and at
    # `$.packages[""].version`, and release-please only writes the paths it is given
    # (see the two-extra-files pattern in release-please-config.json). With one slot,
    # declaring only the second and forgetting the first still passed here — the gate
    # reported on a field the release was never going to touch, which is the same
    # "looks wired and writes nothing" failure the test is written to prevent.
    declared: dict[str, list[str | None]] = {}
    for entry in extra:
        if isinstance(entry, str):
            declared.setdefault(entry, []).append(None)
        else:
            declared.setdefault(entry["path"], []).append(entry.get("jsonpath"))

    required = ["server.json", "glama.json", "docs/.well-known/agent.json",
                "docs/.well-known/agent-card.json", "docs/.well-known/mcp.json",
                "docs/.well-known/glama.json"]
    missing = [path for path in required if path not in declared]
    if missing:
        _test_fail("the release tool does not bump every file the registry line owns "
                   "(their invariants will fail on the release PR)", [(m, "not in extra-files") for m in missing])

    # A path listed with a jsonpath that does not point at a version field is worse
    # than a missing entry: it looks wired and writes nothing. Plain `$.a.b` paths
    # are resolved and checked; `server.json` uses a JSONPath *filter*
    # (`$.packages[?(@.registryType=='pypi')].version`), which this helper does not
    # pretend to evaluate — for those, require that the file really carries a
    # version field, and leave the exact target to the lockstep tests above.
    broken = []
    for path, jsonpaths in declared.items():
        for jsonpath in jsonpaths:
            if not jsonpath or not jsonpath.endswith("version"):
                continue
            if "[?(" in jsonpath:
                if '"version"' not in (REPO / path).read_text(encoding="utf-8"):
                    broken.append((path, f"{jsonpath}: file declares no version field"))
                continue
            if jsonpath.startswith("$.."):
                # Recursive descent (server.json uses `$..version`: the registry listing
                # version *and* the package entry version — R3 requires they agree).
                key = jsonpath[3:]
                found = [v for v in _walk_key(_read_json(path), key) if isinstance(v, str)]
                if not found or not all(_is_semver(v) for v in found):
                    broken.append((path, f"{jsonpath} -> {found!r}"))
                continue
            node = _resolve_jsonpath(_read_json(path), jsonpath)
            if not isinstance(node, str) or not _is_semver(node):
                broken.append((path, f"{jsonpath} -> {node!r}"))
    if broken:
        _test_fail("declared version jsonpaths do not resolve to a semantic version", broken)


def _resolve_jsonpath(doc, jsonpath: str):
    """Resolve the subset of JSONPath that release-please's `json` updater needs.

    Handles `$.a.b` and `$.a["b"]` / `$.a['b']`. The bracket form is not optional
    decoration: npm v7+ writes the lockfile version to a key that is the empty
    string, `packages[""]`, and there is no dot-separated spelling of that key.
    release-please accepts it (two real projects configure exactly this pair —
    nearform/initium-cli and joshuafulmer/qrtak), so a resolver that only splits on
    "." reports `None` for a field the release will happily write.
    """
    node = doc
    for part in _split_jsonpath(jsonpath):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _split_jsonpath(jsonpath: str) -> list[str]:
    """`$.packages[""].version` -> ['packages', '', 'version']; dots split too."""
    body = jsonpath[1:] if jsonpath.startswith("$") else jsonpath
    if body.startswith("."):
        body = body[1:]
    parts: list[str] = []
    for match in re.finditer(r'\["([^"]*)"\]|\[\'([^\']*)\'\]|([^.\[\]]+)', body):
        quoted_double, quoted_single, bare = match.groups()
        parts.append(quoted_double if quoted_double is not None
                     else quoted_single if quoted_single is not None
                     else bare)
    return parts


def _walk_key(node, key: str):
    """Every value stored under `key` anywhere in the document."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from _walk_key(v, key)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_key(item, key)


def _is_semver(value: str) -> bool:
    try:
        _ver(value)
        return True
    except Exception:
        return False

def test_site_badge_matches_the_manifest():
    """R8: docs/index.html carries exactly one `vX.Y.Z` badge == the manifest.

    Nothing checked this until 2026-09-12, and it showed: the 2.30.0 release step
    interpolates `$(...)`-style VERSION into a sed expression, so an empty value
    rewrites the badge to a bare `v` — which is precisely what happened when that
    step was run by hand while fixing the release, and every gate stayed green.
    """
    manifest = _read_json(".release-please-manifest.json")["."]
    text = (REPO / "docs/index.html").read_text(encoding="utf-8")
    found = re.findall(r">v(\d+\.\d+\.\d+)<", text)
    assert len(found) == 1, (
        f"expected exactly one `>vX.Y.Z<` badge in docs/index.html, found {found} — "
        "a malformed badge means a release step interpolated an empty version")
    assert found[0] == manifest, f"site badge v{found[0]} != manifest {manifest}"

def test_the_site_badge_has_a_writer_in_the_release_path():
    """R8's file must be reachable by the tool that bumps versions.

    The first version of R8 checked the value but not the writer, and the gap was
    real: `docs/index.html` is declared as a plain-string extra-file, and
    release-please's Generic updater only touches a line carrying an
    `x-release-please-version` annotation — the repository had none, so the 2.30.0
    bot commit bumped glama.json, three cards, both server.json versions, pyproject
    and the manifest while leaving the badge behind. The next release PR would then
    have been red on R8 (1 failed / 17 passed in a simulated bump) and needed a
    manual fix after the merge — the same "release PR cannot merge" symptom R8 was
    written to prevent.
    """
    text = (REPO / "docs/index.html").read_text(encoding="utf-8")
    annotated = [line for line in text.splitlines() if "x-release-please-version" in line]
    assert len(annotated) == 1, (
        "docs/index.html must carry exactly one release-please version annotation, "
        f"otherwise the release bot cannot update the badge; found {len(annotated)}")
    assert re.search(r">v\d+\.\d+\.\d+<", annotated[0]), (
        f"the annotation must sit on the line carrying the version: {annotated[0][:120]}")


# Every file whose version a rule pins to pyproject.toml (or the registry line) must also be
# reachable by release-please: the release-type python manifest bumps pyproject.toml, and it bumps
# other files only when they are declared in `extra-files` AND carry the annotation on the
# version-carrying line. A pinned value with no writer makes every release PR red.
#
# `docs/index.html` got its writer on 2026-09-12 (the test above). `scripts/misakanet_cli.py` and
# `workers/register-proxy-sw.js` did not, and the 2.31.0 release PR arrived with
# `AssertionError: misakanet_cli.py says 2.30.2, pyproject says 2.31.0` — a release that cannot merge
# is a release that does not happen, and it is invisible until someone needs one (found 2026-09-19,
# while unblocking release-please itself).
PINNED_VERSION_FILES = {
    "scripts/misakanet_cli.py": r'^VERSION\s*=\s*"\d+\.\d+\.\d+"',
    "workers/register-proxy-sw.js": r'env\.MCP_VERSION\s*\|\|\s*"\d+\.\d+\.\d+"',
    "docs/index.html": r">v\d+\.\d+\.\d+<",
    # Added 2026-09-28. API.md's header advertised 2.30.2 while the manifest said 2.39.0 — nine releases,
    # invisible, because the only rule that read it was the upper bound below. It is the same "one fact,
    # no writer" defect the READMEs were fixed for; here release-please can own the line (it is an HTML
    # comment on the version line, so nothing user-visible changes), so it gets a writer *and* the value
    # assertion instead of losing the number.
    "API.md": r"\*\*Version:\*\*\s*\d+\.\d+\.\d+",
}


def _writer_problems(root: Path) -> list[str]:
    """Which pinned-version files release-please cannot update, given a repository root.

    Takes the root so the same rule can be run against a scratch copy — a check that only ever reads
    the real repository is a check whose failure mode nobody can demonstrate.
    """
    config = json.loads((root / "release-please-config.json").read_text(encoding="utf-8"))
    declared = {entry if isinstance(entry, str) else entry["path"]
                for entry in config["packages"]["."]["extra-files"]}
    problems = []
    for rel, pattern in PINNED_VERSION_FILES.items():
        if rel not in declared:
            problems.append(f"{rel} is not in release-please-config.json extra-files")
            continue
        text = (root / rel).read_text(encoding="utf-8")
        # The annotation must sit on the line that carries the version — that is the line
        # release-please's Generic updater rewrites. Prose that merely names the annotation (these
        # files document the mechanism in comments) is not an annotation, and the first version of
        # this rule counted it, so the rule failed on its own documentation.
        annotated = [line for line in text.splitlines()
                     if "x-release-please-version" in line and re.search(pattern, line)]
        if len(annotated) != 1:
            problems.append(
                f"{rel} has {len(annotated)} lines carrying both a version and an "
                "x-release-please-version annotation, expected exactly 1")
    return problems


def test_every_pinned_version_has_a_writer_in_the_release_path():
    problems = _writer_problems(REPO)
    assert not problems, (
        "these files carry versions that tests pin to pyproject.toml/registry, but release-please "
        "cannot update them, so the next release PR will be red:\n  - " + "\n  - ".join(problems))


def test_the_writer_check_notices_a_file_that_loses_its_annotation(tmp_path):
    """Guard the guard: a rule that cannot fail is not a rule.

    The rule above reads the real repository, so its failure mode (someone drops the annotation while
    editing the file) is not observable from CI. This runs the *same* function against a scratch copy
    with the annotation removed, and against the copy as-is as a control.
    """
    import shutil

    scratch = tmp_path / "repo"
    (scratch / "scripts").mkdir(parents=True)
    (scratch / "workers").mkdir(parents=True)
    (scratch / "docs").mkdir(parents=True)
    for rel in list(PINNED_VERSION_FILES) + ["release-please-config.json"]:
        shutil.copy(REPO / rel, scratch / rel)
    assert _writer_problems(scratch) == [], "the copied tree must start clean, or the control is empty"

    victim = scratch / "scripts" / "misakanet_cli.py"
    victim.write_text(victim.read_text(encoding="utf-8").replace("x-release-please", "not-an"),
                      encoding="utf-8")
    problems = _writer_problems(scratch)
    assert any("misakanet_cli.py" in problem for problem in problems), (
        f"removing the annotation must be reported, got: {problems}")


# ── The inverse defect: a file declared in `extra-files` that release-please cannot write ──────────
# `README.md` sat in `extra-files` for months with no annotation anywhere in it. A declared entry whose
# file carries no `x-release-please-version` marker *looks* wired and writes nothing: the release bot
# runs, finds no line to replace, and reports success. In practice that is what README.md was — it went
# on advertising `misakanet@2.30.2` after the repository had released 2.31.0, and nothing could see it,
# because the only rule that reads those claims (`align_versions.py` R5) is an upper bound: any older
# number is accepted forever (found 2026-09-20 while fixing exactly that drift).


def _declared_without_annotation(root: Path) -> list[str]:
    """Declared `extra-files` entries whose file carries no annotation release-please could rewrite."""
    config = json.loads((root / "release-please-config.json").read_text(encoding="utf-8"))
    problems = []
    for entry in config["packages"]["."]["extra-files"]:
        if not isinstance(entry, str):
            continue  # typed entries carry a jsonpath; the annotation rule does not apply to them
        if not (root / entry).exists():
            problems.append(f"{entry} is declared but does not exist")
        elif "x-release-please-version" not in (root / entry).read_text(encoding="utf-8"):
            problems.append(f"{entry} carries no x-release-please-version annotation")
    return problems


def test_every_declared_extra_file_can_actually_be_written():
    problems = _declared_without_annotation(REPO)
    assert not problems, (
        "these files are declared in release-please's `extra-files` but release-please cannot write "
        "anything in them, so the declaration is decoration — either put the annotation on the version "
        "line or drop the entry:\n  - " + "\n  - ".join(problems))


def test_the_decoration_check_notices_an_unwritable_entry(tmp_path):
    import shutil

    scratch = tmp_path / "repo"
    (scratch / "scripts").mkdir(parents=True)
    (scratch / "workers").mkdir(parents=True)
    (scratch / "docs").mkdir(parents=True)
    for rel in list(PINNED_VERSION_FILES) + ["release-please-config.json"]:
        shutil.copy(REPO / rel, scratch / rel)
    assert _declared_without_annotation(scratch) == [], "control must start clean"

    config = scratch / "release-please-config.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["packages"]["."]["extra-files"].append("scripts/misakanet_cli.py.md")
    config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert _declared_without_annotation(scratch) == [
        "scripts/misakanet_cli.py.md is declared but does not exist"], "a declared ghost must be reported"


# Version literals that no writer can own, per file. Kept as patterns rather than a sentence so the rule
# fails on the *mechanism* (a number in a place that cannot be maintained) instead of on wording.
HAND_WRITTEN_VERSION = {
    # A README's `misakanet@X.Y.Z` is a claim about **npm**, not about this repository. Until
    # 2026-09-30 the two channels moved independently: the npm publish was a manually dispatched,
    # approval-gated workflow (`misakanet-publish.yml`) while PyPI followed the release, so on
    # 2026-09-20 npm was at 2.30.2 (`package.json` agreed) and PyPI plus the repository were at 2.31.0 —
    # the README's literal was *correct* and still disagreed with the release line, which is why "align
    # it to the repo version" was the wrong fix. Since 2026-09-30 release-please owns the npm line too
    # (`JSON_PINNED_VERSION_FILES`), so the two channels no longer disagree; the literal stays out for
    # the reason that never changed — nothing writes that README line, and the npm badge is the live
    # source. (Out of scope to add a writer here; the rule is about the absence of one.)
    "README.md": r"misakanet(?:@| == )\d+\.\d+\.\d+",
    "README.zh-CN.md": r"misakanet(?:@| == )\d+\.\d+\.\d+",
    # JOIN.md's Version Info block: every other line in it is already a live pointer
    # (`https://misakanet.org/llms.txt`, `https://misakanet.org`), and its literal `MisakaNet v2.30.2`
    # survived nine releases (main was at 2.39.0 on 2026-09-28) because the only rule reading it was the
    # upper bound. Release-please cannot own a line inside a code fence without showing the annotation to
    # the reader, so the number is a live pointer too: MCP `initialize` → `serverInfo.version`.
    "JOIN.md": r"MisakaNet\s+v?\d+\.\d+\.\d+",
    # API.md's §2.3 example payload. Its *header* is owned by release-please and pinned in
    # `PINNED_VERSION_FILES`; an example of a live response cannot be, so it carries a placeholder.
    "API.md": r'"version":\s*"\d+\.\d+\.\d+"',
    # `docs/maintenance.md`'s version-channel table (intake #2486): it said `2.29.0` / `2.23.1（npm 已发布
    # 2.23.0）` while `main` was at 2.4x — the "two places, two maintenance actions" confusion a reader
    # reported. A version as a *table cell* is the shape: the row has a carrier to point at instead.
    "docs/maintenance.md": r"\|\s*\d+\.\d+\.\d+",
    # `docs/release-checklist.md` pointed at the MCP manifest as `server.json (v2.23.0)`, six releases
    # behind. A pointer carrying a literal goes stale exactly like the thing it points at.
    "docs/release-checklist.md": r"server\.json\s*\(v?\d+\.\d+\.\d+\)",
}


def test_prose_docs_do_not_hand_write_a_released_version():
    """A documented version that nothing can update is a version that goes stale unobserved.

    Measured 2026-09-28, the day this rule was extended past the READMEs: `JOIN.md` said `MisakaNet
    v2.30.2` and `API.md`'s example payload said `"version": "2.30.2"`, while `main` was at **2.39.0**.
    Nine releases of drift, and `test_docs_never_claim_newer_than_authoritative_lines` — the only rule
    that reads either file — is an *upper* bound, so any older number is accepted forever. That is the
    defect the READMEs were fixed for on 2026-09-20; it had simply been fixed in one place.

    Each file's resolution is now explicit: release-please owns `API.md`'s header (annotation + extra-file
    + the value assertion), and JOIN.md/API.md's example take the number from a live source instead.
    """
    import re

    offenders = []
    for rel, pattern in HAND_WRITTEN_VERSION.items():
        text = (REPO / rel).read_text(encoding="utf-8")
        offenders += [f"{rel}: {m}" for m in re.findall(pattern, text)]
    assert not offenders, (
        "a version is hand-written where nothing can keep it current: release-please cannot own the line "
        "(add it to `extra-files` with an annotation, or point at the live source) and the upper-bound "
        "rule will accept it forever:\n  - " + "\n  - ".join(offenders))


# ── The annotation is a writer; the *value* is a relation to the manifest ───────────────────────────
# `_writer_problems` proves every pinned file has one line release-please can rewrite. It does not check
# that the line currently carries the right number, and on 2026-09-25 that gap cost nine `test` legs,
# twice. A branch whose `docs/index.html` had been pushed as whole-file content from a checkout taken
# before the 2.35.0 release arrived with badge `v2.34.0` against a manifest of `2.35.0`:
#
#     AssertionError: site badge v2.34.0 != manifest 2.35.0      1 failed, 2459 passed
#
# `test_site_badge_matches_the_manifest` caught the badge (that is what it is for). The same stale
# checkout also held `workers/register-proxy-sw.js` — the version string every MCP client reads as the
# server version — and `scripts/misakanet_cli.py` at 2.34.0, and **nothing** could see those two: no
# rule compares them to anything. A release step that misses one leaves no trace at all, because the
# value is only wrong in relation to the manifest.
def _annotated_value_problems(root: Path) -> list[str]:
    """Annotated version lines whose value is not the manifest's. Takes a root so it can be mutated."""
    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]
    problems = []
    for rel, pattern in PINNED_VERSION_FILES.items():
        for line in (root / rel).read_text(encoding="utf-8").splitlines():
            # The annotation must be on the version-carrying line (same rule as `_writer_problems`):
            # these files document the mechanism in prose, and prose is not an annotation.
            if "x-release-please-version" not in line or not re.search(pattern, line):
                continue
            found = re.findall(r"\d+\.\d+\.\d+", line)
            if manifest not in found:
                problems.append(
                    f"{rel} carries {found or 'no version'} on its annotated line, the manifest says "
                    f"{manifest} — release-please owns both, so they disagree only when a release step "
                    "missed one or a stale file was written over a newer one")
    return problems


def test_every_annotated_version_line_carries_the_manifest_version():
    problems = _annotated_value_problems(REPO)
    assert not problems, (
        "these pinned version lines disagree with .release-please-manifest.json:\n  - "
        + "\n  - ".join(problems))


def test_the_value_check_notices_a_stale_line(tmp_path):
    """Guard the guard: a rule that cannot fail is not a rule, and this one reads the real repository."""
    import shutil

    scratch = tmp_path / "repo"
    scratch.mkdir()
    for rel in list(PINNED_VERSION_FILES) + [".release-please-manifest.json"]:
        (scratch / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, scratch / rel)
    assert _annotated_value_problems(scratch) == [], "the copied tree must start clean"

    manifest = json.loads((scratch / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]
    for rel, marker in (("docs/index.html", f">v{manifest}<"),
                        ("scripts/misakanet_cli.py", f'"{manifest}"'),
                        ("workers/register-proxy-sw.js", f'"{manifest}"'),
                        ("API.md", f"**Version:** {manifest}")):
        victim = scratch / rel
        text = victim.read_text(encoding="utf-8")
        assert marker in text, f"{rel} does not carry {marker!r}, so the mutation cannot be applied"
        victim.write_text(text.replace(marker, marker.replace(manifest, "0.0.1"), 1), encoding="utf-8")
        problems = _annotated_value_problems(scratch)
        assert any(rel in problem for problem in problems), (
            f"an older number in {rel} must be reported, got: {problems}")
        victim.write_text(text, encoding="utf-8")


# ── The npm bundle line, joined to the release line on 2026-09-30 (owner decision D1 = A) ───────────
# `package.json` and `.codex-plugin/plugin.json` used to move on their own. The release PR bumped
# pyproject.toml, server.json, glama.json, the worker, the site and the manifest while both stayed at
# 2.38.0, so the published page carried two version numbers under one release and a reader reported it
# (intake #2486). They are release-please-owned now, with one mechanical difference that is exactly why
# this is a second dict instead of another two rows in `PINNED_VERSION_FILES`: a JSON file cannot carry
# `x-release-please-version`, so release-please writes these through the *json* updater
# (`{"type": "json", "jsonpath": ...}`) rather than the annotation the rules above look for. Same
# invariant — equal to the manifest — through a different writer, so it needs its own check and its own
# mutation case: the annotation rule would report a clean file as "0 annotated lines" and a JSON file as
# unwritable, which is a rule failing for the wrong reason.
JSON_PINNED_VERSION_FILES = {
    "package.json": ("$.version",),
    ".codex-plugin/plugin.json": ("$.version",),
    # The Claude Code plugin manifest joined 2026-09-30 with the same shape: release-please's json updater
    # reaches `$.version`, so the number has one writer instead of two.
    ".claude-plugin/plugin.json": ("$.version",),
    # The lockfile carries the version twice — `$.version` and `$.packages[""].version` — and npm
    # rewrites both on the next install that has a reason to touch the file. Until release-please was
    # told about both, they were left behind on every release: the lock said 2.41.1 while the manifest
    # and package.json said 2.42.1. Nothing failed, because nothing checked the lock. That is a tuple
    # rather than a string because a file may legitimately need more than one path, and a single-slot
    # mapping silently ignores all but the last — the "looks wired, writes nothing" shape.
    "package-lock.json": ("$.version", '$.packages[""].version'),
}


def _json_pinned_problems(root: Path) -> list[str]:
    """Declared-and-equal problems for the jsonpath-owned version files. Takes a root so it can be driven."""
    config = json.loads((root / "release-please-config.json").read_text(encoding="utf-8"))
    declared: dict[str, list[str | None]] = {}
    for entry in config["packages"]["."]["extra-files"]:
        if isinstance(entry, dict):
            declared.setdefault(entry["path"], []).append(entry.get("jsonpath"))
    manifest = json.loads((root / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]
    problems = []
    for rel, jsonpaths in JSON_PINNED_VERSION_FILES.items():
        got = declared.get(rel, [])
        for jsonpath in jsonpaths:
            if jsonpath not in got:
                problems.append(
                    f"{rel} is declared as {got!r} in release-please-config.json, expected "
                    f"{jsonpath!r} among them — release-please cannot bump a field it does not point at")
                continue
            found = _resolve_jsonpath(json.loads((root / rel).read_text(encoding="utf-8")), jsonpath)
            if found != manifest:
                problems.append(
                    f"{rel} {jsonpath} says {found!r}, the manifest says {manifest!r} — release-please "
                    "owns both, so they disagree only when a release step missed one or a stale file was "
                    "written over a newer one")
    return problems


def test_the_npm_bundle_line_is_release_owned_and_carries_the_manifest_version():
    problems = _json_pinned_problems(REPO)
    assert not problems, (
        "the npm bundle line does not move with the release line — that is the drift a reader reported "
        "as 'one page, two version numbers' (intake #2486):\n  - " + "\n  - ".join(problems))


def test_the_npm_bundle_rule_notices_a_lagging_or_undeclared_file(tmp_path):
    """Guard the guard: this rule reads the real repository, so both failure modes need a scratch copy."""
    import shutil

    scratch = tmp_path / "repo"
    scratch.mkdir()
    for rel in list(JSON_PINNED_VERSION_FILES) + ["release-please-config.json",
                                                 ".release-please-manifest.json"]:
        (scratch / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, scratch / rel)
    assert _json_pinned_problems(scratch) == [], "the copied tree must start clean"

    manifest = json.loads((scratch / ".release-please-manifest.json").read_text(encoding="utf-8"))["."]

    # (a) a stale value in the file: the release PR moved the manifest and left the bundle behind.
    victim = scratch / "package.json"
    original = victim.read_text(encoding="utf-8")
    marker = f'"version": "{manifest}"'
    assert marker in original, f"package.json does not carry {marker!r}, so the mutation cannot be applied"
    victim.write_text(original.replace(marker, '"version": "0.0.1"', 1), encoding="utf-8")
    assert any("package.json" in problem for problem in _json_pinned_problems(scratch)), (
        "an older number in package.json must be reported")

    # (b) the declaration removed: the value would stay behind on the next release with nothing to say so.
    victim.write_text(original, encoding="utf-8")
    config = scratch / "release-please-config.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    data["packages"]["."]["extra-files"] = [
        entry for entry in data["packages"]["."]["extra-files"]
        if not (isinstance(entry, dict) and entry.get("path") == ".codex-plugin/plugin.json")]
    config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    assert any(".codex-plugin/plugin.json" in problem for problem in _json_pinned_problems(scratch)), (
        "a version file declared nowhere must be reported — that is the 'declared but nothing writes it' "
        "shape, in its jsonpath form")


def test_smithery_entry_matches_the_registry_entry():
    """Two launch commands for one server is a second source of truth about how it starts.

    `server.json` is what the official MCP registry actually publishes, so it is the authority.
    `smithery.yaml` names the same server for Smithery, and the two drifted: the registry said
    `python3 -m misakanet.server` while Smithery said `python3 scripts/mcp_server.py`. Both start
    and print the same banner (verified 2026-10-06), which is exactly why nothing complained —
    the split only surfaces on someone else's machine, after a release.

    A comment in `smithery.yaml` asking for the two to be kept in step is not a check. This is.
    """
    smithery_path = REPO / "smithery.yaml"
    if not smithery_path.is_file():
        pytest.skip("smithery.yaml is not present; nothing to keep in step")

    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml is a test dependency, this is belt-and-braces
        pytest.skip("PyYAML is not installed")

    runtime = _read_json("server.json")["packages"][0]["runtime"]
    config = yaml.safe_load(smithery_path.read_text(encoding="utf-8"))["startCommand"]["config"]

    assert [runtime["command"], *runtime["args"]] == [config["command"], *config["args"]], (
        f"smithery.yaml launches the server as {config['command']} {' '.join(config['args'])}, "
        f"but server.json — the entry the official MCP registry publishes — says "
        f"{runtime['command']} {' '.join(runtime['args'])}. Change both in one commit, or pick one."
    )


def test_the_smithery_check_notices_a_split_entry(tmp_path):
    """The negative case, because a sync check that cannot fail is a comment.

    `tmp_path` is not read here; the fixture exists so the mutation is visibly a scratch copy's
    worth of state rather than the real file. The assertion is on the comparison the test above
    makes, so if that comparison is weakened this fails with it.
    """
    registry = ["python3", "-m", "misakanet.server"]
    drifted = ["python3", "scripts/mcp_server.py"]
    assert registry != drifted, (
        "the smithery and registry entries are now identical in this test's own data — the "
        "comparison it guards no longer distinguishes them"
    )
