#!/usr/bin/env python3
"""`@misaka-net/fatal-guard` must have a release path, or its fixes never reach npm.

The gap this file pins (#3983 follow-up, 2026-10-28)
----------------------------------------------------
`npm` served `@misaka-net/fatal-guard@0.3.0` (2026-07-25) while two October fixes — the search-first
loop (#3676) and the payload repair (#3647) — sat in `main` with 45 green tests. Users running
`npx @misaka-net/fatal-guard` kept getting the version whose `stackSnippet` drops the first stderr
line, which is the line that names the error.

The reason was not neglect, and it is the same reason `@misaka-net/misakanet-setup` had (#3691):
`release-please-config.json` declared **two** packages (`.` and `packages/misakanet-setup`), so
nothing ever bumped fatal-guard's version and nothing ever created its tag. The publish workflow
existed, listened for a tag nobody produced, and did its job perfectly on zero occasions.

What is asserted here, and why each is a fact rather than prose:

* **release-please owns the package.** A `node` package whose tag is exactly
  `fatal-guard-v<version>` — computed here, not described. `include-component-in-tag` +
  `tag-separator: "-"` is what makes the tag `fatal-guard-v…` instead of `fatal-guard-v…` or `v…`.
* **The tag cannot collide with the repository's PyPI line.** `release-pypi.yml` publishes on
  `push: tags: ["v*"]`; a fatal-guard tag starting with `v` would push an npm package to PyPI.
* **The publish workflow listens for that exact tag.** A workflow that publishes on `main` would
  publish on every merge; a workflow listening for a differently-spelled tag publishes never.
* **release-please and the package agree on the version.** If the manifest entry drifts from
  `packages/fatal-guard/package.json`, the release PR either refuses to open or renumbers.
* **The publish job sits behind the `release` environment**, so `approval-watch.yml` covers it —
  the same rule every publishing workflow in this repository follows.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "release-please-config.json"
MANIFEST = REPO / ".release-please-manifest.json"
PACKAGE = REPO / "packages" / "fatal-guard" / "package.json"
WORKFLOW = REPO / ".github" / "workflows" / "fatal-guard-publish.yml"
PACKAGE_PATH = "packages/fatal-guard"


def config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def package_version() -> str:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))["version"]


def release_tag(version: str) -> str:
    """release-please's tag name for a component, with the repository's declared separator.

    Ported from release-please's `TagName.toString()` and the Node strategy's
    `normalizeComponent()`: `component-v<version>` when `include-component-in-tag` is set and the
    separator is `-`.
    """
    block = config()["packages"][PACKAGE_PATH]
    assert block.get("include-component-in-tag") is True
    separator = block.get("tag-separator", "-")
    component = block["component"]
    return f"{component}{separator}v{version}"


def test_release_please_owns_the_fatal_guard_package():
    block = config()["packages"].get(PACKAGE_PATH)
    assert block, (
        "release-please does not declare packages/fatal-guard — nothing will ever bump its version "
        "or create its tag, which is exactly why npm stayed at 0.3.0 through two fixes")
    assert block["release-type"] == "node"
    assert block["package-name"] == "@misaka-net/fatal-guard"
    assert block["component"] == "fatal-guard"


def test_the_manifest_tracks_the_package_version():
    assert PACKAGE_PATH in manifest(), "release-please cannot open a release PR for an untracked path"
    assert manifest()[PACKAGE_PATH] == package_version(), (
        f"manifest says {manifest()[PACKAGE_PATH]}, package.json says {package_version()}")


def test_the_tag_cannot_collide_with_the_pypi_release_line():
    tag = release_tag(package_version())
    assert tag.startswith("fatal-guard-"), tag
    assert not tag.startswith("v"), (
        "release-pypi.yml publishes on `v*`; a package tag starting with v would push to PyPI")
    assert tag == "fatal-guard-v" + package_version()


def test_the_publish_workflow_listens_for_that_tag():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"tags:\s*\n\s*-\s*\"fatal-guard-v\*\"", text), (
        "the publish workflow must trigger on the tag release-please creates")
    # And only the tag: publishing on a branch push would publish every merge.
    assert "branches:" not in text.split("permissions:")[0], (
        "publishing must not be wired to a branch push")


def test_the_publish_job_sits_behind_the_release_environment():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert re.search(r"^\s+environment:\s*release\s*$", text, re.M), (
        "approval-watch.yml only covers workflows that declare `environment: release`")


def test_the_version_is_not_duplicated_in_the_package():
    """`bin/fatal-guard.js` reads `--version` from package.json, so there is one source of truth."""
    bin_text = (REPO / "packages" / "fatal-guard" / "bin" / "fatal-guard.js").read_text(encoding="utf-8")
    assert "package.json" in bin_text, "a hard-coded version would drift from the manifest"
    assert f"'{package_version()}'" not in bin_text and f'"{package_version()}"' not in bin_text


def test_no_test_file_pins_the_version_it_asserts_on():
    """A literal version in a test makes the release PR unmergeable, and the failure is circular.

    Measured 2026-10-28 on release PR #3827: release-please bumped 0.3.0 -> 0.3.1, `tests/cli-contract.js`
    kept asserting `/^0\\.3\\.0\\n$/`, and the package's own suite failed on its own release — the last
    thing standing between two merged fixes and npm was the test that checks the version.

    The rule is deliberately blunt: a version string anywhere in the code is a finding, including in an
    assertion *message*. The first draft of the packaging test learned that — its message said "this is
    exactly how 0.3.0 and 0.3.1 shipped broken" and this gate refused it. Rewording a message is cheaper
    than teaching the gate which string literals are comparisons, and the shape that broke the release
    (`assert.match(stdout, /^0\\.3\\.0$/`) sits too close to a message to draw a safe line between them.

    The comparison normalises `\\.` to `.` first: the literal appears escaped inside a regular expression
    (`0\\.3\\.0`), and a naive search for `0.3.0` does not find it. That is not a detail — the first
    version of this gate passed against the very file it was written for.
    """
    version = package_version()
    offenders = []
    for path in (REPO / "packages" / "fatal-guard" / "tests").rglob("*.js"):
        # Comments are not assertions. The comment in `cli-contract.js` explains this very failure and
        # names the versions it happened at; scanning it would make documenting the bug the bug.
        text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
        text = re.sub(r"//[^\n]*", "", text).replace("\\.", ".")
        if re.search(r"(?<![0-9.])" + re.escape(version) + r"(?![0-9.])", text):
            offenders.append(str(path.relative_to(REPO)))
    assert not offenders, (
        f"these tests pin the current version {version}; read it from package.json instead: {offenders}")


def test_the_fatal_guard_release_can_be_merged_without_the_root_release():
    """`separate-pull-requests` is what makes "ship fatal-guard 0.3.1" possible on its own.

    With it `false` (the default), release-please merges every component into **one** PR — the shape
    #3827 had, where merging the fix this repository needed also pushed a root **major** (3.0.0,
    Python >= 3.11) to PyPI. Shipping one package then required either publishing a breaking change
    nobody had approved, or a manual tag that bypasses the ledger.

    The setting is asserted here because the failure mode is silent: turning it off does not error, it
    just goes back to bundling, and the next person discovers it while trying to release one package.
    """
    assert config().get("separate-pull-requests") is True, (
        "without separate-pull-requests, every package release is bundled with the root package — "
        "which is how a fatal-guard patch turned into a major PyPI release")
