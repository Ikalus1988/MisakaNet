#!/usr/bin/env python3
"""The setup package's release must be wired to the repository, and its drift must be a red gate.

The report this file answers (#3691)
------------------------------------
`npm` had `@misaka-net/misakanet-setup` at **0.5.6** (published 2026-09-19) while the package's
source had moved **ten commits ahead** (the last change 2026-10-19). A new user running
`npx @misaka-net/misakanet-setup` got a month-old installer.

The report blamed "no publish automation". That was wrong: `.github/workflows/misakanet-setup-publish.yml`
has published the package on a `misakanet-setup-v*` tag since 0.2.0, and it does the right thing
with the tarball it builds. What was missing was the half *before* it: nothing ever bumped
`packages/misakanet-setup/package.json`, and nothing ever created the tag, because
`release-please-config.json` declared **one** package (the repository root). The publish path was
fine and had nothing to publish.

`--verify` could not see the gap either, and still cannot: it compares against **npm latest**
(`latestPublishedVersion()` in the installer), and 0.5.6 *is* npm latest. The gap is between the
**registry** and the **repository**, and that is what the drift gate measures.

What is pinned here, and why each assertion is a *fact* rather than prose:

* **release-please owns the setup package** — the config declares it, as a `node` package, with a
  component whose tag is exactly `misakanet-setup-v<version>`. The tag is computed with a port of
  release-please's own `TagName.toString()` and the Node strategy's `normalizeComponent()`, so the
  naming is not a guess: upstream's source is quoted in the functions.
* **the tag cannot collide with the repository's own tags** — `v*` is the Python release line, and
  `release-pypi.yml` publishes on `push: tags: ["v*"]`. A setup tag that started with `v` would
  push the installer to PyPI.
* **the publish workflow listens for that tag** — and only the tag (a plain push to `main` must
  not publish; it must ask for a tag first).
* **the drift gate can go red** — `scripts/setup_release_drift.py` holds the decision, and this
  file runs it against synthetic repositories: a source that moved with no release (red), a
  source that matches its release (green), a release that never reached npm (red), a change
  inside the grace period (green, because a release-please flow bumps the version *after* the
  change lands), and a registry that cannot be reached (neither red nor green — "could not
  answer").
* **the gate watches every file the tarball ships** — the shipped set is declared by the package
  itself (`package.json`'s `files` and the sources `scripts/copy-hook.mjs` copies in), and a new
  shipped file that the gate does not watch is a hole in the gate.
* **the gate runs where the drift appears** — in the package's own CI workflow, on the pull
  requests that touch the package, and on a schedule, because the drift it measures accumulates
  without producing a pull request.

The gate's decision logic lives in `scripts/setup_release_drift.py`, the repository's pattern
(`scripts/install_smoke.py` holds the decision and `tests/test_install_smoke.py` mutates it), and
the workflow calls that same module — so the gate CI runs and the gate this file proves are one
implementation, not two.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflows")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from setup_release_drift import (  # noqa: E402  (the module under test)
    GRACE_DAYS,
    NPM_PACKAGE,
    SHIPPED_SOURCES,
    TAG_PREFIX,
    assess,
    published_versions,
    released_tags,
    version_key,
)

CONFIG = REPO / "release-please-config.json"
MANIFEST = REPO / ".release-please-manifest.json"
PUBLISH_WORKFLOW = REPO / ".github" / "workflows" / "misakanet-setup-publish.yml"
CI_WORKFLOW = REPO / ".github" / "workflows" / "misakanet-setup-ci.yml"
SETUP_PATH = "packages/misakanet-setup"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on(workflow: dict) -> dict:
    """The `on:` block — PyYAML reads the bare key `on` as the boolean True."""
    return workflow[True] if True in workflow else workflow["on"]


# ── release-please's own rules, ported ────────────────────────────────────────────────────────────
# src/util/tag-name.ts and src/strategies/node.ts. release-please is not installed here, so the
# two functions that decide the tag name are transcribed, and the transcription is asserted
# against upstream's own examples below — the same discipline `test_release_please_exclude_paths.py`
# uses for release-please's commit matcher.


def _tag_name(version: str, component: str | None, separator: str = "-", include_v: bool = True) -> str:
    """release-please's `TagName.toString()` (src/util/tag-name.ts).

        toString(): string {
          if (this.component) {
            return `${this.component}${this.separator}${this.includeV ? 'v' : ''}${this.version}`;
          }
          return `${this.includeV ? 'v' : ''}${this.version}`;
        }
    """
    if component:
        return f"{component}{separator}{'v' if include_v else ''}{version}"
    return f"{'v' if include_v else ''}{version}"


def _normalize_component(component: str | None) -> str:
    """release-please's Node strategy `normalizeComponent()` (src/strategies/node.ts).

        return component.match(/^@[\\w-]+\\//) ? component.split('/')[1] : component;
    """
    if not component:
        return ""
    return component.split("/")[1] if re.match(r"^@[\w-]+/", component) else component


def _parse_tag(tag: str) -> tuple[str | None, str, str | None] | None:
    r"""release-please's `TagName.parse()` (src/util/tag-name.ts), for the round trip.

        /^((?<component>.*)(?<separator>[^a-zA-Z0-9]))?(?<v>v)?(?<version>\d+\.\d+\.\d+.*)$/
    """
    match = re.match(r"^((.*)([^a-zA-Z0-9]))?(v)?(\d+\.\d+\.\d+.*)$", tag)
    if not match:
        return None
    component = match.group(2) or None
    separator = match.group(3)
    return component, match.group(5), separator


# ── 1. the tag name release-please would create ─────────────────────────────────────────────────


def test_the_ported_tag_rules_match_release_please_upstream():
    """The transcription is the thing the wiring depends on, so it is checked against upstream.

    Upstream's own unit tests (`test/util/tag-name.ts`) build the name from a version, a
    component and a separator, and the published tags in this repository are the ground truth
    for the format: `misakanet-setup-v0.5.6`.
    """
    assert _tag_name("1.2.3", "pkg") == "pkg-v1.2.3"
    assert _tag_name("1.2.3", None) == "v1.2.3"
    assert _tag_name("1.2.3", "pkg", ".") == "pkg.v1.2.3"
    assert _tag_name("1.2.3", "pkg", "-", include_v=False) == "pkg-1.2.3"
    assert _normalize_component("@misaka-net/misakanet-setup") == "misakanet-setup"
    assert _normalize_component("misakanet-setup") == "misakanet-setup"
    assert _normalize_component(None) == ""
    assert _parse_tag("misakanet-setup-v0.5.6") == ("misakanet-setup", "0.5.6", "-")
    assert _parse_tag("v2.48.0") == (None, "2.48.0", None)


def test_release_please_owns_the_setup_package():
    """The missing link was the version bump, and release-please is what owns a version.

    `release-please-config.json` declared one package (the repository root), so nothing ever
    bumped `packages/misakanet-setup/package.json` and nothing ever asked for a release of it.
    """
    config = _read_json(CONFIG)
    assert SETUP_PATH in config["packages"], (
        f"release-please-config.json does not declare {SETUP_PATH}: the setup package's version "
        "is bumped by nobody, so the publish workflow has nothing to publish"
    )
    entry = config["packages"][SETUP_PATH]
    assert entry["release-type"] == "node", (
        f"the setup package is an npm package, so its release type must be 'node', not "
        f"{entry['release-type']!r}"
    )
    assert entry.get("package-name") == NPM_PACKAGE, (
        "package-name must name the package npm knows, or release-please would publish under "
        "another name"
    )


def test_the_release_tag_is_the_one_the_publish_workflow_listens_for():
    """The tag is computed the way release-please computes it, not the way it is hoped for.

    release-please builds it as `<component><separator>v<version>` (src/util/tag-name.ts), with
    the component taken from `component` or, failing that, from the package name with the scope
    stripped (src/strategies/node.ts), and `include-component-in-tag` defaulting to true
    (src/strategies/base.ts). The publish workflow listens for `misakanet-setup-v*`, so the two
    have to agree — this is the assertion that says they do.
    """
    entry = _read_json(CONFIG)["packages"][SETUP_PATH]
    component = entry.get("component") or _normalize_component(entry.get("package-name"))
    include_component = entry.get("include-component-in-tag", True)
    separator = entry.get("tag-separator", "-")
    tag = _tag_name("0.6.0", component if include_component else None, separator)

    assert tag == "misakanet-setup-v0.6.0", (
        f"release-please would tag {tag!r}, which is not the {TAG_PREFIX}* the publish workflow "
        "listens for"
    )
    filters = _on(_read_yaml(PUBLISH_WORKFLOW))["push"]["tags"]
    assert any(fnmatch.fnmatch(tag, pattern) for pattern in filters), (
        f"no publish-workflow tag filter matches {tag!r}: {filters}"
    )


def test_the_setup_release_tag_cannot_be_mistaken_for_a_python_release():
    """`v*` is the Python release line, and `release-pypi.yml` publishes on it.

    A setup tag that started with `v` would push the installer to PyPI, and a root tag that
    started with `misakanet-setup-` would stop the PyPI publish from firing at all.
    """
    entry = _read_json(CONFIG)["packages"][SETUP_PATH]
    component = entry.get("component") or _normalize_component(entry.get("package-name"))
    tag = _tag_name("0.6.0", component, entry.get("tag-separator", "-"))
    assert not fnmatch.fnmatch(tag, "v*"), (
        f"{tag!r} matches the repository's Python release tags (v*) — release-pypi.yml would "
        "publish the installer to PyPI"
    )
    assert not fnmatch.fnmatch("v2.48.0", f"{component}*"), (
        "the repository's own release tag matches the setup component's prefix — the two tag "
        "lines would collide"
    )


def test_the_first_setup_release_is_a_bump_and_not_a_republish():
    """Before release-please has released the package, its first version must be a new one.

    `initial-version` is what release-please uses when a path has no release yet
    (src/strategies/base.ts, `initialReleaseVersion()`). Without it, the default is **1.0.0** —
    a jump from 0.5.6 that nobody asked for. With it set to a version that is already published,
    the tag would already exist and the publish would skip straight past the change that needed
    publishing, which is the state this repository sat in.

    Once release-please has released the package (the manifest carries the path), the manifest
    wins and `initial-version` no longer applies — so the assertion only speaks while the
    bootstrap has not happened yet.
    """
    manifest = _read_json(MANIFEST)
    if SETUP_PATH in manifest:
        pytest.skip("release-please has already released the setup package; the manifest wins")
    entry = _read_json(CONFIG)["packages"][SETUP_PATH]
    initial = entry.get("initial-version")
    assert initial, (
        "the setup package has no release yet, so release-please would fall back to 1.0.0 "
        "(src/strategies/base.ts) — declare initial-version"
    )
    assert version_key(initial), f"initial-version {initial!r} is not X.Y.Z"
    current = _read_json(REPO / SETUP_PATH / "package.json")["version"]
    assert version_key(initial) > version_key(current), (
        f"initial-version {initial} is not newer than the published {current}: the first release "
        "would republish a version npm already has, and the drift would survive it"
    )


# ── 2. the publish path: a release tag, then the publish ───────────────────────────────────────


def test_the_publish_workflow_creates_the_tag_before_it_publishes():
    """The publish path needs a tag, and before this nothing created one.

    The `tag` job reads the version release-please bumped, creates `misakanet-setup-v<version>`
    and dispatches the publish at that tag; the `publish` job itself only runs for a tag push or
    a manual dispatch, so a push to `main` cannot publish whatever `main` happens to hold.
    """
    workflow = _read_yaml(PUBLISH_WORKFLOW)
    assert "tag" in workflow["jobs"], (
        "the publish workflow has no job that creates the release tag — release-please cuts the "
        "version, but nothing turned it into a misakanet-setup-v* tag"
    )
    tag_job = workflow["jobs"]["tag"]
    assert "github.ref == 'refs/heads/main'" in tag_job["if"], (
        "the tag job must run on the repository's release flow landing on main, not on every push"
    )
    body = yaml.dump(tag_job)
    assert "gh workflow run misakanet-setup-publish.yml" in body, (
        "the tag job must dispatch the publish at the tag it created"
    )
    assert TAG_PREFIX in body, f"the tag job must create a {TAG_PREFIX}* tag"

    # The step that *creates* the tag, not the one that lists the tags it already has: a
    # read-only `git tag -l` in the deciding step must not be able to satisfy this.
    creations = [
        step
        for step in tag_job.get("steps", [])
        if re.search(r"^\s*git tag (?!-l)\S", str(step.get("run", "")), re.M)
    ]
    assert creations, (
        "no step creates the release tag — the deciding step only reads the tags that exist"
    )
    for step in creations:
        run = str(step.get("run", ""))
        assert "git push origin" in run, "the step that creates the tag must push it"
        assert TAG_PREFIX in run, f"the tag must be a {TAG_PREFIX}* tag"

    publish_if = workflow["jobs"]["publish"]["if"]
    assert "ref_type == 'tag'" in publish_if, (
        "the publish job must only run for a tag push or a manual dispatch, not for the push to "
        "main that asks for the tag"
    )


def test_the_publish_creates_a_release_after_npm_has_the_version():
    """The installer's version has to exist on the Releases page, not only on npm.

    Measured 2026-10-23: the last 100 GitHub Releases contained zero `misakanet-setup-*` entries,
    and `gh release view misakanet-setup-v0.6.0` answered "release not found". The `tag` job only
    creates the tag and dispatches the publish, so the package had no Release at all while the
    root package had one per release — the one page a reader opens to ask "what is the newest
    installer, and what changed" showed nothing.

    The order is the contract, not an implementation detail: a release created in the `tag` job
    would announce a version npm does not have yet, which is exactly the drift #3774 is about.
    So the step lives after `npm publish`, stands down when the release already exists, and
    refuses to invent a tag.
    """
    workflow = _read_yaml(PUBLISH_WORKFLOW)
    publish = workflow["jobs"]["publish"]
    steps = publish.get("steps") or []
    publish_at = next(
        (index for index, step in enumerate(steps) if step.get("name") == "Publish to npm"), None
    )
    release_at = next(
        (
            index
            for index, step in enumerate(steps)
            if "gh release create" in str(step.get("run", ""))
        ),
        None,
    )
    assert publish_at is not None, "the publish job lost its `Publish to npm` step"
    assert release_at is not None, (
        "no step creates a GitHub Release, so the installer's version is still invisible on the "
        "Releases page"
    )
    assert release_at > publish_at, (
        "the release is created before npm has the version; that advertises a version nobody can "
        "install, which is the drift this is meant to expose"
    )

    step = steps[release_at]
    run = str(step.get("run", ""))
    assert "misakanet-setup-v" in run, "the release must use the package's own tag prefix"
    assert "gh release view" in run, "a re-run must stand down instead of failing"
    assert "--verify-tag" in run, (
        "the step must not fabricate a tag — the `tag` job owns tag creation"
    )
    assert "--latest=false" in run, (
        "without it the installer's release becomes the repository's Latest and displaces the "
        "product release on the Releases page"
    )
    assert "setup_release_notes.py" in run, (
        "the body must come from the package CHANGELOG, not from `--generate-notes`"
    )
    assert (REPO / "scripts" / "setup_release_notes.py").is_file(), (
        "the step calls a script that does not exist"
    )
    env = step.get("env") or {}
    assert str(env.get("GH_TOKEN", "")).endswith("secrets.GITHUB_TOKEN }}"), (
        "a PAT-created release fires the root package's `on: release` publish for a tag it does "
        "not own; the built-in token must create this release"
    )
    permissions = publish.get("permissions") or {}
    assert permissions.get("contents") == "write", (
        "`gh release create` needs `contents: write` on this job"
    )


def test_a_setup_release_cannot_start_the_root_pipeline():
    """`on: release` fires for every release; the root package's workflows must ignore ours.

    The automatic setup Release is created with GITHUB_TOKEN and starts no workflow. A human
    backfill — or "publish release" in the UI — uses a user token and *does* fire
    `on: release: published`. Two workflows listen: `misakanet-publish.yml` compares the release
    tag with the root `package.json`, and `publish-container.yml` used to accept any tag that
    contained a dot. A `misakanet-setup-v<version>` tag fails the first guard and passes the
    second, so both now require the root line's `v*` prefix.
    """
    for name in ("misakanet-publish.yml", "publish-container.yml"):
        workflow = _read_yaml(REPO / ".github" / "workflows" / name)
        conditions = " ".join(str(job.get("if") or "") for job in workflow["jobs"].values())
        assert "startsWith(github.event.release.tag_name, 'v')" in conditions, (
            f"{name} still reacts to a `misakanet-setup-v*` release, which it does not publish"
        )


# ── 2.1 the version literals the release has to move ──────────────────────────────────────────────

# release-please's generic updater, transcribed. src/updaters/generic.ts. release-please is not
# installed here, so the rule that decides whether a plain-text file moves with the release is
# transcribed, and the transcription is applied to the real files below.
#
# The rule, in full:
#   * a line that carries `x-release-please-<scope>` has a version replaced **on that line**;
#   * a line that carries no marker is copied **verbatim**.
#
# The second half is the whole trap: a plain-text extra-file **without** the marker is not
# updated at all — and the release then ships a stale `--version` and a stale
# `X-MisakaNet-Version` header while the release pull request looks perfectly healthy.
_MARKER = re.compile(r"x-release-please-(?P<scope>major|minor|patch|version-date|version|date)")
_VERSION_ON_LINE = re.compile(
    r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(-(?P<pre>[\w.]+))?(\+(?P<build>[-\w.]+))?")


def _apply_release_please_generic(content: str, new_version: str) -> str:
    """release-please's `Generic.updateContent` (src/updaters/generic.ts), version scope.

    The marker decides the scope; only the `version` scope is used by the files this repository
    governs, and `test_the_markers_use_the_version_scope` says so out loud.
    """
    lines = []
    for line in content.split("\n"):
        match = _MARKER.search(line)
        if match and match.group("scope") == "version":
            # `String.replace` with a non-global regex replaces the **first** match on the line.
            line = _VERSION_ON_LINE.sub(new_version, line, count=1)
        lines.append(line)
    return "\n".join(lines)


# The files that carry the setup package's version. Each of them has to move with the release:
# the installer's literal is what `--version` prints and what goes into the X-MisakaNet-Version
# header, and the pin in the test is the tripwire that says "the version moved".
VERSION_LITERAL_FILES = {
    "packages/misakanet-setup/bin/misakanet-setup.mjs": "const VERSION = '{}'",
    "workers/misakanet-setup.test.mjs": "assert.equal(declared, '{}'",
}


def _setup_extra_files() -> list[str]:
    entry = _read_json(CONFIG)["packages"][SETUP_PATH]
    files = []
    for item in entry.get("extra-files", []):
        files.append(item if isinstance(item, str) else item.get("path"))
    return files


def _release_please_add_path(package_path: str, file: str) -> str:
    """release-please's `BaseStrategy.addPath` (src/strategies/base.ts), transcribed.

    The rule that bit us, verbatim from upstream:

        protected addPath(file: string) {
          if (!this.path || this.path === ROOT_PROJECT_PATH || file.startsWith('/')) {
            file = file.replace(/^\\/+/, '');
          } else {
            file = `${this.path.replace(/\\/+$/, '')}/${file}`;
          }
          ...
        }

    So a package **with a path** resolves its extra-files **relative to that path**, and only a
    path that starts with `/` (or a package at the root) is taken as repository-relative.
    """
    if not package_path or package_path == "." or file.startswith("/"):
        return file.lstrip("/")
    return f"{package_path.rstrip('/')}/{file}"


def _resolved_extra_files(package_path: str) -> set[str]:
    entry = _read_json(CONFIG)["packages"][package_path]
    files = []
    for item in entry.get("extra-files", []):
        path = item if isinstance(item, str) else item.get("path")
        files.append(_release_please_add_path(package_path, path))
    return set(files)


def test_every_version_literal_is_released_with_the_version():
    """A release that bumps the manifest must move every literal that names it.

    Measured 2026-10-22: the first automated release of this package bumped the manifest to
    0.6.0 and left the installer's literal at 0.5.6, because nothing told the release tooling
    about that file. Nine e2e legs went red on exactly that (`--version printed 0.5.6 but the
    installed package.json says 0.6.0`) — the safety net worked, but the release could not go
    out. The net is for the case where a person forgets; this is the case where the *tooling*
    forgets, and it needs the file to be listed.
    """
    extra = _setup_extra_files()
    resolved = _resolved_extra_files(SETUP_PATH)
    for path in VERSION_LITERAL_FILES:
        # The path release-please *resolves* is the one that matters: the config entry is
        # resolved against the package's own path first (`addPath`), so a repository-relative
        # entry in a package that has a path resolves to a file that does not exist — and the
        # updater skips it without a word.
        assert path in resolved, (
            f"{path} carries the package's version, but the release does not move it: the "
            f"release would ship the old version in --version and in the X-MisakaNet-Version "
            f"header (extra-files: {extra}, resolved: {sorted(resolved)})"
        )


def test_every_extra_file_resolves_to_a_file_that_exists():
    """The path release-please resolves is not the path the config writes.

    Measured 2026-10-22, on the first automated release of this package: the config listed
    `packages/misakanet-setup/bin/misakanet-setup.mjs` and `workers/misakanet-setup.test.mjs`,
    but the setup package's strategy **has a path**, and release-please resolves a package's
    extra-files relative to that path (`BaseStrategy.addPath`). Both entries therefore resolved
    to files that do not exist, and the updater skipped them silently
    (`createIfMissing: false`).

    The result was the thing #3738 was about: the release bumped the manifest to 0.6.0 and left
    the installer's literal at 0.5.6. The file was *listed*, and the marker rule was *right*, and
    the release still did not move it — because the listing resolved to nowhere.

    So this gate resolves every entry the way release-please does and asks whether a file is
    there. A path that does not resolve is a release that silently does not move a version.
    """
    config = _read_json(CONFIG)
    for package_path, entry in config["packages"].items():
        for item in entry.get("extra-files", []):
            path = item if isinstance(item, str) else item.get("path")
            resolved = _release_please_add_path(package_path, path)
            assert (REPO / resolved).is_file(), (
                f"the extra-files entry {path!r} of the package {package_path!r} resolves to "
                f"{resolved!r}, and that file does not exist — release-please skips a missing "
                f"file silently, so the release would not move whatever version it carries"
            )


def test_the_release_moves_the_literals_it_lists():
    """release-please's own rule, applied to the real files: the literal must follow the manifest."""
    current = _read_json(REPO / SETUP_PATH / "package.json")["version"]
    nxt = "9.9.9"          # a version that cannot already be in the repository
    for path, template in VERSION_LITERAL_FILES.items():
        source = (REPO / path).read_text(encoding="utf-8")
        updated = _apply_release_please_generic(source, nxt)
        assert template.format(nxt) in updated, (
            f"release-please would not move the literal in {path}: the marker is missing, or it "
            f"is not on the line that carries the version — and an unmarked line is copied "
            f"verbatim, so the release ships the old version"
        )
        assert template.format(current) not in updated, (
            f"the old version is still in {path} after the release moved it"
        )
        # Exactly one line may move. A line that *mentions* the marker also counts as a version
        # line, so a comment that quotes the marker next to a version would have that version
        # rewritten by the release — which is why the comment in these files never does.
        changed = [i for i, (before, after) in enumerate(zip(source.split("\n"), updated.split("\n")))
                   if before != after]
        assert len(changed) == 1, (
            f"the release would change {len(changed)} lines in {path}, not one: a line that "
            f"mentions the marker is treated as a version line, so a version next to the marker "
            f"text would be rewritten too"
        )


def test_the_markers_use_the_version_scope():
    """The transcription above only implements the `version` scope — so that is what is used."""
    for path in VERSION_LITERAL_FILES:
        for line in (REPO / path).read_text(encoding="utf-8").split("\n"):
            match = _MARKER.search(line)
            if match:
                assert match.group("scope") == "version", (
                    f"{path} uses the `x-release-please-{match.group('scope')}` marker, and the "
                    f"transcribed rule in this file only implements the `version` scope"
                )


# ── 2b. the commit scan's floor ────────────────────────────────────────────────────────────────


def _package_tag(entry: dict, version: str) -> str:
    """The tag release-please looks for when it backfills a release for a package.

    Upstream `Manifest.backfillReleasesFromTags` (src/manifest.ts):

        const component = await strategiesByPath[path].getComponent();
        const expectedTag = new TagName(
          expectedVersion,
          component,
          this.repositoryConfig[path].tagSeparator,
          this.repositoryConfig[path].includeVInTag
        );
        const foundTag = allTags[expectedTag.toString()];

    The component is the package's own (`misakanet-setup` for the setup package); the root has
    none, which is why the root's tags are `v2.48.0` and the setup package's are
    `misakanet-setup-v0.6.0`.
    """
    return _tag_name(
        version,
        entry.get("component"),
        entry.get("tag-separator", "-"),
        entry.get("include-v-in-tag", True),
    )


def _released_paths(config: dict, ledger: dict, repo: Path) -> set[str] | None:
    """Upstream's `releasesFound`, transcribed.

    A path counts as released only when it has a ledger entry **and** the tag that entry names
    exists. Upstream, in `Manifest.buildPullRequests` (src/manifest.ts):

        for (const path of paths) {
          const expectedVersion = this.releasedVersions[path];
          if (!expectedVersion) { continue; }
          if (expectedVersion.toString() === tagName.version.toString()) { releasesFound += 1; }
        }

    and in the fallback it reaches for when that did not find enough:

        const expectedVersion = this.releasedVersions[path];
        if (!expectedVersion) {
          this.logger.warn(`No version for path ${path}`);
          continue;
        }

    Both need the **ledger entry**, so the tags alone do not count: the setup package has release
    tags (`misakanet-setup-v0.5.6` and older) and is still not released as far as release-please
    is concerned, because the ledger has no entry for it. That is the whole reason the log says
    `No version for path packages/misakanet-setup` and the reason the scan had no floor.

    The ledger entry alone does not count either: release-please writes the *next* version into
    the ledger when it opens the release pull request, and the tag only exists once that pull
    request merges. **Which ledger is being judged is the whole question**, and it has to be the
    one release-please reads: the base branch of the pull request, never the proposal in the
    working tree. Reading the proposal is what deadlocked release PRs (#3755, measured
    2026-10-23): the PR carries 2.49.1/0.6.1 while the newest tags are 2.49.0/0.6.0, so the
    proposal says *nothing has ever been released* and demands a `bootstrap-sha` that #3756 had
    deliberately deleted. release-please itself did not need that floor — it kept updating #3755
    after the deletion — because it evaluates the base, so the gate evaluates the base too.

    Returns None when this checkout carries no tags at all: "cannot tell" must not be read as
    "not released", and a shallow clone carries none.
    """
    tags = set(_git(repo, "tag", "--list").split())
    if not tags:
        return None
    released = set()
    for path, entry in config.get("packages", {}).items():
        version = ledger.get(path)
        if not version:
            continue
        if _package_tag(entry, str(version)) in tags:
            released.add(path)
    return released


def _ledger_ref() -> str:
    """The ref whose manifest release-please reads: a pull request's **base**, not its proposal.

    Measured on #3755 (2026-10-23): the release PR carried 2.49.1/0.6.1 in its ledger while the
    newest tags were still 2.49.0/0.6.0. Read from the working tree, that says neither package has
    ever been released — so this gate demanded a `bootstrap-sha` that #3756 had deleted
    twenty-two minutes after the PR opened, and `audit` could never go green again: the floor
    could only come back in a merge that the check was refusing.

    release-please never judges the proposal. It reads the manifest at the base of the branch, and
    the record says so: it kept updating #3755 after the floor was deleted, without needing one.
    So the gate reads what release-please reads. In Actions `GITHUB_BASE_REF` names the base;
    locally the current branch's upstream is the same fact, and `origin/main` covers a detached
    checkout. `HEAD` is the last resort so this never becomes an unreadable gate.
    """
    base = os.environ.get("GITHUB_BASE_REF", "").strip()
    candidates = ([f"origin/{base}"] if base else []) + ["@{upstream}", "origin/main", "HEAD"]
    for ref in candidates:
        probe = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return ref
    return "HEAD"


def _ledger_from(ref: str) -> dict:
    """The release ledger at `ref` — the input release-please would see for this branch."""
    return json.loads(_git(REPO, "show", f"{ref}:.release-please-manifest.json"))


def _release_please_needs_bootstrap(config: dict, released: set[str]) -> bool:
    """release-please's `Manifest.buildPullRequests` (src/manifest.ts), transcribed.

    The rule that decides whether the commit scan has a floor at all:

        let releasesFound = 0;
        const expectedReleases = Object.keys(strategiesByPath).length;
        ...
        const needsBootstrap = releasesFound < expectedReleases;

    and the floor itself, inside the scan:

        } else if (needsBootstrap && commit.sha === this.bootstrapSha) {
          this.logger.info(
            `Needed bootstrapping, found configured bootstrapSha ${this.bootstrapSha}`
          );
          break;
        }

    So `bootstrap-sha` is read **only while `needsBootstrap` is true** — and a package that
    release-please has never released is not counted in `releasesFound`, so the scan has no
    answer to "where does this package's history start" and falls back to the beginning of the
    repository.
    """
    return len(released) < len(config.get("packages", {}))


def test_the_commit_scan_has_a_floor_while_a_package_is_unreleased():
    """The scan needs a floor, or the release PR cannot be rebuilt at all.

    Measured 2026-10-22: the setup package (`packages/misakanet-setup`) joined the manifest in
    #3691 and has never been released by release-please, so it has no entry in the ledger
    (`.release-please-manifest.json`). Without an entry, release-please cannot say where that
    package's history starts and falls back to the beginning of the repository — 1237 commits —
    and walks all of it through GitHub's GraphQL API. The walk dies at roughly the 29th page,
    every time (#3740).

    `bootstrap-sha` is the floor, and it is the *only* floor: the branch that reads it is guarded
    by `needsBootstrap`, and without a configured sha the comparison can never be true, so the
    scan runs to the beginning of the repository.

    This gate exists because the floor was lost without anybody noticing. #3744 edited this same
    file — to give the setup package's extra-files a leading `/` — and the edit took the whole
    file with it, `bootstrap-sha` included. The next two release-please runs then failed exactly
    the way the first ones had, and the reason had to be read out of a failure log
    ("No version for path packages/misakanet-setup") rather than out of a gate.

    The other direction is the same rule: once every configured package has been released — a
    ledger entry **and** the tag that entry names — the floor has outlived its purpose and has to
    go. A bootstrap that outlives its purpose would silently truncate a future changelog instead
    of failing loudly: the day a new package joins the manifest without a ledger entry, the stale
    sha would cut that package's history off at an arbitrary commit, and nobody would see it.

    "Released" needs both halves on purpose. The ledger entry alone is not enough — release-please
    writes the *next* version into the ledger when it opens the release pull request, and the tag
    only exists once that pull request merges. The ledger that decides whether the floor is
    needed is therefore the **base** ledger — the one release-please reads. Judging the release
    PR's proposal instead is what made every release PR demand a floor its own merge would
    delete (#3755).
    """
    config = _read_json(CONFIG)
    try:
        ledger = _ledger_from(_ledger_ref())
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        # No readable git ref (an exported tarball, say): judge the file that is here.
        ledger = _read_json(MANIFEST)
    bootstrap_sha = config.get("bootstrap-sha")

    released = _released_paths(config, ledger, REPO)
    if released is None:
        pytest.skip(
            "this checkout carries no release tags, so it cannot tell which packages have been "
            "released — a shallow clone carries none, and \"cannot tell\" is not \"not released\""
        )

    if _release_please_needs_bootstrap(config, released):
        missing = [path for path in config.get("packages", {}) if path not in released]
        assert bootstrap_sha, (
            f"{missing} has not been released by release-please (no ledger entry, or no tag for "
            f"it) and the config carries no `bootstrap-sha`: release-please cannot say where that "
            f"package's history starts, so it scans from the beginning of the repository and the "
            f"release PR cannot be rebuilt at all (#3740)"
        )
    else:
        assert not bootstrap_sha, (
            f"every configured package has been released, so the scan no longer needs a floor — "
            f"`bootstrap-sha` ({bootstrap_sha}) is inert now, and it would silently truncate a "
            f"future changelog instead of failing loudly"
        )


def test_a_release_pull_request_is_judged_on_the_base_ledger():
    """A release PR must not be asked for a floor its own merge would delete (#3755).

    Two readings of the same config, and only one of them can be right: the base branch's ledger
    says every package is released (so no floor), while the PR's proposal — every version bumped
    to a tag that does not exist yet — says nothing has ever been released (so a floor). The
    first is what release-please reads; the second is the deadlock, because the floor can only
    come back in a merge that the check keeps refusing.
    """
    config = _read_json(CONFIG)
    base = _ledger_from(_ledger_ref())
    released = _released_paths(config, base, REPO)
    if released is None:
        pytest.skip("this checkout carries no release tags, so it cannot tell")

    assert not _release_please_needs_bootstrap(config, released), (
        "the base ledger says every configured package is released, so a release PR must not be "
        "the one that demands a bootstrap floor"
    )

    # The exact shape #3755 presents: the ledger proposes versions whose tags cannot exist yet.
    proposed = {path: "99.0.0" for path in base}
    assert _release_please_needs_bootstrap(
        config, _released_paths(config, proposed, REPO) or set()
    ), (
        "judging the proposal is the #3755 deadlock this helper exists to avoid — if this ever "
        "stops being true, the gate no longer distinguishes a release PR from an unreleased package"
    )


def test_the_bootstrap_sha_is_a_commit_that_exists():
    """A floor that points at nothing is not a floor.

    A sha that is not in the repository would never match a commit in the scan, and the scan
    would walk to the beginning of the repository anyway — a failure that looks exactly like
    "no floor configured", which is the harder one to see.
    """
    sha = _read_json(CONFIG).get("bootstrap-sha")
    if not sha:
        pytest.skip("no `bootstrap-sha` is configured — there is no floor to point at")

    assert re.fullmatch(r"[0-9a-f]{40}", sha), (
        f"bootstrap-sha {sha!r} is not a full commit sha"
    )
    kind = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-t", sha],
        capture_output=True,
        text=True,
    ).stdout.strip()
    if kind == "commit":
        return
    # A shallow checkout (the CI matrix uses the default depth of 1) does not carry the history
    # this needs. Not being able to check is not the same as the sha being wrong — and the
    # full-history workflows (pr-checks, the publish workflow) do carry it.
    if _git(REPO, "rev-parse", "--is-shallow-repository").strip() == "true":
        pytest.skip("the checkout is shallow, so the commit is not here to check")
    pytest.fail(
        f"bootstrap-sha {sha} is not a commit in this repository, so the scan would never stop "
        f"there — it would run to the beginning of the repository and fail the same way"
    )


# ── 3. the drift gate ───────────────────────────────────────────────────────────────────────────


def test_the_drift_gate_runs_where_the_drift_appears():
    """It has to fire where the drift appears, and not on every unrelated pull request.

    The drift accumulates without producing a pull request — a release that was cut and never
    published, or a source that moved and was never released — so the gate also runs on a
    schedule. The matrix jobs are skipped there: the schedule is the sweep's, not the test
    suite's.
    """
    workflow = _read_yaml(CI_WORKFLOW)
    on = _on(workflow)
    assert "pull_request" in on, "the gate must run on pull requests"
    paths = on["pull_request"]["paths"]
    assert paths, "the gate's pull_request trigger has no paths filter — it would fire on everything"
    assert f"{SETUP_PATH}/**" in paths, f"the gate must watch {SETUP_PATH}"
    for catch_all in ("**", "**/*", "/"):
        assert catch_all not in paths, f"the path filter {catch_all!r} watches the whole repository"
    assert "schedule" in on, (
        "the gate must also run on a schedule: drift accumulates without a pull request, and "
        "that is how npm sat at 0.5.6 for a month"
    )
    assert "drift" in workflow["jobs"], "the package's CI workflow has no drift job"
    for name in ("unit", "pack", "e2e"):
        assert "schedule" in str(workflow["jobs"][name].get("if", "")), (
            f"the {name} job must be skipped on the schedule — the daily sweep is the drift "
            "job's, and running the matrix every day is a bill nobody asked for"
        )


def _copied_sources() -> set[str]:
    """The repository paths `scripts/copy-hook.mjs` copies into the tarball.

    The script resolves them from the package directory:
    `resolve(here, '..', '..', '..', 'integrations', 'agent-autostart', 'checkpoint_reminder.mjs')`.
    """
    copy_hook = (REPO / SETUP_PATH / "scripts" / "copy-hook.mjs").read_text(encoding="utf-8")
    sources = set()
    for match in re.finditer(r"resolve\(\s*here,\s*([^)]*)\)", copy_hook):
        parts = [part.strip().strip("'") for part in match.group(1).split(",") if part.strip()]
        if len(parts) >= 4 and parts[:3] == ["..", "..", ".."]:
            sources.add("/".join(parts[3:]))
    return sources


def _covers(watched: set[str], path: str) -> bool:
    path = path.rstrip("/")
    return any(
        entry.rstrip("/") == path
        or path.startswith(entry.rstrip("/") + "/")
        or entry.rstrip("/").startswith(path + "/")
        for entry in watched
    )


def test_the_gate_watches_every_file_the_tarball_ships():
    """A newly shipped file that the gate does not watch is a hole in the gate.

    The shipped set is declared by the package itself: `package.json`'s `files`, and the sources
    `scripts/copy-hook.mjs` copies in at pack time. The gate watches a list of its own, so the
    two are compared here — otherwise a file added to the tarball would be invisible to the
    gate, and the gate would report "not behind the repository" while the installer on npm was
    exactly that.
    """
    watched = set(SHIPPED_SOURCES)
    assert watched, "the gate declares no shipped sources"

    copied = _copied_sources()
    assert copied, "copy-hook.mjs no longer declares its sources in a readable form"
    for source in sorted(copied):
        assert _covers(watched, source), (
            f"copy-hook.mjs copies {source!r} into the tarball, but the drift gate does not watch "
            f"it: {sorted(watched)}"
        )

    package = _read_json(REPO / SETUP_PATH / "package.json")
    copied_names = {source.rstrip("/").split("/")[-1] for source in copied}
    for entry in package["files"]:
        if _covers(watched, f"{SETUP_PATH}/{entry}"):
            continue
        name = entry.rstrip("/").split("/")[-1]
        assert name in copied_names, (
            f"package.json ships {entry!r}, but the drift gate watches neither it nor a source it "
            f"is copied from: {sorted(watched)}"
        )


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **(env or {})},
    ).stdout


def _synthetic_repo(root: Path) -> Path:
    """A repository that looks like the setup package: the shipped files and a release tag."""
    repo = root / "repo"
    (repo / SETUP_PATH / "bin").mkdir(parents=True)
    (repo / SETUP_PATH / "bin" / "misakanet-setup.mjs").write_text("// installer v1\n", encoding="utf-8")
    (repo / SETUP_PATH / "README.md").write_text("# setup\n", encoding="utf-8")
    (repo / SETUP_PATH / "package.json").write_text(
        json.dumps({"name": NPM_PACKAGE, "version": "0.5.6"}) + "\n", encoding="utf-8"
    )
    (repo / "integrations" / "agent-autostart").mkdir(parents=True)
    (repo / "integrations" / "agent-autostart" / "checkpoint_reminder.mjs").write_text("// hook\n", encoding="utf-8")
    (repo / "integrations" / "agent-autostart" / "voice_hook.mjs").write_text("// voice\n", encoding="utf-8")
    (repo / "docs" / "assets" / "voice").mkdir(parents=True)
    (repo / "docs" / "assets" / "voice" / "cue.mp3").write_bytes(b"\x00")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat(setup): the installer")
    _git(repo, "tag", f"{TAG_PREFIX}0.5.6")
    return repo


def _move_the_source(repo: Path, when: str) -> None:
    """A change to the shipped source, dated — the drift the gate is looking for."""
    (repo / SETUP_PATH / "bin" / "misakanet-setup.mjs").write_text("// installer v2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-qm",
        "fix(setup): the installer changed",
        env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
    )


def test_the_gate_is_red_when_the_source_moved_and_no_release_happened(tmp_path):
    """The state #3691 describes: the source moved, the release did not, the registry is behind.

    This is the case `--verify` cannot see, because npm's latest *is* the published version —
    the gap is between the registry and the repository.
    """
    repo = _synthetic_repo(tmp_path)
    _move_the_source(repo, "2026-09-20T00:00:00+00:00")
    report = assess(repo, published=["0.5.6"], now=_now("2026-10-22T00:00:00+00:00"))
    assert report.status == "drift", (
        f"the gate did not go red on a source that moved with no release:\n{report.lines}"
    )
    assert any("a release is overdue" in problem for problem in report.problems), report.problems
    assert any(f"{TAG_PREFIX}0.5.6" in line for line in report.lines), report.lines
    assert any("bin/misakanet-setup.mjs" in line for line in report.lines), (
        f"the gate must name the file that moved:\n{report.lines}"
    )


def test_the_gate_is_green_when_the_published_package_matches_the_repository(tmp_path):
    """The steady state: the tag, the registry and the source agree."""
    repo = _synthetic_repo(tmp_path)
    report = assess(repo, published=["0.5.6"], now=_now("2026-10-22T00:00:00+00:00"))
    assert report.status == "ok", f"the gate went red on a repository that is in sync:\n{report.lines}"
    assert report.exit_code == 0


def test_the_gate_is_red_when_a_release_never_reached_npm(tmp_path):
    """A tag with no published version is a release that never happened."""
    repo = _synthetic_repo(tmp_path)
    report = assess(repo, published=["0.5.5"], now=_now("2026-10-22T00:00:00+00:00"))
    assert report.status == "drift", (
        f"the gate did not go red on a release that never reached npm:\n{report.lines}"
    )
    assert any("never reached the registry" in problem for problem in report.problems), report.problems


def test_the_gate_waits_out_the_grace_period(tmp_path):
    """A change that landed today is not drift yet.

    release-please bumps the version *after* the change lands, so "the source is ahead of the
    last release" is true for a few days by design. A gate that called that drift would block
    every pull request that touches the package.
    """
    repo = _synthetic_repo(tmp_path)
    _move_the_source(repo, "2026-10-21T00:00:00+00:00")
    report = assess(repo, published=["0.5.6"], now=_now("2026-10-22T00:00:00+00:00"))
    assert report.status == "ok", f"the gate called a one-day-old change drift:\n{report.lines}"
    assert any("grace days used" in line for line in report.lines), report.lines


def test_the_gate_says_it_could_not_answer_when_npm_is_unreachable(tmp_path, monkeypatch):
    """Unreachable is not the same as wrong, and the two must not be reported as one.

    `registry-drift-watch.yml` draws the same line: a check that cannot answer must not answer
    "wrong" — it fails the run for a different reason, and says which one.
    """
    import setup_release_drift as drift  # noqa: PLC0415 - the module under test, mutated here

    def unreachable(*args, **kwargs):
        raise OSError("registry.npmjs.org is unreachable")

    monkeypatch.setattr(drift, "published_versions", unreachable)
    repo = _synthetic_repo(tmp_path)
    report = drift.assess(repo, now=_now("2026-10-22T00:00:00+00:00"))
    assert report.status == "unknown", (
        f"an unreadable registry must be 'could not answer', not a verdict:\n{report.lines}"
    )
    assert report.exit_code == 2, "an unanswered question must not read as a verdict"
    assert any("could not ask npm" in problem for problem in report.problems), report.problems


def _now(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def _bump_the_version(repo: Path, version: str, when: str) -> None:
    """The commit release-please makes: the package declares a version that has no tag yet."""
    package = repo / SETUP_PATH / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    data["version"] = version
    package.write_text(json.dumps(data) + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-qm",
        "chore(setup): release 0.5.7",
        env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
    )


def test_the_gate_waits_for_a_release_that_is_in_flight(tmp_path):
    """A declared version with no tag yet is a release on its way, not drift.

    release-please bumps the version in a release pull request, and the tag and the publish
    follow the merge. A gate that called that state drift would be red on the release pull
    request itself — the very pull request that fixes the drift.
    """
    repo = _synthetic_repo(tmp_path)
    _move_the_source(repo, "2026-09-20T00:00:00+00:00")
    _bump_the_version(repo, "0.5.7", "2026-10-22T00:00:00+00:00")
    report = assess(repo, published=["0.5.6"], now=_now("2026-10-22T06:00:00+00:00"))
    assert report.status == "ok", f"the gate called a release in flight drift:\n{report.lines}"
    assert any("a release is cut" in line for line in report.lines), report.lines


def test_the_gate_is_red_when_a_cut_release_never_got_a_tag(tmp_path):
    """A release cut days ago and still untagged is the publish path being broken."""
    repo = _synthetic_repo(tmp_path)
    _move_the_source(repo, "2026-09-20T00:00:00+00:00")
    _bump_the_version(repo, "0.5.7", "2026-09-20T00:00:00+00:00")
    report = assess(repo, published=["0.5.6"], now=_now("2026-10-22T00:00:00+00:00"))
    assert report.status == "drift", (
        f"the gate did not go red on a release that was cut and never published:\n{report.lines}"
    )
    assert any("publish path is broken" in problem for problem in report.problems), report.problems


def test_the_gate_reads_the_repository_it_is_pointed_at(tmp_path):
    """The gate measures a repository, not a hard-coded story about one.

    The tags and the published versions are read from the repository and the registry; nothing
    about *this* repository's history is baked into the module.
    """
    repo = _synthetic_repo(tmp_path)
    tags = released_tags(repo)
    assert [tag for _, _, tag in tags] == [f"{TAG_PREFIX}0.5.6"]
    assert version_key("0.5.6") == (0, 5, 6)
    assert version_key("not a version") is None
    assert published_versions(injected=["0.5.6"]) == ["0.5.6"]
