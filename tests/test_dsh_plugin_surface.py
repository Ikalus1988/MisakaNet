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
import posixpath
import re
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
