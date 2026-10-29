#!/usr/bin/env python3
"""`scripts/release_tags.py` — the step between "release PR merged" and "tag exists" (#4031).

The gap it closes is silent in both directions: a merged release with no tag publishes nothing (the
workflow listening for the tag simply never fires), and release-please simultaneously reads it as
outstanding and re-proposes the same commit range — which is how a duplicate 0.3.3 PR appeared while
0.3.2 was untagged.

The tests pin the two things a wrong implementation would get away with for a release or two: the tag
spelling, and "no publish workflow" being reported rather than guessed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import release_tags  # noqa: E402


def write_repo(tmp_path, manifest, packages, tags=()):
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "release-please-config.json").write_text(
        json.dumps({"packages": packages}), encoding="utf-8")
    (tmp_path / ".release-please-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for tag in tags:
        subprocess_tag(tmp_path, tag)
    return tmp_path


def subprocess_tag(repo: Path, tag: str) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "x"], cwd=repo, check=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@e", "PATH": "/usr/bin:/bin"})
    subprocess.run(["git", "tag", tag], cwd=repo, check=True)


def test_the_tag_spelling_matches_release_please():
    block = {"component": "fatal-guard", "tag-separator": "-", "include-component-in-tag": True}
    assert release_tags.tag_for(block, "0.3.2") == "fatal-guard-v0.3.2"


def test_a_different_separator_is_respected():
    """The separator is configuration, not a constant — `misakanet-setup` uses the same `-`, but a
    package that chose another separator must not get a tag release-please never creates."""
    block = {"component": "setup", "tag-separator": "_"}
    assert release_tags.tag_for(block, "1.0.0") == "setup_v1.0.0"


def test_a_merged_untagged_release_is_reported(tmp_path, monkeypatch):
    repo = write_repo(
        tmp_path,
        manifest={".": "2.50.1", "packages/x": "1.2.3"},
        packages={".": {"release-type": "python"},
                  "packages/x": {"component": "x", "tag-separator": "-"}},
    )
    monkeypatch.setattr(release_tags, "REPO", repo)
    monkeypatch.setattr(release_tags, "CONFIG", repo / "release-please-config.json")
    monkeypatch.setattr(release_tags, "MANIFEST", repo / ".release-please-manifest.json")
    monkeypatch.setattr(release_tags, "WORKFLOWS", repo / ".github" / "workflows")
    rows = release_tags.pending(repo)
    assert [r["tag"] for r in rows] == ["x-v1.2.3"]
    assert rows[0]["workflow"] == "", "no x-publish.yml exists, and the script must not invent one"


def test_the_root_package_is_left_to_its_own_step(tmp_path, monkeypatch):
    """The root release has its own tag step with rules the packages do not share (the moving `v1`
    alias, the onboarding footer). Reporting it here would tag it twice."""
    repo = write_repo(
        tmp_path,
        manifest={".": "2.50.1"},
        packages={".": {"release-type": "python"}},
    )
    monkeypatch.setattr(release_tags, "REPO", repo)
    monkeypatch.setattr(release_tags, "CONFIG", repo / "release-please-config.json")
    monkeypatch.setattr(release_tags, "MANIFEST", repo / ".release-please-manifest.json")
    monkeypatch.setattr(release_tags, "WORKFLOWS", repo / ".github" / "workflows")
    assert release_tags.pending(repo) == []


def test_the_publish_workflow_is_named_when_it_exists(tmp_path, monkeypatch):
    repo = write_repo(
        tmp_path,
        manifest={"packages/fatal-guard": "0.3.2"},
        packages={"packages/fatal-guard": {"component": "fatal-guard", "tag-separator": "-"}},
    )
    (repo / ".github" / "workflows" / "fatal-guard-publish.yml").write_text("name: x\n", encoding="utf-8")
    monkeypatch.setattr(release_tags, "REPO", repo)
    monkeypatch.setattr(release_tags, "CONFIG", repo / "release-please-config.json")
    monkeypatch.setattr(release_tags, "MANIFEST", repo / ".release-please-manifest.json")
    monkeypatch.setattr(release_tags, "WORKFLOWS", repo / ".github" / "workflows")
    rows = release_tags.pending(repo)
    assert rows and rows[0]["workflow"] == "fatal-guard-publish.yml"
