#!/usr/bin/env python3
"""A step that runs a `gh`-shelling script needs a token in scope — or it dies on its first run.

Measured 2026-11-20, and it is the shape this file exists for: `update-lessons.yml` grew a step
"Close any intake whose lesson already exists" that runs `scripts/intake_receipt.py --sweep --apply`.
That script shells out to `gh`, the step declared no `GH_TOKEN`, and the job's `permissions:` did not
grant `issues: write` either. The step therefore failed with

    gh: To use GitHub CLI in a GitHub Actions workflow, set the GH_TOKEN environment variable

on **every** run it ever had — and it is the step that closes "done but open" intakes, which is why 41
of them were still open when the truncation bug in the same sweep was fixed (#5486).

`test_workflow_env_is_used.py` is the other direction (declared but unused). This one is *used but
undeclared*, which static analysis can only see through one hop: the script name appears in the step,
and the script shells out to `gh`. That hop is enough to catch this class, and cheap enough to keep.

Comments are stripped first: a `# NOT build_feed.py` line is a note, not an invocation.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
SCRIPTS = REPO / "scripts"

TOKEN_KEYS = ("GH_TOKEN", "GITHUB_TOKEN")


def gh_scripts(scripts_dir: Path = SCRIPTS) -> set[str]:
    """Every script that invokes `gh` through a subprocess argument list."""
    found = set()
    for path in scripts_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"""\[\s*["']gh["']""", text) or re.search(r"""["']gh["']\s*,?""", text):
            found.add(path.name)
    return found


def strip_comments(script: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in script.splitlines())


def steps(workflows_dir: Path = WORKFLOWS):
    """(workflow file, job id, step, env in scope) for every step that carries a script."""
    for path in sorted(workflows_dir.glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        top = document.get("env") or {}
        for job_id, job in (document.get("jobs") or {}).items():
            job_env = job.get("env") or {}
            for step in job.get("steps") or []:
                run = step.get("run") or ""
                if not run.strip():
                    continue
                yield path.name, job_id, step, {**top, **job_env, **(step.get("env") or {})}


def missing_tokens(workflows_dir: Path = WORKFLOWS, scripts_dir: Path = SCRIPTS) -> list[str]:
    scripts = gh_scripts(scripts_dir)
    missing = []
    for workflow, job_id, step, env in steps(workflows_dir):
        body = strip_comments(step["run"])
        used = sorted(name for name in scripts if name in body)
        if not used:
            continue
        if any(key in env for key in TOKEN_KEYS):
            continue
        label = step.get("name") or body.strip().split("\n")[0][:40]
        missing.append(f"{workflow}:{job_id} → {label} runs {', '.join(used)}")
    return missing


def test_every_step_running_a_gh_script_has_a_token_in_scope():
    assert gh_scripts(), "the detector found no gh-shelling script — it would pass vacuously"
    missing = missing_tokens()
    assert not missing, (
        "these steps run a script that shells out to `gh` but declare no GH_TOKEN: "
        + "; ".join(missing)
    )


def test_the_scan_notices_a_step_that_forgot_the_token(tmp_path):
    """The gate has to fail on the shape it was written for, or it is decoration."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "demo.yml").write_text(
        "name: demo\n"
        "jobs:\n"
        "  j:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: sweep\n"
        "        run: python3 scripts/intake_receipt.py --sweep --apply\n",
        encoding="utf-8",
    )
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "intake_receipt.py").write_text(
        'import subprocess\nsubprocess.run(["gh", "issue", "list"])\n', encoding="utf-8")
    with pytest.raises(AssertionError) as caught:
        missing = missing_tokens(workflows, scripts)
        assert not missing, "; ".join(missing)
    assert "intake_receipt.py" in str(caught.value)


def test_a_comment_is_not_an_invocation(tmp_path):
    """`# NOT build_feed.py` is prose; the name alone must not make the step look like a caller."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "demo.yml").write_text(
        "name: demo\n"
        "jobs:\n"
        "  j:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: regenerate\n"
        "        run: |\n"
        "          # NOT build_feed.py: it changes on every run\n"
        "          python3 scripts/update_lessons_json.py\n",
        encoding="utf-8",
    )
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "build_feed.py").write_text('import subprocess\nsubprocess.run(["gh"])\n', encoding="utf-8")
    assert missing_tokens(workflows, scripts) == []
