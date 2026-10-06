#!/usr/bin/env python3
"""`exclude-paths` is a prefix list, not a glob list — so a glob in it is dead config.

Found while fixing #2894 (2026-10-06)
-------------------------------------
`release-please-config.json` was going to grow

    "exclude-paths": ["docs/maintainer/**"]

so that a handoff-document PR would stop opening a release PR (#2887 was 2.41.4, one handoff file).
That value is the natural thing to write and it does **nothing at all**. Measured, not assumed:
release-please's matcher (`src/util/commit-exclude.ts`) is

    isRelevant(file, path)  ->  path === '.' || file.indexOf(`${path}/`) === 0

and `normalizePaths` (`src/util/commit-utils.ts`) only strips leading/trailing slashes — it never
touches `*`. The entry is therefore compared against the literal prefix `docs/maintainer/**/`, which
no real path begins with, and every handoff commit keeps counting toward the bump. The config would
have read as correct in review while changing nothing.

What this checks
----------------
1. **No glob characters in `exclude-paths`.** Provably dead, as above. This is the assertion that
   catches the regression at the moment someone edits the config.
2. **The configured entries actually exclude a handoff-only commit** — read from the real config, so
   a wrong-but-plausible edit fails here too.
3. **They do not over-reach**: a commit that also changes code still counts, and a sibling directory
   sharing a name prefix is not swept in.
4. **The matcher below is faithful.** Asserted against release-please's own unit tests
   (`test/util/commit-exclude.ts`) before being trusted to prove anything about our config — a port
   that drifts would otherwise pass every assertion here by agreeing with itself.

The git history is deliberately not consulted: `fetch-depth` differs between runners and a local
shallow clone, and a gate that quietly stops testing anything is worse than no gate. The value under
test comes from the real config; the inputs are representative file lists.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG = REPO_ROOT / "release-please-config.json"

ROOT_PROJECT_PATH = "."

# ── port of googleapis/release-please @ main ──────────────────────────────────────────────────────
# src/util/commit-utils.ts   -> normalize_paths
# src/util/commit-exclude.ts -> is_relevant / _should_include


def normalize_paths(paths: list[str]) -> list[str]:
    """release-please strips one leading and one trailing slash — and nothing else.

    Written as repeated single-character removal because that is literally what the JS does
    (`replace(/^\\//, '')`), and the point of this file is to be a faithful copy.
    """
    out: list[str] = []
    for path in paths:
        new = path[:-1] if path.endswith("/") else path
        new = new[1:] if new.startswith("/") else new
        new = new + "/"
        new = "/" + new
        new = new[:-1] if new.endswith("/") else new
        new = new[1:] if new.startswith("/") else new
        out.append(new)
    return out


def is_relevant(file: str, path: str) -> bool:
    return path == ROOT_PROJECT_PATH or file.startswith(f"{path}/")


def _should_include(commit_files: list[str], exclude_paths: list[str], package_path: str) -> bool:
    """A commit is excluded only when *every* file relevant to the package is excluded."""
    relevant = [f for f in commit_files if is_relevant(f, package_path)]
    return not all(any(is_relevant(f, p) for p in exclude_paths) for f in relevant)


def configured_exclude_paths() -> list[str]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    return normalize_paths(config["packages"]["."].get("exclude-paths", []))


# ── 1. the port matches release-please's own tests ───────────────────────────────────────────────
# Fixture and expectations transcribed from test/util/commit-exclude.ts.

_COMMITS_PER_PATH = {
    ".": [
        {"sha": "pack1Pack2", "files": ["pkg1/foo.txt", "pkg2/bar.txt"]},
        {"sha": "rootCommit", "files": ["foo.txt"]},
        {"sha": "pack3", "files": ["pkg3/bar/foo.txt"]},
    ],
    "pkg1": [{"sha": "pack1Pack2", "files": ["pkg1/foo.txt", "pkg2/bar.txt"]}],
    "pkg2": [{"sha": "pack1Pack2", "files": ["pkg1/foo.txt", "pkg2/bar.txt"]}],
    "pkg3": [
        {"sha": "pack3", "files": ["pkg3/foo.txt"]},
        {"sha": "pack3sub", "files": ["pkg3/bar/foo.txt"]},
    ],
}


def _exclude(config: dict[str, list[str]], commits: dict) -> dict[str, list]:
    out = {}
    for path, items in commits.items():
        paths = config.get(path)
        if paths is None:
            out[path] = list(items)
            continue
        out[path] = [c for c in items if _should_include(c["files"], paths, path)]
    return out


def test_port_empty_config_excludes_nothing():
    """upstream: 'should not exclude anything if paths are empty' -> 3/1/1/2."""
    result = _exclude({}, _COMMITS_PER_PATH)
    assert (len(result["."]), len(result["pkg1"]), len(result["pkg2"]), len(result["pkg3"])) \
        == (3, 1, 1, 2)


def test_port_excludes_only_all_file_commits():
    """upstream: config {'.': ['pkg3','pkg1'], 'pkg3': ['pkg3/bar']} -> 2/1/1/1."""
    result = _exclude({".": ["pkg3", "pkg1"], "pkg3": ["pkg3/bar"]}, _COMMITS_PER_PATH)
    assert (len(result["."]), len(result["pkg1"]), len(result["pkg2"]), len(result["pkg3"])) \
        == (2, 1, 1, 1)


def test_port_excludes_when_all_files_are_excluded():
    """upstream: config {'.': ['pkg3','pkg1','pkg2']} -> 1/1/1/2."""
    result = _exclude({".": ["pkg3", "pkg1", "pkg2"]}, _COMMITS_PER_PATH)
    assert (len(result["."]), len(result["pkg1"]), len(result["pkg2"]), len(result["pkg3"])) \
        == (1, 1, 1, 2)


def test_port_decides_only_on_files_relevant_to_the_package():
    """upstream: 'should make decision only on relevant files' -> a keeps 1, d keeps 0.

    The commit touches a/ and d/; under package `d` only the d/ files are weighed.
    """
    shared = {"files": ["a/b/c", "d/e/f", "d/e/g"]}
    result = _exclude({"d": ["d/e"]}, {"a": [shared], "d": [dict(shared)]})
    assert len(result["a"]) == 1
    assert len(result["d"]) == 0


# ── 2. our own config ────────────────────────────────────────────────────────────────────────────

def test_exclude_paths_contains_no_glob_characters():
    """The whole point: release-please matches by literal prefix, so `*`/`?` match nothing."""
    globs = [p for p in configured_exclude_paths() if "*" in p or "?" in p]
    assert not globs, (
        f"release-please excludes by literal prefix (`file.indexOf(path + '/') === 0`), not by "
        f"glob, so {globs} can never match a path and silently excludes nothing. Use a plain "
        f"directory — e.g. 'docs/maintainer', with no '/**'."
    )


def test_a_handoff_only_commit_is_excluded():
    """a7cc6f24 touched exactly this file list and opened the 2.41.4 release PR (#2887)."""
    paths = configured_exclude_paths()
    assert paths, "no exclude-paths configured — a handoff PR will open a release PR again"
    handoff_only = ["docs/maintainer/handoff-2026-10-05.md"]
    assert not _should_include(handoff_only, paths, "."), (
        f"these exclude-paths do not exclude a handoff-only commit: {paths}"
    )


def test_a_handoff_pr_that_also_changes_code_still_releases():
    # A real handoff path, not a plausible-looking one: `tests/test_handoff_citations_resolve.py`
    # fails on any `docs/maintainer/handoff-*.md` this file names that was never committed, and it
    # is right to — an unverifiable path in a test is the same defect it exists to catch.
    mixed = ["docs/maintainer/handoff-2026-10-05.md", "scripts/benchmark_workers_ai.py"]
    assert _should_include(mixed, configured_exclude_paths(), "."), (
        "a real code change was excluded — exclude-paths must drop only all-doc commits"
    )


def test_a_sibling_directory_sharing_a_prefix_is_not_swept_in():
    """The matcher compares `path + '/'`, so a bare prefix cannot match a longer sibling name."""
    assert _should_include(["docs/maintainer-notes/notes.md"], configured_exclude_paths(), ".")


def test_other_docs_still_count_toward_the_changelog():
    paths = configured_exclude_paths()
    for files in (["docs/lessons/a.md"], ["docs/data/feed.json"], ["docs/benchmarks/latest.json"]):
        assert _should_include(files, paths, "."), f"{files} was excluded but is not a handoff doc"
