#!/usr/bin/env python3
"""The two configuration files that describe *other* files, checked against the tree.

Both defects this pins were silent:

* `.github/dependabot.yml` tracked `directory: "/web"` — a "Cloudflare Pages frontend" that does not
  exist in this repository (`deploy:web` pointed at it until #2150 deleted the two dead deploy scripts).
  Dependabot reports nothing for a directory it cannot find, so the entry cost a weekly fetch of a
  missing `package.json` and produced no PR anyone could notice the absence of. Found 2026-09-28 while
  grouping the ecosystems.
* There was no `.gitattributes` at all, so `data/lessons.json` (1.26 MB, rewritten in full by
  `scripts/update_lessons_json.py`) and `docs/**`'s 470 generated pages appeared as ordinary diffs. The
  repository already knows which files are generated — `data/README.md` names a generator for each, and
  `docs/.generated-pages.json` is the page generator's own manifest — but nothing said so to GitHub.

Both rules are checked in the direction that catches rot: a path or directory that does not exist is an
error, and the artifacts the repository's own documentation calls generated must be marked.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the dependabot config")

REPO = Path(__file__).resolve().parent.parent
DEPENDABOT = REPO / ".github" / "dependabot.yml"
WORKFLOWS = REPO / ".github" / "workflows"
ATTRIBUTES = REPO / ".gitattributes"

# The artifacts `data/README.md` and `docs/.generated-pages.json` describe as generated, and which a
# reader would otherwise scroll past in a diff. Not the whole list — the file may mark more — but these
# three must be in it: the largest, the most frequently rewritten, and the manifest itself.
MUST_BE_MARKED = ("data/lessons.json", "docs/sitemap.xml", "docs/.generated-pages.json")


def tracked_paths() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.split()


# ── dependabot.yml ───────────────────────────────────────────────────────────────────────────────

def _config() -> dict:
    """The dependabot config, with duplicate keys refused.

    PyYAML keeps the last of a duplicated key, so `directory: "/web"` added below an existing
    `directory: "/"` in the same entry would be silently *ignored* — which is how the first version of
    the directory test stayed green under exactly that mutation.
    """
    class StrictLoader(yaml.SafeLoader):
        pass

    def no_duplicates(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            assert key not in mapping, f"duplicate key {key!r} in {DEPENDABOT.name}"
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_duplicates)
    return yaml.load(DEPENDABOT.read_text(encoding="utf-8"), Loader=StrictLoader)


def test_every_dependabot_directory_exists():
    config = _config()
    updates = config["updates"]
    assert updates, "dependabot.yml lists no ecosystems — the file exists to list them"
    missing = [entry["directory"] for entry in updates
               if not (REPO / entry["directory"].lstrip("/")).is_dir()]
    assert missing == [], (
        f"dependabot.yml watches {missing}, which are not directories in this repository. Dependabot "
        "reports nothing for a directory it cannot find, so a stale entry is an update path that has "
        "been dead for as long as nobody looked (`/web` was one of these)."
    )


def test_every_ecosystem_is_grouped():
    """One PR per ecosystem per week instead of one per dependency — the reason this file was edited."""
    config = _config()
    ungrouped = [entry["package-ecosystem"] for entry in config["updates"] if not entry.get("groups")]
    assert ungrouped == [], (
        f"these ecosystems have no `groups` block: {ungrouped}. Without one, a weekly bump of five "
        "actions is five PRs, which is how five open dependabot PRs accumulated on 2026-09-28."
    )
    for entry in config["updates"]:
        patterns = [p for group in entry["groups"].values() for p in group["patterns"]]
        assert patterns, f"{entry['package-ecosystem']}: a group with no patterns matches nothing"


def test_the_auto_merge_channels_cannot_swallow_a_dependency_bump():
    """The policy is enforced where it would actually break, not by the sentence that states it.

    A dependabot github-actions bump edits `.github/workflows/**` — the deploy path and the
    credential-bearing surface of this repository — and a pip/npm bump edits `requirements*.txt` /
    `package.json`. Neither may ride an existing auto-merge channel:

    * `auto-merge-docs.yml` merges only `docs/**` plus four root markdown files. Widening its allowlist
      to include `.github/` or `workers/` (or `package.json`, or `requirements.txt`) would silently make
      dependency bumps unread;
    * `auto-merge-lessons.yml` merges only PRs carrying the `auto-merge-lesson` label.

    The first version of this test looked for the phrase "never auto-merge" in the dependabot config and
    passed with the policy deleted, because the comment *quoted* that phrase while explaining it — a rule
    satisfied by the prose describing the defect, which this repository has now made six times.
    """
    docs_gate = (WORKFLOWS / "auto-merge-docs.yml").read_text(encoding="utf-8")
    allowlist = re.search(r"const isDocsFile = \(path\) =>(.*?);\n", docs_gate, re.S)
    assert allowlist, "auto-merge-docs.yml no longer defines `isDocsFile` in the shape this test reads"
    body = allowlist.group(1)
    for forbidden in (".github/", "workers/", "requirements", "package.json"):
        assert forbidden not in body, (
            f"`auto-merge-docs.yml`'s docs-only allowlist now mentions {forbidden!r} — that is the "
            "surface a dependency bump edits, and merging one without a reader is what the undependabot "
            "policy in .github/dependabot.yml exists to prevent"
        )
    assert "'docs/'" in body or "docs/" in body, (
        "the allowlist no longer checks for `docs/` at all — if this gate was rewritten, re-derive what "
        "it can merge and update this test with the answer"
    )
    lessons_gate = (WORKFLOWS / "auto-merge-lessons.yml").read_text(encoding="utf-8")
    assert "auto-merge-lesson" in lessons_gate, (
        "auto-merge-lessons.yml no longer requires its opt-in label — then nothing distinguishes a "
        "lesson PR from a dependency bump there either"
    )


# ── .gitattributes ───────────────────────────────────────────────────────────────────────────────

def marked_patterns() -> list[str]:
    lines = [line.split("#")[0].strip() for line in ATTRIBUTES.read_text(encoding="utf-8").splitlines()]
    return [line.split()[0] for line in lines if line and "linguist-generated=true" in line]


def test_the_files_the_repository_calls_generated_are_marked():
    marked = marked_patterns()
    unmarked = [path for path in MUST_BE_MARKED
                if not any(fnmatch.fnmatch(path, pattern) for pattern in marked)]
    assert unmarked == [], (
        f"these generated artifacts are not marked `linguist-generated` in .gitattributes: {unmarked}. "
        "data/README.md names a generator for each of them, so a diff of one is not a review target."
    )


def test_every_marked_path_matches_something_in_the_tree():
    """A rule about a file that does not exist is a rule that cannot fail."""
    tracked = tracked_paths()
    dead = [pattern for pattern in marked_patterns()
            if not any(fnmatch.fnmatch(path, pattern) for path in tracked)
            and not (REPO / pattern.rstrip("*").rstrip("/")).exists()]
    assert dead == [], (
        f".gitattributes marks {dead}, which match no tracked file. A stale path here is the same "
        "defect as a dependabot directory that does not exist, one file over."
    )


def test_nothing_is_marked_as_not_generated():
    """`linguist-generated=false` on a generated file would be worse than silence: it claims a review
    happened."""
    text = ATTRIBUTES.read_text(encoding="utf-8")
    assert "linguist-generated=false" not in text, (
        ".gitattributes asserts a file is hand-written; if that is deliberate, say so in the file's "
        "comment and update this test, because the default is silence rather than a claim"
    )
