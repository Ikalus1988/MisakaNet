#!/usr/bin/env python3
"""The generated-path split between `main` and `dist`, as two checks that read the same table.

`dist` is not a branch anyone edits. `.github/workflows/publish-dist.yml` rebuilds it on every push
to `main`: it checks `main` out, runs the generators, commits the whole tree on top of `main`'s HEAD
and force-pushes the result. So `dist` is a *function* of `main`, and the paths below are the whole
of the difference it is allowed to have.

Two of these lists are not the same list, and that is the point of the split:

* `MAIN_SIDE` — generated files that **stay on `main`**, because a required check reads them there.
  A required check cannot read a branch it did not check out, so these cannot leave without first
  changing the check. The evidence per path is the table in
  `docs/maintainer/dist-branch-cutover.md`.
* `DIST_ONLY` — generated files that are only ever *served*: the site's generated tree and the two
  corpus copies the browser downloads. Their only readers on `main` are gates that could equally
  read them on `dist`, which is the follow-up's work, not this file's.

`PUBLISHED` is their union: every path a generator owns. The publisher's assertion is about it.

That assertion is also what keeps the publisher's `git add -A` safe. `-A` is needed there (the page
generator creates *and* deletes files), and it stages anything untracked that `.gitignore` does not
cover — including a `node_modules` **symlink**, which `.gitignore`'s `node_modules/` (trailing
slash) matches only when it is a directory. A path like that fails this check before the push
instead of being committed onto `dist`.

Two subcommands, because the two states they run in are different:

    # in publish-dist.yml, after the regeneration is committed and before the push:
    python3 scripts/ci/check_dist_diff.py diff --base "$BASE_SHA"

    # in lesson-gate.yml, after the main-side generators have run over a pull request:
    python3 scripts/ci/check_dist_diff.py main-side
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: Generated paths that leave `main` for `dist`. Grouped by the generator that owns each one,
#: because the question a future edit has to answer is "which generator started writing this", not
#: "is this string in a list".
DIST_ONLY: tuple[str, ...] = (
    # scripts/build_lesson_pages.py — the site's generated tree
    "docs/lessons/**",
    "docs/topics/**",
    "docs/sitemap.xml",
    "docs/_redirects",
    "docs/.generated-pages.json",
    # scripts/update_lessons_json.py — the two copies the browser downloads (the canonical index,
    # `data/lessons.json`, stays on `main` and is in MAIN_SIDE below)
    "docs/data/lessons.json",
    "docs/data/lessons-lite.json",
)

#: Generated paths that stay on `main`, each because a *required* check or a runtime script reads it
#: from `main`'s tree (ruleset 23826057 requires `DCO`, `test (ubuntu-latest, 3.11)`, `gate` and
#: `audit`; the reader of each path is named in the cutover document's classification table).
MAIN_SIDE: tuple[str, ...] = (
    # scripts/update_lessons_json.py — the canonical index; `sync_lesson_count.canonical_count()`
    # reads it, and `tests/test_lesson_count_ssot.py` compares every count surface against it.
    "data/lessons.json",
    # scripts/export_okf.py — a clone-time input (`scripts/build_sag_index.py` builds `data/sag.db`
    # from it) and read by `tests/test_okf_export_freshness.py`.
    "data/okf/lessons.jsonl",
    # scripts/sync_lesson_count.py — the three surfaces that keep a literal count
    # (`tests/test_lesson_count_ssot.py`, `sync_lesson_count.py --check` in the required `audit`
    # job) plus the file `pr-thank-you.yml` reads at runtime.
    "docs/index.html",
    "docs/llms.txt",
    "docs/.well-known/llms.txt",
    "docs/_lessons_count.txt",
    # scripts/rebuild_lessons_index.py — `scripts/lesson_pr_mergeable.py` (the auto-merge gate for
    # lesson pull requests) reads it as the corpus index.
    "lessons/index.md",
    # scripts/gen_ranking_snapshot.py — a pinned expectation, not site output at all:
    # `tests/test_ranking_snapshot.py` compares the live ranking against it.
    "tests/fixtures/ranking-snapshot.json",
)

#: Every path a generator owns. The publisher may differ from `main` in these and nowhere else.
PUBLISHED: tuple[str, ...] = DIST_ONLY + MAIN_SIDE


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    """`fnmatch`'s `*` crosses `/`, so a `**` pattern matches at any depth — which is what these
    globs mean. Compared as written, never expanded against the filesystem, so a pattern that no
    longer matches anything is invisible here; the failure this has to catch (a generator writing a
    path that is not listed at all) still fires."""
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def is_published(path: str) -> bool:
    return _matches(path, PUBLISHED)


def is_main_side(path: str) -> bool:
    return _matches(path, MAIN_SIDE)


# ── `diff`: the publisher, before it pushes ──────────────────────────────────────────────────────

def problems(diff: list[tuple[str, str]]) -> list[str]:
    """Findings for a `git diff --name-status` result, as `(status, path)` pairs.

    `status` is git's letter: `A`dded, `M`odified, `D`eleted, `T`ype change. Renames are read as
    delete + add, which is the conservative reading — the added path is judged on its own.
    """
    found: list[str] = []
    for status, path in diff:
        letter = status[:1]
        if letter == "D":
            found.append(
                f"{path}: deleted — `dist` must contain every path `main` has, so a deletion is a "
                f"404 on the live site that nobody reviewed. The page generator prunes its own "
                f"output on purpose; a deletion outside the published set is not that"
            )
            continue
        if not is_published(path):
            found.append(
                f"{path}: changed ({status}) but no generator owns it — `dist` may differ from "
                f"`main` only in the artifacts the publishers write (see this file's DIST_ONLY and "
                f"MAIN_SIDE)"
            )
    return found


def diff_against(base: str) -> list[tuple[str, str]]:
    """`git diff --name-status` from `base` to HEAD, one `(status, path)` pair per line."""
    raw = _git("diff", "--name-status", "--no-renames", base, "HEAD")
    rows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        rows.append((status.strip(), path.strip()))
    return rows


def run_diff(base: str) -> int:
    try:
        _git("merge-base", "--is-ancestor", base, "HEAD")
    except subprocess.CalledProcessError:
        print(f"FAIL: {base} is not an ancestor of HEAD — `dist` was not built on top of `main`, "
              f"so it is not a superset of it", file=sys.stderr)
        return 1

    try:
        rows = diff_against(base)
    except subprocess.CalledProcessError as exc:
        print(f"FAIL: could not read the diff against {base}: {exc.stderr.strip()}", file=sys.stderr)
        return 1

    found = problems(rows)
    if found:
        print(f"FAIL: {len(found)} path(s) differ from `main` and are not the publishers' output:")
        for item in found:
            print(f"  - {item}")
        return 1

    print(f"OK: {len(rows)} path(s) differ from `{base}`, all of them generated artifacts.")
    return 0


# ── `main-side`: the pull-request gate, after the main-side generators have run ──────────────────

def main_side_dirty(porcelain: str) -> list[str]:
    """The dirty `MAIN_SIDE` paths in a `git status --porcelain` result.

    Deliberately blind to `DIST_ONLY`: after the follow-up deletes those files from `main`, running
    any generator that touches them (both `update_lessons_json.py` and `build_lesson_pages.py` do)
    leaves them dirty in the checkout, and a gate that failed on that would fail every lesson pull
    request for doing the right thing. Their freshness is a required *test*'s business today
    (`tests/test_lesson_page_generator.py`), and the publisher's after the cutover — it regenerates
    them on every push, so they cannot be stale.
    """
    found: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2].strip(), line[3:].strip()
        if " -> " in path:  # a rename shows both sides; the destination is the path that exists
            path = path.split(" -> ", 1)[1].strip()
        path = path.strip('"')
        if is_main_side(path):
            found.append(f"{path} ({status})")
    return found


def run_main_side() -> int:
    found = main_side_dirty(_git("status", "--porcelain"))
    if found:
        print("::error title=Main-side generated files are stale::A lesson was added or changed "
              "without re-running the generators that write the files `main` keeps.")
        print("These files are derived from `lessons/` and this pull request did not carry them:")
        for item in found:
            print(f"  - {item}")
        print("Fix: run `python3 scripts/update_lessons_json.py`, `python3 scripts/export_okf.py`, "
              "`python3 scripts/sync_lesson_count.py` and `python3 scripts/rebuild_lessons_index.py`, "
              "then commit what they wrote. The generated site (`docs/lessons/**`, `docs/topics/**`, "
              "`docs/sitemap.xml`, `docs/_redirects`, `docs/.generated-pages.json`, `docs/data/**`) "
              "is not part of this: `publish-dist.yml` regenerates and publishes it.")
        return 1

    print("OK: every generated file that stays on `main` matches the corpus.")
    return 0


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)

    diff = sub.add_parser("diff", help="assert the `dist` diff against `main` is generated output only")
    diff.add_argument("--base", default="origin/main",
                      help="the commit `dist` was built on top of (default: origin/main)")

    sub.add_parser("main-side", help="assert no generated file that stays on `main` is stale")

    args = parser.parse_args(argv)
    if args.mode == "diff":
        return run_diff(args.base)
    return run_main_side()


if __name__ == "__main__":
    raise SystemExit(main())
