#!/usr/bin/env python3
"""Every path a `Makefile` recipe names has to resolve to something that exists.

The Makefile carried the same two dead references that #2150 fixed in `package.json`, and for the
same reason nothing noticed: no test read the Makefile at all.

* `deploy-web` ran `cd web && npx wrangler deploy`. `web/` is not a directory that never existed — it
  was **deleted on 2026-08-31 by 739cae4d9** ("slim repo — … drop web/ shell"), and the target was
  left behind as residue. The site worker is configured by the **root** `wrangler.jsonc`
  (`name: misakanet-web`, `assets.directory: docs`) and is deployed by Cloudflare Workers Builds, not
  by this Makefile.
* `deploy-api` ran `cd workers && npx wrangler deploy --config wrangler.api.jsonc`, and
  `workers/wrangler.api.jsonc` is not in this repository. The file CI deploys is
  `workers/wrangler.toml` (`.github/workflows/deploy-worker.yml`).

**`make -n deploy` was never a gate for this.** It exits 0 on the broken Makefile too: `-n` prints the
recipe without running it, so `cd web` is never executed and its failure is never observed. The check
has to resolve the paths itself. That is what this file does, and the test below proves it is not
vacuous by running the same checker over the pre-fix Makefile, which is checked in as
`tests/fixtures/makefile-before-deploy-paths.txt`, and requiring it to report both references.

That control used to shell out to `git show origin/main:Makefile`, which was wrong twice over, and both
were measured on 2026-10-02 after an independent review of this change: once this fix merges, the
Makefile on `origin/main` **is** the fixed one, so the control would fail on `main` itself
(`2 failed` when simulating post-merge main); and on a checkout without an `origin/main` ref it
**skipped**, so the control that proves the checker is not vacuous never ran in the CI that needs it
(`7 passed, 2 skipped` when the ref was removed). A frozen fixture is enforced in both places.

The rules are pure functions over parsed input so the fixtures below can prove each one fires, and the
`cd` / `--config` extractors are imported from `tests/test_npm_scripts_resolve.py` — the npm-side gate
#2150 added for this same class of bug — so the two cannot drift into disagreeing about what the shell
would resolve.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from test_npm_scripts_resolve import cd_targets, config_targets

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"


# ── parsing ──────────────────────────────────────────────────────────────────────────────────────

def recipe_lines(text: str) -> list[tuple[int, str]]:
    """Every real recipe line in a Makefile, as `(1-based line number, command)`.

    A recipe line is one that starts with a **tab**; that is Make's rule, and it is also what keeps
    comment lines and variables out. Blank recipe lines are dropped.
    """
    out: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.startswith("\t"):
            continue
        command = raw.strip()
        if command and not command.startswith("#"):
            out.append((number, command))
    return out


def recipe_problems(lines: list[tuple[int, str]], root: Path) -> list[str]:
    """References in recipe lines that do not resolve, as human-readable strings.

    The working directory is reset to the repository root **at the start of every recipe line**, not
    carried over from the previous one: each recipe line is its own shell, so a `cd` on one line does
    not move the next. Within a single line the last `cd` wins, which is where a relative `--config`
    is resolved from — the same rule `test_npm_scripts_resolve.py` applies to npm scripts.
    """
    problems: list[str] = []
    for number, command in lines:
        cds = cd_targets(command)
        for directory in cds:
            if not (root / directory).is_dir():
                problems.append(f"Makefile:{number}: `cd {directory}` — no such directory in the repository")
        for config in config_targets(command):
            base = root / cds[-1] if cds else root
            if not (base / config).is_file():
                problems.append(
                    f"Makefile:{number}: `--config {config}` — no such file"
                    + (f" (looked in {cds[-1]}/)" if cds else "")
                )
    return problems


def makefile_references(lines: list[tuple[int, str]]) -> list[tuple[str, str]]:
    """The `(kind, value)` of every reference a recipe line makes, in order."""
    refs: list[tuple[str, str]] = []
    for _, command in lines:
        refs += [("cd", directory) for directory in cd_targets(command)]
        refs += [("--config", config) for config in config_targets(command)]
    return refs


def resolve_config(command: str) -> str:
    """The config a deploy recipe resolves to, as a repository-relative path.

    `deploy-api` is written as `cd workers && … --config wrangler.toml`, the same way
    `.github/workflows/deploy-worker.yml` writes it, so comparing raw strings would only pin the
    spelling. This is the path the shell would actually use.
    """
    cds = cd_targets(command)
    configs = config_targets(command)
    assert cds and configs, f"no `cd`/`--config` to resolve in: {command}"
    return (Path(cds[-1]) / configs[-1]).as_posix()


# ── the gate ─────────────────────────────────────────────────────────────────────────────────────

def test_every_makefile_recipe_reference_resolves():
    lines = recipe_lines(MAKEFILE.read_text(encoding="utf-8"))
    assert lines, "the Makefile has no recipe lines — this gate would pass vacuously"
    problems = recipe_problems(lines, REPO)
    assert not problems, "\n  ".join(problems)


def test_the_makefile_actually_names_references_to_check():
    """A Makefile with no `cd`/`--config` would make the gate above vacuous, not green."""
    refs = makefile_references(recipe_lines(MAKEFILE.read_text(encoding="utf-8")))
    kinds = {kind for kind, _ in refs}
    assert refs, "no `cd`/`--config` reference found in the Makefile — the extractors have drifted"
    assert "cd" in kinds, f"the `cd` extractor found nothing; references were {refs}"


def test_the_deploy_targets_point_at_what_ci_deploys():
    """`deploy-api` and CI must not describe two different deployments.

    This is the check that would have caught `--config wrangler.api.jsonc` while
    `.github/workflows/deploy-worker.yml` deployed `wrangler.toml`.
    """
    text = MAKEFILE.read_text(encoding="utf-8")
    recipes = {command for _, command in recipe_lines(text)}
    deploy_api = next((c for c in recipes if "--config" in c), None)
    assert deploy_api, "no recipe names a wrangler config anymore; fix this pin with it"

    workflow = (REPO / ".github" / "workflows" / "deploy-worker.yml").read_text(encoding="utf-8")
    ci_configs = [config for line in workflow.splitlines()
                  if "wrangler deploy" in line for config in config_targets(line)]
    assert ci_configs, "the deploy workflow no longer names a wrangler config; fix this pin with it"
    ci_resolved = sorted({resolve_config(f"cd workers && npx wrangler deploy --config {c}")
                          for c in ci_configs})
    assert resolve_config(deploy_api) in ci_resolved, (
        f"{deploy_api!r} resolves to {resolve_config(deploy_api)}, CI deploys {ci_resolved}")


# ── positive control: the checker fails on the Makefile that shipped the bug ─────────────────────

FIXTURE = REPO / "tests" / "fixtures" / "makefile-before-deploy-paths.txt"


def _shipped_makefile() -> str:
    """The pre-fix Makefile, frozen in the repository.

    Deliberately **not** `git show origin/main:Makefile`: after this fix merges, that ref holds the
    corrected file and the control below would fail on `main`; and where the ref is missing the
    control skipped instead of running. Both failure modes were measured — see the module docstring.
    """
    return FIXTURE.read_text(encoding="utf-8")


def test_the_checker_reports_both_broken_references():
    """This is the positive control: it must FAIL on the Makefile that shipped the bug.

    Measured on 2026-10-02 — the checker reports exactly two problems, the two the Makefile carried
    and the two `make -n deploy` never surfaced (because `-n` prints `cd web` without running it, it
    exits 0 on this Makefile too):

        Makefile:13: `cd web` — no such directory in the repository
        Makefile:10: `--config wrangler.api.jsonc` — no such file (looked in workers/)

    The input is the verbatim pre-fix file, so the control cannot drift away from the bug it claims to
    catch — and unlike a `git show` against a moving ref, it is enforced on every checkout.
    """
    lines = recipe_lines(_shipped_makefile())
    problems = recipe_problems(lines, REPO)
    assert len(problems) == 2, f"expected the two broken references, got: {problems}"
    assert any("`cd web`" in p and "no such directory" in p for p in problems), problems
    assert any("wrangler.api.jsonc" in p and "no such file" in p for p in problems), problems
    # The `--config` is reported against the `cd` on its own line, which is where the shell looks.
    assert any("looked in workers/" in p for p in problems), problems


def test_the_reported_lines_are_the_ones_we_fixed():
    """The fixture puts `cd web` on line 13 and the bad `--config` on line 10 — if that moves, the
    fixture was edited and this control's message is stale, not wrong."""
    refs = {}
    for number, command in recipe_lines(_shipped_makefile()):
        for directory in cd_targets(command):
            refs[("cd", directory)] = number
        for config in config_targets(command):
            refs[("--config", config)] = number
    assert refs.get(("cd", "web")) == 13, refs
    assert refs.get(("--config", "wrangler.api.jsonc")) == 10, refs


# ── fixtures: proof that each rule can go red ────────────────────────────────────────────────────

def test_a_missing_directory_is_flagged(tmp_path):
    (tmp_path / "workers").mkdir()
    assert recipe_problems([(1, "cd workers && npx wrangler deploy")], tmp_path) == []
    problems = recipe_problems([(1, "cd web && npx wrangler deploy")], tmp_path)
    assert len(problems) == 1 and "no such directory" in problems[0], problems


def test_a_missing_config_is_flagged_relative_to_the_cd(tmp_path):
    (tmp_path / "workers").mkdir()
    (tmp_path / "workers" / "wrangler.toml").write_text("", encoding="utf-8")
    assert recipe_problems([(1, "cd workers && npx wrangler deploy --config wrangler.toml")], tmp_path) == []
    problems = recipe_problems([(1, "cd workers && npx wrangler deploy --config wrangler.api.jsonc")], tmp_path)
    assert len(problems) == 1 and "no such file" in problems[0], problems
    assert "workers/" in problems[0], problems


def test_the_working_directory_resets_at_every_recipe_line(tmp_path):
    """A `cd` on one line must not move the next — that is why the broken `--config` is even visible.

    `workers/` exists and `wrangler.toml` is only inside it. Line 1 enters `workers/`; if that leaked
    into line 2, the bare `wrangler.toml` would resolve inside `workers/` and a broken recipe would
    look correct.
    """
    (tmp_path / "workers").mkdir()
    (tmp_path / "workers" / "wrangler.toml").write_text("", encoding="utf-8")
    lines = [(1, "cd workers && npx wrangler deploy"), (2, "npx wrangler deploy --config wrangler.toml")]
    problems = recipe_problems(lines, tmp_path)
    assert len(problems) == 1 and "Makefile:2" in problems[0], problems


def test_recipe_lines_are_tab_prefixed_only():
    """Comments and variables are not recipes, so they can never contribute a reference."""
    text = "# cd web  <- a comment about the old target\nDEPLOY := cd web\n\nall:\n\tcd workers\n"
    assert recipe_lines(text) == [(5, "cd workers")]


if __name__ == "__main__":  # pragma: no cover - convenience for local runs
    raise SystemExit(pytest.main([__file__, "-q"]))
