#!/usr/bin/env python3
"""The parts of a DSH plugin a *host* reads before it ever runs our code.

Measured 2026-09-30 while comparing this repository with a plugin the host ecosystem had picked up
(`bowenliang123/dsh-context`, 1.6k stars, 32k npm downloads a week): a plugin there is not only a bundle
patch. The host plugin manager renders `package.json` `icon` (`PackageArtwork({src: pkg.meta?.icon})`),
the Add-plugin dialog tells users the name is "the part after `dsh plugin add` in a community plugin's
README install command", directory harvesters and npm search index the keywords, and a manifest may
declare which host releases it is tested against (`dsh.compatibility.dshReleases`).

None of that was in this package: `icon` was `null`, the keywords had no `dsh`/`deepseek-harness`/
`cordis`, there was no compatibility declaration, and the DSH story was split across three documents
(the README channel table, `docs/dsh-installation.md`, and `docs/integration/deepseek-harness.md`, which
described only the older local adapter).

What is pinned here, with the failure each rule prevents:

* **The icon contract the host enforces.** `dsh-app-boot`'s `iconOf()` *throws* on an absolute path, an
  extension outside SVG/PNG/JPEG/WebP, a file over 256 KiB, or a target outside the manifest directory —
  a bad icon is not a cosmetic problem, it is a plugin that does not load. The live declaration and the
  red cases are both driven through `icon_problems()`, so the rule is exercised, not just asserted.
* **The declared release list and the compatibility page are the same list**, in both directions:
  a version claimed in one and not the other is exactly the drift that makes a compatibility claim
  worthless.
* **A declared release is inside the declared optional-peer range.** Measured 2026-09-30: the host this
  package was installed on (`dsh 0.2.0-rc.2`) sat *outside* its own `>=0.1.0-rc.8 <0.2.0` peer range.
* **Discovery metadata is present**: npm keywords the ecosystem searches on, and the install command
  above the fold in the README — because the host's dialog sends users there to find it.
"""
from __future__ import annotations

import json
import ntpath
import os
import pytest
import posixpath
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# dsh-app-boot/lib/index.js (iconOf): these are the host's own rules, not ours.
ICON_MEDIA_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg", ".webp": "image/webp"}
MAX_ICON_BYTES = 256 * 1024

ECOSYSTEM_KEYWORDS = ("dsh", "dsh-plugin", "deepseek-harness", "cordis")

# The row shape the compatibility page uses for a host we declare and verified:
#     | `0.2.0-rc.2` | compatible | ✅ … |
VERIFIED_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*compatible\s*\|", re.M | re.I)

ABSOLUTE_OR_URI = re.compile(r"^[A-Za-z][A-Za-z\d+.-]*:")


def is_absolute(icon: str) -> bool:
    """The host's own test: `path.isAbsolute(value) || path.win32.isAbsolute(value)`.

    Both conventions, because a manifest can come from either platform. `os.path.isabs` is only one of
    them — on Windows it answers *False* for `/etc/passwd`, which is how the first version of this rule
    passed on Linux and turned `windows-latest` red. `ntpath.isabs` requires a drive, and
    `win32.isAbsolute` does not, so the rooted form is checked separately here.
    """
    return (posixpath.isabs(icon) or ntpath.isabs(icon) or icon[:1] in ("/", "\\")
            or bool(re.match(r"^[A-Za-z]:", icon)))


def _pkg(root: Path) -> dict:
    return json.loads((root / "package.json").read_text(encoding="utf-8"))


def icon_problems(root: Path) -> list[str]:
    """Every way `package.json: icon` would make the host refuse to load this plugin."""
    pkg = _pkg(root)
    icon = pkg.get("icon")
    if not isinstance(icon, str) or not icon:
        return ["package.json declares no `icon` — the host's plugin list renders an empty artwork slot"]
    problems: list[str] = []
    if is_absolute(icon) or ABSOLUTE_OR_URI.match(icon):
        return [f"icon {icon!r} must be a relative file path (the host throws on absolute paths and URIs)"]
    suffix = Path(icon).suffix.lower()
    if suffix not in ICON_MEDIA_TYPES:
        problems.append(f"icon {icon!r} must be SVG, PNG, JPEG, or WebP, not {suffix!r}")
    target = (root / icon).resolve()
    if not target.is_file():
        problems.append(f"icon {icon!r} does not exist")
        return problems
    if not target.is_relative_to(root.resolve()):
        problems.append(f"icon {icon!r} must remain inside the package directory")
    size = target.stat().st_size
    if size > MAX_ICON_BYTES:
        problems.append(f"icon is {size} bytes; the host refuses anything over {MAX_ICON_BYTES} (256 KiB)")
    if suffix == ".svg":
        try:
            if ET.fromstring(target.read_text(encoding="utf-8")).tag != "{http://www.w3.org/2000/svg}svg":
                problems.append("icon.svg does not have an <svg> root element")
        except ET.ParseError as exc:
            problems.append(f"icon.svg is not parseable XML: {exc}")
    if icon not in pkg.get("files", []):
        problems.append(f"icon {icon!r} is not in `files`, so it would not be published to npm")
    return problems


def test_the_plugin_icon_meets_the_host_contract():
    problems = icon_problems(REPO)
    assert not problems, "the DSH plugin icon would not load:\n  - " + "\n  - ".join(problems)


def test_the_icon_rule_can_go_red(tmp_path):
    """Guard: the rule reads the repository, so its red cases need fixtures."""
    (tmp_path / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")

    def write(icon: str, files: list[str]) -> None:
        (tmp_path / "package.json").write_text(
            json.dumps({"icon": icon, "files": files}), encoding="utf-8")

    # Every spelling the host's `isAbsolute || win32.isAbsolute` rejects. `"/etc/passwd"` is the one that
    # got away: `ntpath.isabs` says it is relative, `win32.isAbsolute` says it is absolute, and the host
    # asks both — so this fixture is what keeps the rule cross-platform.
    for absolute in (str(tmp_path / "icon.svg"), "/etc/passwd", "\\windows\\icon.svg", "C:/tmp/icon.svg"):
        write(absolute, [])
        assert any("relative file path" in p for p in icon_problems(tmp_path)), \
            (absolute, icon_problems(tmp_path))

    write("icon.gif", ["icon.gif"])
    (tmp_path / "icon.gif").write_bytes(b"GIF89a")
    assert any("SVG, PNG, JPEG, or WebP" in p for p in icon_problems(tmp_path))

    write("missing.png", ["missing.png"])
    assert any("does not exist" in p for p in icon_problems(tmp_path))

    (tmp_path / "big.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">' + "x" * MAX_ICON_BYTES + "</svg>", encoding="utf-8")
    write("big.svg", ["big.svg"])
    assert any("256 KiB" in p for p in icon_problems(tmp_path)), icon_problems(tmp_path)

    write("icon.svg", [])
    assert any("not in `files`" in p for p in icon_problems(tmp_path)), icon_problems(tmp_path)

    # …and the good shape is quiet, or the rule above proves nothing.
    write("icon.svg", ["icon.svg"])
    assert icon_problems(tmp_path) == []


def test_the_icon_is_the_same_mark_as_the_site_fallback():
    """Two copies of one mark drift silently; this is the cheap rope between them."""
    icon = (REPO / _pkg(REPO)["icon"]).read_text(encoding="utf-8")
    fallback = (REPO / "docs" / "assets" / "misaka-avatar-fallback.svg").read_text(encoding="utf-8")
    mark = re.search(r'<path d="([^"]+)" fill="#67e8f9"', fallback)
    assert mark, "the site fallback no longer carries the M mark this test compares against"
    assert mark.group(1) in icon, (
        "icon.svg and docs/assets/misaka-avatar-fallback.svg have drifted apart — they must draw the "
        "same mark, or the plugin list and the site will show two different brands")


def _semver(text: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    core, _, pre = text.partition("-")
    numbers = tuple(int(part) for part in core.split("."))
    return numbers + (0, 0, 0)[: max(0, 3 - len(numbers))], tuple(pre.split(".")) if pre else ()


def _precedence(left: str, right: str) -> int:
    (ln, lp), (rn, rp) = _semver(left), _semver(right)
    if ln != rn:
        return (ln > rn) - (ln < rn)
    if lp == rp:
        return 0
    if not lp:            # a release outranks its own pre-releases: 0.2.0 > 0.2.0-rc.2
        return 1
    if not rp:
        return -1
    return (lp > rp) - (lp < rp)


_COMPARATOR = re.compile(r"^(>=|<=|>|<|=)?\s*(\S+)$")
_OPERATORS = {"=": lambda c: c == 0, ">": lambda c: c > 0, ">=": lambda c: c >= 0,
              "<": lambda c: c < 0, "<=": lambda c: c <= 0}


def satisfies(version: str, range_text: str) -> bool:
    """npm's semver rules, including the one that bit this package.

    A range is a union of comparator sets (`||`). Inside a set every comparator must hold — **and** a
    version carrying a pre-release only satisfies a set that names a pre-release comparator with the
    same major.minor.patch, which is why `<0.2.0` excludes `0.2.0-rc.2` and why widening the bound to
    `<0.3.0` still excludes it. The table in `test_the_prerelease_rule_matches_npm_semver` is the
    measured behaviour of npm's own `semver` (bundled with npm, SEMVER_SPEC_VERSION 2.0.0), so this
    implementation is pinned to it rather than trusted.
    """
    version_pre = _semver(version)[1]
    for clause in range_text.split("||"):
        comparators = []
        for token in clause.split():
            match = _COMPARATOR.match(token)
            if match is None:
                raise AssertionError(f"unparsable comparator {token!r} in {range_text!r}")
            comparators.append((match.group(1) or "=", match.group(2)))
        if not comparators or not all(_OPERATORS[op](_precedence(version, target))
                                      for op, target in comparators):
            continue
        if version_pre and not any(_semver(target)[1] and _semver(target)[0] == _semver(version)[0]
                                   for _, target in comparators):
            continue
        return True
    return False


def test_the_prerelease_rule_matches_npm_semver():
    """The measured table (npm's bundled semver, 2026-09-30). This is the rule, not a guess.

    `0.1.5-rc.1` is excluded by *every* spelling here: npm only admits a pre-release when the set names
    its exact major.minor.patch. Any host line we declare has to be named in the range.
    """
    versions = ["0.1.0-rc.8", "0.1.5-rc.1", "0.1.9", "0.2.0-rc.1", "0.2.0-rc.2", "0.2.0", "0.2.5",
                "0.3.0-rc.1", "0.3.0"]
    measured = {
        ">=0.1.0-rc.8 <0.2.0":
            [True, False, True, False, False, False, False, False, False],
        ">=0.1.0-rc.8 <0.3.0":
            [True, False, True, False, False, True, True, False, False],
        ">=0.1.0-rc.8 <0.2.0 || >=0.2.0-rc.1 <0.3.0":
            [True, False, True, True, True, True, True, False, False],
    }
    for range_text, expected in measured.items():
        actual = [satisfies(v, range_text) for v in versions]
        assert actual == expected, f"{range_text!r}: {dict(zip(versions, actual))}"


def test_every_declared_release_is_inside_the_optional_peer_range():
    """The contradiction this fixes: declare `0.2.0-rc.2` compatible while the range excludes it.

    Measured 2026-09-30: `dsh 0.2.0-rc.2` ships `@deepseek-ai/dsh-mcp-client@0.2.0-rc.2`, and
    `>=0.1.0-rc.8 <0.2.0` does not admit it — nor does `<0.3.0`, because npm only admits a pre-release
    into a set that names its own major.minor.patch. The declared line has to be named.
    """
    pkg = _pkg(REPO)
    declared = pkg["dsh"]["compatibility"]["dshReleases"]
    assert declared, "declare at least one host release, or the compatibility page has nothing to record"
    peer = pkg["peerDependencies"]["@deepseek-ai/dsh-mcp-client"]
    for release in declared:
        assert satisfies(release, peer), (
            f"{release} is declared compatible but does not satisfy the optional-peer range {peer!r} "
            f"under npm's rules (a pre-release must be named by its own major.minor.patch)")


def test_the_declared_releases_and_the_compatibility_page_are_the_same_list():
    pkg = _pkg(REPO)
    declared = set(pkg["dsh"]["compatibility"]["dshReleases"])
    page = (REPO / "docs" / "compatibility.md").read_text(encoding="utf-8")
    documented = set(VERIFIED_ROW.findall(page))
    assert documented == declared, (
        "package.json's dsh.compatibility.dshReleases and docs/compatibility.md disagree — "
        f"manifest {sorted(declared)}, page {sorted(documented)}. A compatibility claim is only worth "
        "having if the measurement behind it is in the same change")


def test_the_compatibility_page_says_what_it_did_not_verify():
    page = (REPO / "docs" / "compatibility.md").read_text(encoding="utf-8")
    assert "not" in page.lower() and "install-smoke" in page, (
        "the page must name the check it is *not* making and who does make it (the daily install-smoke "
        "probe), or the table reads as if everything was verified")


def test_the_npm_keywords_carry_the_host_ecosystem_terms():
    keywords = set(_pkg(REPO).get("keywords", []))
    missing = [word for word in ECOSYSTEM_KEYWORDS if word not in keywords]
    assert not missing, (
        f"npm search and the directory harvesters classify plugins by these terms; missing {missing}")


def test_the_readme_installs_the_dsh_plugin_above_the_fold():
    """The host's Add-plugin dialog sends users to the README install command.

    Verbatim from the host's plugin manager: "The plugin package name is the npm package name …: the
    part after `dsh plugin add` or `pnpm add` in a community plugin's README install command." An
    install line that only appears 160 lines down is a step the dialog's own instruction cannot complete.
    """
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    install_at = readme.find("dsh plugin --profile web add misakanet")
    assert install_at != -1, "the README no longer shows the DSH install command at all"
    howto_at = readme.find("## How to use it")
    assert howto_at != -1, "the README lost its `How to use it` section"
    assert install_at < howto_at, "the DSH install command must appear above `How to use it`"
    assert readme[:install_at].count("\n") < 120, (
        "the install command is below the fold; the host's dialog points users at this file to find it")


# ── the client half (lib/client.js) ──────────────────────────────────────────
#
# `dsh.client` + `exports["./client"]` turn one file into a browser bundle the host serves through the
# module loader. Three things break it silently and all three are static: a bundle that does not
# register its own factory (the loader contract is `window.__ModuleLoader__.load({id, factory})`), a
# bundle that requires a module the frozen platform table cannot answer (bundle purity), and packaging
# that drops the file from the published tarball (the host throws "exports[./client] must be …" or the
# route 404s). None of that needs a browser to check, so it is a gate rather than a manual step.

CLIENT_BUNDLE = "lib/client.js"
# The module table the shell seeds: React, Cordis, and the static UI libraries. We declare no
# `dsh.client.external`, so the bundle may only ask for what the seed already answers.
PLATFORM_MODULES = {"react", "react/jsx-runtime", "react-dom", "react-dom/client", "@deepseek-ai/cordis"}
REQUIRE_CALL = re.compile(r"""require\(\s*["']([^"']+)["']\s*\)""")
ROUTE_LITERAL = re.compile(r"""(/api/[a-z0-9/_-]+)""")


def client_source(root: Path = REPO) -> str:
    return (root / CLIENT_BUNDLE).read_text(encoding="utf-8")


def declared_client_export(root: Path = REPO) -> str | None:
    """`exports["./client"]` in either form the host accepts (a string, or an object with default)."""
    entry = (_pkg(root).get("exports") or {}).get("./client")
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("default")
    return None


def unbundled_requires(source: str, declared: set[str]) -> list[str]:
    """Specifiers the bundle asks for that the platform table and the declaration cannot answer.

    Bundler-relative specifiers count as failures regardless of the declaration: a hand-written
    single-file bundle has no sibling chunk to resolve them against, and the host serves one file.
    """
    problems = []
    for specifier in REQUIRE_CALL.findall(source):
        if specifier.startswith("."):
            problems.append(f"{specifier} (relative — no sibling chunk is served)")
        elif specifier not in PLATFORM_MODULES and specifier not in declared:
            problems.append(f"{specifier} (not in the platform seed and not declared)")
    return problems


def test_the_client_bundle_satisfies_the_module_loader_contract():
    pkg = _pkg(REPO)
    declared = declared_client_export()
    assert declared, (
        "package.json exports[\"./client\"] is what the host resolver reads; without it "
        "dsh-client-modules throws instead of serving a bundle")
    path = REPO / declared.lstrip("./")
    assert path.is_file(), f"exports[\"./client\"] points at {declared}, which is not in the package"
    assert CLIENT_BUNDLE in pkg.get("files", []), (
        f"{CLIENT_BUNDLE} must be in `files` or the published tarball drops the browser half")
    assert pkg["dsh"]["client"]["platform"] == "web", "the Web consumer selects platform 'web'"

    source = client_source()
    assert "window.__ModuleLoader__.load(" in source, (
        "the bundle must register its own factory: executing it registers, materializing runs the body")
    assert re.search(r"""id:\s*["']%s["']""" % re.escape(pkg["name"]), source), (
        f"the registered id must be the package name ({pkg['name']}) — that is the graph row's identity")
    assert re.search(r"factory:\s*\(", source), "the loader contract is load({id, factory})"
    assert "exports.apply" in source, "a client plugin activates through its `apply` export"
    assert "exports.inject" in source, "the slot service must be declared so the fiber waits for it"


def test_the_client_bundle_only_asks_for_modules_the_platform_supplies():
    declared = set((_pkg(REPO).get("dsh", {}).get("client", {}) or {}).get("external", []))
    problems = unbundled_requires(client_source(), declared)
    assert not problems, (
        "a request the module table cannot answer does not degrade — it fails the row: " + str(problems))


def test_the_bundle_purity_rule_can_go_red():
    """A gate nobody has seen fail is a gate nobody can trust."""
    assert unbundled_requires("var a = require('react');", set()) == []
    assert unbundled_requires("var a = require('./chunk.js');", set()) == [
        "./chunk.js (relative — no sibling chunk is served)"]
    assert unbundled_requires("var a = require('@deepseek-ai/dsh-client-ui-primitives');", set()) == [
        "@deepseek-ai/dsh-client-ui-primitives (not in the platform seed and not declared)"]
    assert unbundled_requires(
        "var a = require('@deepseek-ai/dsh-client-ui-primitives');",
        {"@deepseek-ai/dsh-client-ui-primitives"}) == []


def test_the_client_half_registers_the_wire_tool_name_the_host_builds():
    """The slot is keyed by the wire tool name, and a key that matches nothing renders nothing.

    `dsh-mcp-client` builds it as `mcp__${serverName}__${rawName}`, and our bundle row sets
    `serverName` in cordis.patch.yml — so a rename in either file silently erases the card.
    """
    patch = (REPO / "cordis.patch.yml").read_text(encoding="utf-8")
    server = re.search(r"^\s*serverName:\s*(\S+)\s*$", patch, re.M)
    assert server, "cordis.patch.yml no longer sets serverName; the wire names cannot be predicted"
    expected = f"mcp__{server.group(1)}__misakanet_search"
    assert expected in client_source(), (
        f"the card must register `key: '{expected}'` — the name the host derives from serverName "
        f"{server.group(1)!r}")


def test_the_client_card_calls_endpoints_the_worker_actually_serves():
    """Votes are posted to public JSON routes; a renamed route would look like a broken button."""
    worker = (REPO / "workers" / "register-proxy-sw.js").read_text(encoding="utf-8")
    called = sorted(set(ROUTE_LITERAL.findall(client_source())))
    assert called, "the client half posts verdicts somewhere; no /api/ route found in the bundle"
    missing = [route for route in called if f'"{route}"' not in worker]
    assert not missing, f"the bundle posts to routes the worker does not serve: {missing}"


def test_the_client_half_carries_no_credential():
    """Anonymous by design: the card may only use the public, unauthenticated read/write routes.

    Two different questions, so two different checks. The bundle could *embed* a credential — answered
    by the repository's own rule (`scan_file`; `check_published_secrets.py` walks prose, so it never
    sees this file) — and it could *send* one, which no pattern of secret shapes catches, so the header
    and field names are asserted directly.
    """
    from scripts.check_published_secrets import scan_file

    findings = scan_file(REPO / CLIENT_BUNDLE)
    assert not findings, f"the browser half embeds a credential-shaped string: {findings}"

    source = client_source()
    forbidden = {"Authorization": "an auth header", "Bearer ": "a bearer token",
                 "api_key": "an API key field", "client_secret": "a secret field"}
    found = [f"{needle!r} ({why})" for needle, why in forbidden.items() if needle in source]
    assert not found, f"the browser half must not send credentials: {found}"


# ── the client half's two surfaces, and the rules they encode ────────────────
#
# The browser half answers a question the CLI cannot: it puts a *human judgment* into the evidence
# system (`POST /api/helpful` is the only writer of what `misakanet_me_events` reports). Three properties
# make that judgment worth having, and each is a static property of this file:
#
#   1. it is asked where the outcome is visible, not where the search happened;
#   2. abstaining costs nothing — nothing auto-votes and nothing is pre-selected;
#   3. each action says what it sends, and the cheap action sends the least.
#
# A UI whose misplacement is invisible to review is how a poisoned evidence signal ships, so these are
# gates with red fixtures rather than review notes.

SEARCH_ROW = "function MisakanetSearchRow"
VERDICT_ACTION = "function MisakanetVerdictAction"
VERDICT_SLOT = "conversation.chat.assistant-actions"
# Which package declares and types each slot we register into; its row must arrive before ours.
SLOT_OWNERS = {
    "tool.call.toolview": "@deepseek-ai/dsh-client-ui-tool",
    "conversation.chat.assistant-actions": "@deepseek-ai/dsh-client-ui-chat",
    "conversation.view": "@deepseek-ai/dsh-client-ui-conversation",
    "sidebar.right.pane.tab": "@deepseek-ai/dsh-client-ui-sidebar-right",
    "sidebar.right.pane.tab.title": "@deepseek-ai/dsh-client-ui-sidebar-right",
}
CALL_TO_HELPFUL = re.compile(r"""/api/helpful["']\s*,\s*\{(.*?)\}""", re.S)
USE_EFFECT = re.compile(r"react\.useEffect\(\s*function\s*\(\)\s*\{(.*?)\}\s*,\s*\[", re.S)


def registered_slots(source: str) -> set[str]:
    """Slot names this bundle registers into (`name: "…"` inside a `slots.register` call)."""
    return {slot for slot in SLOT_OWNERS if f'name: "{slot}"' in source}


def surface_bodies(source: str) -> tuple[str, str]:
    """The two component bodies, split at the verdict so each can be checked on its own."""
    assert SEARCH_ROW in source and VERDICT_ACTION in source, (
        "the client half is expected to keep two surfaces: visibility on the tool call, judgment on the "
        "assistant message")
    cut = source.index(VERDICT_ACTION)
    return source[source.index(SEARCH_ROW):cut], source[cut:]


def auto_votes(source: str) -> list[str]:
    """A POST issued from an effect would be a vote nobody cast. Effects may only observe."""
    return [body.strip()[:60] for body in USE_EFFECT.findall(source) if "post(" in body or "send(" in body]


def test_the_visibility_surface_cannot_vote():
    """Rule 1: the search row shows what came back; the verdict is asked at the outcome.

    At search time the fix has not run, so "did it help?" is unanswerable. A button there would collect
    reflex clicks, and reflex clicks are indistinguishable from judgment once they are in the counter.
    """
    search, _ = surface_bodies(client_source())
    assert "post(" not in search, (
        "the search row must not post anything: judgment belongs on the finalized assistant message, "
        "where the outcome is visible")


def test_the_judgment_surface_is_the_assistant_action_row():
    """Rule 1, other half: the vote rides the host's own per-message action row, not a new panel."""
    source = client_source()
    _, verdict = surface_bodies(source)
    assert VERDICT_SLOT in source, (
        "the verdict registers into the host's finalized-assistant-message action list")
    assert "messageId" in verdict, (
        "the action row is a list slot keyed per message; the entry must read its own messageId")
    assert "return null" in verdict, (
        "an entry with nothing to judge must render nothing, leaving the host's standard action row "
        "unchanged")


def test_every_registered_slot_has_its_owning_package_declared_first():
    """A keyed/list slot belongs to a package; registering before it loads is a race, not a feature."""
    pkg = _pkg(REPO)
    declared = list((pkg.get("dsh", {}).get("client", {}) or {}).get("inject", []))
    source = client_source()
    slots = registered_slots(source)
    assert slots, "no known slot is registered any more; the owner map needs updating with the code"
    missing = [SLOT_OWNERS[slot] for slot in sorted(slots) if SLOT_OWNERS[slot] not in declared]
    assert not missing, (
        f"`dsh.client.inject` must order the factories that declare these slots first: missing {missing}")
    dead = [name for name in declared if name not in set(SLOT_OWNERS.values())]
    assert not dead, (
        f"`dsh.client.inject` names a package no registered slot comes from: {dead} — a declaration "
        "nobody needs is a dependency the plugin pays for at boot")


def test_the_vote_is_never_cast_for_the_person():
    """Rule 2: abstention is the default. Nothing posts from an effect, and nothing pre-selects."""
    source = client_source()
    offenders = auto_votes(source)
    assert not offenders, f"a verdict must never be posted without a click: {offenders}"
    assert "defaultChecked" not in source and "checked=" not in source, (
        "no control may start in a chosen state")


def test_the_cheap_vote_sends_the_least_it_can():
    """Rule 3: 👍 carries the lesson id alone; 👎 carries the search text, and the UI says so.

    The disclosure is not decoration. `/api/feedback` stores the query text and an IP for 90 days, so a
    click that sends it has to be a click the person understood.
    """
    source = client_source()
    matches = CALL_TO_HELPFUL.findall(source)
    assert matches, "the helpful vote must post to /api/helpful"
    assert len(matches) == 1, f"one call site expected for /api/helpful, found {len(matches)}"
    assert "query" not in matches[0], (
        f"👍 must send only lesson_id, but its body carries more: {matches[0].strip()!r}")
    assert "sends the lesson id" in source and "also sends the search text" in source, (
        "each action must state what it sends, in the UI, before the click")


def test_the_design_rules_can_go_red():
    """The three rules above, demonstrated on both sides of each line."""
    # a POST in an effect is an auto-vote
    assert auto_votes("react.useEffect(function () { post('/api/helpful', {}); }, [x]);") != []
    assert auto_votes("react.useEffect(function () { memory.shownFor = id; }, [x]);") == []
    # the visibility surface posting is the misplacement
    assert "post(" in "function MisakanetSearchRow() { post('/api/helpful', {}); } function MisakanetVerdictAction() {}"
    # 👍 carrying the query is the disclosure bug
    ok = """/api/helpful", { lesson_id: lesson }"""
    bad = """/api/helpful", { lesson_id: lesson, query: memory.query }"""
    assert "query" not in CALL_TO_HELPFUL.findall(ok)[0]
    assert "query" in CALL_TO_HELPFUL.findall(bad)[0]


# ── the payload a default call really returns ────────────────────────────────
#
# The browser half renders whatever the agent's tool call returned. A default `misakanet_search` uses
# `detail: "compact"`, and the worker's own tool description names that key set — `domain` arrives only
# at `summary`, `path` only at `full`. The first version of the search row printed `(domain E3)` and
# therefore printed `(E3)` for every real call; the preview did not catch it because the preview's
# fixture was hand-written with a `domain` in it.
#
# So the key set is parsed from the *worker* (SSOT) and the row may not reach past it.

COMPACT_KEYS = re.compile(r"compact:\s*\{([^}]*)\}")


def compact_payload_keys(worker_source: str) -> set[str]:
    match = COMPACT_KEYS.search(worker_source)
    assert match, "the search tool description no longer spells out the compact key set"
    return {name.strip() for name in match.group(1).split(",") if name.strip()}


def test_the_search_row_reads_only_fields_the_default_payload_carries():
    worker = (REPO / "workers" / "register-proxy-sw.js").read_text(encoding="utf-8")
    allowed = compact_payload_keys(worker)
    assert allowed == {"id", "title", "problem", "freshness", "evidence_level"}, (
        f"the compact key set changed in the worker: {sorted(allowed)} — the row and the docs follow it")
    search, _ = surface_bodies(client_source())
    read = set(re.findall(r"\btop\.([A-Za-z_][A-Za-z0-9_]*)", search))
    beyond = sorted(read - allowed)
    assert not beyond, (
        "the search row reads fields the default `detail: \"compact\"` payload does not carry, so they "
        f"render empty in production: {beyond} (compact carries {sorted(allowed)}; ask the worker's "
        "description, not the fixture, when in doubt)")


def test_the_payload_rule_can_go_red():
    source = "function MisakanetSearchRow() { return top.domain + top.title; } function MisakanetVerdictAction() {}"
    search, _ = surface_bodies(source)
    assert sorted(set(re.findall(r"\btop\.([A-Za-z_][A-Za-z0-9_]*)", search)) - {"id", "title", "problem", "freshness", "evidence_level"}) == ["domain"]
    assert compact_payload_keys('compact: {id, title, problem, freshness, evidence_level}') == {
        "id", "title", "problem", "freshness", "evidence_level"}


# ── the panel (the review surface) ───────────────────────────────────────────
#
# The panel is where the numbers live, so its failure modes are different from the transcript rows': a
# number that cannot be traced, a state that is mislabelled, or a sound nobody asked for. Each is a
# static property of the file, and each has a red fixture below.

PANEL = "function MisakanetPanel"
INTAKE_LABELS = re.compile(r"already_have:\s*\"([^\"]*)\"")
# call sites only: the definition is not a place sound starts
PLAY_CUE = re.compile(r"^(?!\s*function ).*playCue\(.*$", re.M)



def dict_value(key: str, lang: str = "en") -> str:
    """One entry of the client's own dictionary — the copy those gates used to read out of the render."""
    source = client_source()
    block = re.search(rf"\n\t\tvar {lang} = \{{(.*?)\n\t\t\}};", source, re.S)
    assert block, f"the {lang} dictionary is not a `var {lang} = {{…}}` block"
    found = re.search(rf'"{re.escape(key)}":\s*"((?:[^"\\]|\\.)*)"', block.group(1))
    assert found, f"{key} is not declared in {lang}"
    return json.loads('"' + found.group(1) + '"')


def panel_body(source: str) -> str:
    assert PANEL in source, "the client half is expected to keep the review panel"
    return source[source.index(PANEL):]


def test_the_panel_answers_the_questions_it_exists_for():
    """Problems, lessons, contributions, trust, activity, voice — each labelled, in both languages.

    The copy moved into the dictionaries when the surfaces were localized, so this pins the key the panel
    asks for **and** the English string behind it: a key that resolves to nothing would pass a keys-only
    check while telling the reader nothing.
    """
    panel = panel_body(client_source())
    source = client_source()
    for key, english in (("panel.asked", "What this session asked"),
                         ("panel.reports", "Reports you filed"),
                         ("panel.trust", "How much these lessons are trusted"),
                         ("panel.activity", "Your activity"),
                         ("panel.voice", "Voice")):
        assert f'T("{key}")' in panel, f"the panel lost its `{key}` section"
        assert f'"{key}": "{english}"' in source, f"`{key}` no longer reads as `{english}`"


def test_the_panel_never_mislabels_a_report_that_was_never_filed():
    """`already_have` is the worker's #1526 backstop: the corpus already covered it, nothing was filed.

    Reading it as "converted" would tell a reporter their work landed when they never filed anything —
    a lie the server's own wording does not support. Conversion is its own state, and it arrives as
    `converted` (the receipt the #2494 channel returns).
    """
    source = client_source()
    labels = INTAKE_LABELS.findall(source)
    assert labels, "the intake states must be rendered by name"
    assert not any("convert" in label.lower() or "became" in label.lower() for label in labels), (
        f"a report that was never filed must not be labelled as a conversion: {labels}")
    assert '"converted"' in source, "the real conversion state must still exist"
    assert "backstop" in source, (
        "the reason `already_have` is not a conversion belongs next to the mapping (it is easy to undo)")


def test_the_panel_states_what_it_cannot_know_about_the_local_voice_hook():
    """The browser can toggle its own cues; the hook is another process with its own switch."""
    panel = panel_body(client_source())
    assert 'T("panel.voice.hook")' in panel, "the voice section renders the hook note from the dictionary"
    hook = dict_value("panel.voice.hook")
    for fact in ("MISAKANET_VOICE=0", "--voice", "cannot read or change"):
        assert fact in hook, f"the hook note must say {fact!r} instead of implying control"
    assert "localStorage" in client_source() or "VOICE_KEY" in client_source(), (
        "the browser toggle must be browser-local; anything else would claim to change the hook")


def test_nothing_makes_sound_without_opt_in_or_a_click():
    """Two playback paths, both asked for: the opt-in switch, and the button the person pressed."""
    calls = [line.strip() for line in PLAY_CUE.findall(client_source())]
    assert len(calls) == 2, f"expected exactly two playback paths (opt-in, click), found {len(calls)}: {calls}"
    for line in calls:
        assert "voiceEnabled()" in line or "onClick" in line, (
            f"a playback path must be guarded by the opt-in switch or a click: {line}")


def test_the_voice_and_intake_rules_can_go_red():
    assert not any("convert" in label.lower() for label in INTAKE_LABELS.findall('already_have: "cited by a lesson"'))
    assert any("convert" in label.lower() for label in INTAKE_LABELS.findall('already_have: "converted to a lesson"'))
    guarded = "if (entry.voice && voiceEnabled()) playCue(entry.voice);"
    unguarded = "playCue(entry.voice);"
    assert ("voiceEnabled()" in guarded) and ("voiceEnabled()" not in unguarded)


def test_every_panel_number_comes_from_the_session_log_or_the_browser_counters():
    """No constant may masquerade as a count: the rows are the log, the counters are localStorage."""
    panel = panel_body(client_source())
    for source_of_truth in ("log.searches", "log.intakes", "log.votes", "log.lessons", "browserStats()"):
        assert source_of_truth in panel, f"the panel stopped reading {source_of_truth!r}"


def test_the_panel_glyph_is_the_package_mark():
    """One brand mark, two places: the package icon the host shows in its plugin list, and the tab glyph.

    They are drawn differently (a file vs an inline SVG) because the host asks a tab for a component, so
    nothing structural keeps them equal — this does. A panel whose glyph drifted from the icon users see
    in the plugin manager is a small thing that looks like two different plugins.
    """
    mark = re.search(r'd="(M16 44V20[^"]*)"', (REPO / "icon.svg").read_text(encoding="utf-8"))
    assert mark, "icon.svg no longer contains the brand path this gate pins"
    assert mark.group(1) in client_source(), (
        "the panel's inline glyph must draw the same path as icon.svg, or the two marks drift apart")


# ── the panel's two seats, and the two ways they can be wired wrong ───────────
#
# The right sidebar ships from 0.1.5 on, and the panel must exist without it (the conversation ring is
# enough). Two mistakes are invisible in a browser that has the registry, and both are static:
# hard-injecting `sidebarRightTabs` (which pends or fails the plugin on an older line), and keying the
# body seat with anything other than the type `id` (which renders the host's "nothing can view this").

DEFERRED_SIDEBAR = re.compile(r'ctx\.inject\(\s*\[\s*"sidebarRightTabs"\s*\]')
PANEL_TYPE_ID = re.compile(r"var PANEL_ID = \"([^\"]+)\";")
# both spellings: a bare constant, or a string literal (which the first version of this gate missed
SIDEBAR_KEY = re.compile(r'name: "sidebar\.right\.pane\.tab",\s*key: ([A-Za-z_$][\w$.]*|"[^"]*")')


def test_the_panel_is_reachable_in_the_conversation_ring():
    """The ring takes a list entry: an id, an order and a label — there is no icon channel there."""
    source = client_source()
    assert 'name: "conversation.view"' in source, "the panel must be registered in the conversation ring"
    block = source[source.index('name: "conversation.view"'):]
    block = block[:block.index("}", block.index("label:"))]
    for field in ("id: PANEL_ID", "order:", "label:"):
        assert field in block, f"a conversation-view entry needs {field!r} ({block[:120]!r})"


def test_the_sidebar_seat_is_deferred_so_older_lines_keep_the_conversation_tab():
    """`sidebarRightTabs` must NOT be a static inject: on a host without it the fiber would pend."""
    source = client_source()
    assert DEFERRED_SIDEBAR.search(source), (
        "the sidebar registration must ride a deferred `ctx.inject(['sidebarRightTabs'], …)`")
    assert '"sidebarRightTabs"' not in re.findall(r"var inject = \[([^\]]*)\]", source)[0], (
        "the registry must not sit in the module's static inject list, or a pre-0.1.5 host pends")
    deferred = source[source.index('ctx.inject(["sidebarRightTabs"]'):]
    for guard in ("typeof tabs.register !== \"function\"", "catch (error)", "unwind"):
        assert guard in deferred, f"the deferred registration must guard against {guard!r}"


def test_the_sidebar_body_is_keyed_by_the_type_id_the_contract_requires():
    """The host dispatches `sidebar.right.pane.tab` with the *type's* id; any other key is dead."""
    source = client_source()
    type_id = PANEL_TYPE_ID.search(source)
    assert type_id, "the panel type id must be a single named constant"
    keys = SIDEBAR_KEY.findall(source)
    assert keys, "no `sidebar.right.pane.tab` registration found — this check would pass vacuously"
    allowed = {"PANEL_ID", '"%s"' % type_id.group(1)}
    for key in keys:
        assert key in allowed, (
            f"a pane seat keyed {key!r} will never be dispatched: the key must equal the type id "
            f"({type_id.group(1)!r}), written as PANEL_ID or as that literal")


def test_the_guide_entry_carries_the_id_the_contract_requires():
    """`guide[].id` is required by the host (it becomes the entry's `entryId` and its React key).

    The one third-party implementation of this pattern omits it, which is harmless only while that
    provider contributes a single entry — so this pins that we supply it rather than copying the bug.
    """
    source = client_source()
    guide = source[source.index("guide: [{"):]
    guide = guide[:guide.index("}]")]
    assert re.search(r'\bid:\s*"', guide), f"the guide entry needs an id: {guide[:120]!r}"
    assert "icon: MisakanetGlyph" in guide, "the guide capsule must carry the product glyph"


def test_the_slot_registration_rules_can_go_red():
    assert not DEFERRED_SIDEBAR.search('ctx.inject(["slots"], cb)')
    assert DEFERRED_SIDEBAR.search('ctx.inject(["sidebarRightTabs"], cb)')
    assert SIDEBAR_KEY.findall('{ name: "sidebar.right.pane.tab", key: PANEL_ID }') == ["PANEL_ID"]
    assert SIDEBAR_KEY.findall('{ name: "sidebar.right.pane.tab", key: "misakanet-panel" }') == ['"misakanet-panel"']
    assert SIDEBAR_KEY.findall('{ name: "sidebar.right.pane.tab" }') == []  # non-vacuity matters


def test_the_panel_cannot_file_an_issue():
    """The browser half reads and votes; it never submits an intake.

    The only way to pull a receipt is to submit the same text again, and the server's dedup window is
    finite — so a page-triggered re-submit could file a *second* GitHub issue for the same problem. No
    click in a UI may create an issue, which is why the panel explains who re-checks instead of offering
    a button. This gate is the difference between a design note and an enforced one.
    """
    source = client_source()
    assert 'API + "/mcp"' not in source and '"tools/call"' not in source, (
        "the browser half must not call the MCP endpoint at all: submits create issues")
    panel = panel_body(source)
    assert 'T("panel.report.recheck")' in panel, (
        "the panel must say who re-checks a pending report, or the missing control looks like an oversight")
    assert "by the agent, not by this page" in dict_value("panel.report.recheck"), (
        "the sentence behind that key is what makes the missing control read as deliberate")


def test_every_counted_noun_in_the_panel_can_be_singular():
    """"1 reports" is the kind of thing that makes a panel look machine-written.

    The render caught it, and the fix is one helper — so this pins the helper rather than the sentence:
    a hard-coded plural next to a count is the bug, and it is invisible until someone has exactly one.
    """
    panel = panel_body(client_source())
    assert "function count(" in client_source(), "the plural helper must exist"
    hardcoded = [phrase for phrase in ('" searches', '" lessons surfaced', '" reports filed', '" votes (')
                 if phrase in panel]
    assert not hardcoded, (
        f"a count is concatenated with a hard-coded plural, so it reads wrong at 1: {hardcoded}")
    assert panel.count("count(") >= 6, (
        "the panel's counted nouns must all go through the helper")


def test_the_plural_helper_is_given_the_plural_where_english_is_irregular():
    """The first version printed "2 searchs" — and the commit message that introduced it said "2 searches".

    A helper that appends "s" is right for most of this panel's nouns and wrong for exactly one of them,
    which is the shape of bug that survives review. So the irregular plural is passed at the call site,
    and this gate refuses a two-argument `count(…, "search")`.
    """
    source = client_source()
    assert "function count(n, singular, many)" in source, "the helper must accept an explicit plural"
    bare = re.findall(r'count\([^)]*?"search"\)', source)
    assert not bare, f"`count(n, \"search\")` would print \"searchs\": {bare}"
    assert source.count('T("unit.search"), T("unit.searches")') >= 2, (
        "both search counts (the stat strip and the activity line) must pass the plural")
    assert dict_value("unit.searches") != dict_value("unit.search") + "s", (
        "the whole point of this call site is that English spells this plural irregularly")


def test_the_trust_rule_is_stated_once_and_every_row_shows_its_own_count():
    """A rule repeated under every row buries the numbers; a rule stated nowhere leaves them unexplained.

    The first version printed the E4 sentence only on rows whose count was 0 — so a lesson people had
    already confirmed twice read as a bare "2 human confirmations" with no explanation of what that
    means. Now the sentence is stated once for the section, and each row carries its own count plus an
    `→ E4` marker when it has crossed.
    """
    panel = panel_body(client_source())
    assert panel.count('T("panel.trust.footnote")') == 1, (
        "the rule belongs once per section, not once per row")
    assert "second is what agents read as E4" in dict_value("panel.trust.footnote"), (
        "the sentence behind that key is the rule")
    assert '→ E4' in panel, "a row past the threshold should say what its count means"
    assert 'count(confirmations, T("panel.trust.human"))' in panel, (
        "each row must print its own confirmation count through the plural helper")


def test_the_panel_asks_each_lesson_once_and_only_nags_about_open_reports():
    """Two things the live render measured rather than revealed by reading.

    * It made **8 `/api/helpful` calls for 4 lessons**: the effect re-runs on every log revision, and while
      the first round was in flight `trust[id]` was still `undefined`, so a second round started. A public
      endpoint should be asked once per lesson, so the panel keeps a `asked` ref.
    * It printed "a pending report is re-checked…" under a report that had already been **converted** — the
      sentence is about work that is still open, so it is now computed from the reports that are.
    """
    panel = panel_body(client_source())
    assert "react.useRef(Object.create(null))" in panel, "the once-per-lesson guard must exist"
    assert "!asked.current[lesson.lessonId]" in panel, "the fetch must consult the guard"
    assert "asked.current[lesson.lessonId] = true" in panel, "the guard must be set before the request"
    assert "var openReports = intakes.filter(" in panel, (
        "the re-check hint must be derived from the reports that are still open, not from any report")


# ── the rule the real host enforced, as a red/green gate ─────────────────────
#
# On 2026-10-01 the live GUI showed "Failed to load plugins / misakanet: failed". The host's own audit says
# exactly what happened (`dsh-app-boot`): the plugin's fiber ended in state `failed`, which means `apply()`
# threw. The client console then named the rule:
#
#     slot "tool.call.toolview" is not declared (a parent entry's children table must declare it)
#
# `tool.call.toolview` and `conversation.chat.assistant-actions` are **child slots**: a parent entry
# declares them, and registering into one before that declaration is committed throws. First-party plugins
# therefore register through `ctx.slots.inject(slot, …)`, which runs immediately when the declaration
# already exists and otherwise inside the declaring call. Registering directly — what this file did — made
# the *first* registration throw, which aborted `apply()`, failed the fiber, and took every other surface
# with it: the panel tab was never at fault, it simply never got registered.
#
# A fake context that accepts anything cannot see this. So the fake below encodes the host's rule, and the
# red fixture runs the same harness against a copy that registers directly again.

# The interpreter that runs the bundle; the repo already runs node from Python elsewhere.
NODE = "node"

CLIENT_APPLY_HARNESS = r"""
global.window = { __ModuleLoader__: { load: (m) => { global.__m = m; } } };
const fs = require('fs');
eval(fs.readFileSync(process.env.CLIENT_FILE, 'utf8'));
const react = { createElement: () => null, useState: (v) => [v, () => {}], useRef: (v) => ({ current: v }),
                useEffect: () => {}, Fragment: function () {} };
const mod = global.__m.factory((name) => (name === 'react' ? react : undefined));
const declared = new Set();          // what some parent entry has declared so far: nothing, at first
const registrations = [], warnings = [], pending = [];
const settingsRows = [];
const slots = {
  // Faithful ordering: the declaration commits, *then* the waiting callback runs. Nothing is declared
  // before we activate, which is exactly why registering a child slot directly throws.
  inject(slot, cb) { pending.push(slot); declared.add(slot); cb(); return () => {}; },
  register(options) {
    if (options.name === "settings.general.item") settingsRows.push(options.id);
    if (!declared.has(options.name)) {
      throw new Error(`slot "${options.name}" is not declared (a parent entry's children table must declare it)`);
    }
    registrations.push(options.key || options.id || options.name);
    return () => {};
  },
};
const realWarn = console.warn;
console.warn = (line) => warnings.push(String(line));
const sources = [];
const ctx = {
  effect: (fn) => { fn(); return () => {}; },
  slots,
  // The General-section row is a list seat whose id is the only thing that names it.
  // `inputTriggers` is a **service**, not a slot: the slash pipeline owns the draft, so the contract
  // that matters is `registerSource`. A host without it must lose the command and keep every seat.
  inject: (deps, cb) => {
    if (deps && deps[0] === 'inputTriggers') {
      cb({ inputTriggers: { registerSource: (src) => { sources.push(src.trigger + src.name); return () => {}; } } });
    } else {
      cb({ sidebarRightTabs: undefined });
    }
    return { dispose() {} };
  },
};
try { mod.apply(ctx); } catch (error) { warnings.push('apply threw: ' + error.message); }
console.warn = realWarn;
console.log(JSON.stringify({ registrations, warnings, pending, sources, settingsRows }));
"""


def _run_client_apply(client_file: Path) -> dict:
    done = subprocess.run([NODE, "--input-type=module", "-e", ""] if False else
                          [NODE, "-e", CLIENT_APPLY_HARNESS],
                          capture_output=True, text=True, timeout=120,
                          env={**os.environ, "CLIENT_FILE": str(client_file)})
    assert done.returncode == 0, done.stderr[-500:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_every_client_registration_waits_for_its_slot_declaration():
    """The regression that reached the owner's GUI: a child slot registered before its declaration.

    Only a context that enforces the host's rule can catch it, so the harness above throws the host's own
    message. Green here means every surface went through `slots.inject` and none raised.
    """
    if shutil.which(NODE) is None:
        pytest.skip("node runs the client half")
    result = _run_client_apply(REPO / "lib" / "client.js")
    assert result["warnings"] == [], (
        f"a surface failed to register — the real host would show `misakanet: failed`: {result['warnings']}")
    assert len(result["registrations"]) == 14, result
    assert result["pending"].count("tool.call.toolview") == 4, result
    for seat in ("conversation.view", "sidebar.panellist", "main", "conversation.input.overlay"):
        assert seat in result["pending"], (
            f"{seat} must wait for its declaration too, not just the child slots")
    # The slash command is a service registration, and it is the only one: one `/misakanet` source.
    assert result["sources"] == ["/misakanet"], result
    # The plugin page's row key is `<bundle>#<row id>`, exactly as the bundle patch spells the row.
    assert "misakanet#misakanet-mcp" in result["registrations"], result
    assert result["settingsRows"] == ["misakanet"], result
    # The two frame-wide seats: a toast in the shell layer and an action at the sidebar foot.
    assert "misakanet-lesson-toast" in result["registrations"], result
    assert "misakanet-summary" in result["registrations"], result   # the General-section preference row
    assert "misakanet" in result["registrations"], (
        "the bundle-level config is keyed by the package name; the row-level one by <bundle>#<row id>")


def test_the_declaration_rule_can_go_red(tmp_path):
    """The pre-fix shape: register into a child slot directly, and the harness must report it."""
    if shutil.which(NODE) is None:
        pytest.skip("node runs the client half")
    source = client_source()
    mutated = source.replace(
        """					return ctx.effect(function () {
						return ctx.slots.inject(slot, function () {
							return ctx.slots.register(options, component);
						});
					}, "misakanet: " + label);""",
        """					return ctx.effect(function () {
						return ctx.slots.register(options, component);
					}, "misakanet: " + label);""")
    assert mutated != source, "the guarded registration is no longer where this fixture expects it"
    path = tmp_path / "client.js"
    path.write_text(mutated, encoding="utf-8")
    result = _run_client_apply(path)
    assert result["warnings"], "the harness must catch a direct child-slot registration"
    assert "is not declared" in " ".join(result["warnings"]), result
