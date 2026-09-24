#!/usr/bin/env python3
"""Every reference in `package.json`'s scripts has to resolve to something that exists.

Two of them did not, and nothing noticed for as long as they had been wrong:

* `deploy:web` ran `cd web && npx wrangler deploy` and there is no `web/` directory — the site worker is
  configured by the **root** `wrangler.jsonc` (`name: misakanet-web`, `assets.directory: docs`);
* `deploy:api` ran `cd workers && npx wrangler deploy --config wrangler.api.jsonc` and
  `workers/wrangler.api.jsonc` is not in this repository. The file CI deploys is `workers/wrangler.toml`.

A broken script is not a harmless one: `npm run deploy:all` fails at the first step, and the name that
no longer exists (`wrangler.api.jsonc`, worker `misakanet-api`) is the likeliest origin of the orphan
Cloudflare worker the 2026-09-24 zone audit found — a config deleted from git does not undeploy what it
already published.

The rules are pure functions over parsed input so the fixtures below can prove each one fires.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "package.json"

# `npm run x` / `npm run-script x` / `yarn x`? Only the form this repository uses.
NPM_RUN = re.compile(r"\bnpm run ([\w:.-]+)")
# `cd dir && …` — the directory has to exist for the rest of the command to mean anything.
CD = re.compile(r"(?:^|&&|;)\s*cd\s+([^\s&;]+)")
# `--config <path>`, resolved relative to the script's own `cd`.
CONFIG = re.compile(r"--config[= ]([^\s]+)")


def script_problems(scripts: dict[str, str], root: Path) -> list[str]:
    problems: list[str] = []
    names = set(scripts)
    for name, command in scripts.items():
        for referenced in NPM_RUN.findall(command):
            if referenced not in names:
                problems.append(f"{name}: runs `npm run {referenced}`, which is not a script in package.json")
        cds = CD.findall(command)
        for directory in cds:
            if not (root / directory).is_dir():
                problems.append(f"{name}: `cd {directory}` — no such directory in the repository")
        for config in CONFIG.findall(command):
            # Resolve relative to the last `cd` in the same command, which is how the shell does it.
            base = root / cds[-1] if cds else root
            if not (base / config).is_file():
                problems.append(
                    f"{name}: `--config {config}` — no such file"
                    + (f" (looked in {base.relative_to(root)}/)" if cds else "")
                )
    return problems


def config_discovery(filenames: list[str]) -> list[str]:
    """Wrangler config file names, by prefix rather than by exact name.

    `wrangler.api.jsonc` existed once; the exact-name list this repository used for its
    compatibility-date gate (`{wrangler.toml, wrangler.jsonc, wrangler.json}`) would have missed it,
    which is how a config can be deployed and ungated at the same time.
    """
    return sorted(f for f in filenames
                  if f.startswith("wrangler") and f.endswith((".toml", ".jsonc", ".json")))


def test_every_script_reference_resolves():
    scripts = json.loads(PACKAGE.read_text(encoding="utf-8")).get("scripts") or {}
    assert scripts, "package.json has no scripts — this gate would pass vacuously"
    problems = script_problems(scripts, REPO)
    assert not problems, "\n  ".join(problems)


def resolved_config(command: str) -> str:
    """The config a deploy command resolves to, as a repository-relative path.

    The same command is written two ways — `cd workers && … --config wrangler.toml` here and in CI —
    so comparing the raw strings would only pin the spelling. This is the path the shell would use.
    """
    cds = CD.findall(command)
    configs = CONFIG.findall(command)
    assert cds and configs, f"no `cd`/`--config` to resolve in: {command}"
    return (Path(cds[-1]) / configs[-1]).as_posix()


def test_the_deploy_scripts_point_at_what_ci_deploys():
    """The scripts and the workflow must not describe two different deployments.

    This is the check that would have caught `deploy:api` pointing at `wrangler.api.jsonc` while
    `.github/workflows/deploy-worker.yml` deployed `wrangler.toml`.
    """
    scripts = json.loads(PACKAGE.read_text(encoding="utf-8"))["scripts"]
    workflow = (REPO / ".github" / "workflows" / "deploy-worker.yml").read_text(encoding="utf-8")
    ci_configs = [config for line in workflow.splitlines()
                  if "wrangler deploy" in line for config in CONFIG.findall(line)]
    assert ci_configs, "the deploy workflow no longer names a wrangler config; fix this pin with it"
    ci_resolved = sorted({resolved_config(f"cd workers && npx wrangler deploy --config {c}")
                          for c in ci_configs})
    assert resolved_config(scripts["deploy:api"]) in ci_resolved, (
        f"deploy:api resolves to {resolved_config(scripts['deploy:api'])}, "
        f"CI deploys {ci_resolved}")
    for referenced in NPM_RUN.findall(scripts["deploy:all"]):
        assert referenced in scripts, f"deploy:all runs a script that does not exist: {referenced}"


# ── fixtures: proof that each rule can go red ────────────────────────────────────────────────────

def test_a_missing_script_reference_is_flagged(tmp_path):
    problems = script_problems({"a": "npm run b", "b": "echo hi"}, tmp_path)
    assert problems == [], problems  # b exists → a is fine
    problems = script_problems({"a": "npm run missing"}, tmp_path)
    assert len(problems) == 1 and "not a script" in problems[0], problems


def test_a_missing_directory_is_flagged(tmp_path):
    (tmp_path / "workers").mkdir()
    problems = script_problems({"a": "cd workers && npx wrangler deploy"}, tmp_path)
    assert problems == [], problems
    problems = script_problems({"a": "cd web && npx wrangler deploy"}, tmp_path)
    assert len(problems) == 1 and "no such directory" in problems[0], problems


def test_a_missing_config_is_flagged_relative_to_the_cd(tmp_path):
    (tmp_path / "workers").mkdir()
    (tmp_path / "workers" / "wrangler.toml").write_text("", encoding="utf-8")
    ok = {"a": "cd workers && npx wrangler deploy --config wrangler.toml"}
    assert script_problems(ok, tmp_path) == [], script_problems(ok, tmp_path)
    bad = {"a": "cd workers && npx wrangler deploy --config wrangler.api.jsonc"}
    problems = script_problems(bad, tmp_path)
    assert len(problems) == 1 and "no such file" in problems[0], problems
    # The path is reported relative to the script's own `cd`, which is where the shell would look.
    assert "workers/" in problems[0], problems


def test_a_config_named_wrangler_api_jsonc_is_discovered():
    found = config_discovery(["wrangler.toml", "wrangler.jsonc", "wrangler.api.jsonc",
                              "wrangler.prod.toml", ".pr-agent.toml", "wrangler.toml.bak"])
    assert found == ["wrangler.api.jsonc", "wrangler.jsonc", "wrangler.prod.toml", "wrangler.toml"], found


def test_the_repository_has_configs_for_this_rule_to_find():
    assert config_discovery([p.name for p in REPO.rglob("wrangler*") if p.is_file()]), \
        "no wrangler config discovered — the discovery rule has drifted from the file names"


if __name__ == "__main__":  # pragma: no cover - convenience for local runs
    raise SystemExit(pytest.main([__file__, "-q"]))
