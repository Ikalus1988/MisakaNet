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
