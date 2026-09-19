#!/usr/bin/env python3
"""Publish and deploy credentials come from the protected environment, not from repository secrets.

`NPM_TOKEN` and `CLOUDFLARE_API_TOKEN` moved into the `release` environment (2026-09-19). That buys
something only if two things stay true, and neither is visible from the workflow files alone:

* **the jobs that use them declare the environment** — otherwise they read the repository-level secret,
  which any collaborator's edit can exfiltrate without anyone approving anything; and
* **automation that must not wait keeps using the repository secret on purpose** — an approval gate on a
  scheduled cron does not make it safer, it makes it stop. `sync-d1.yml` runs daily at 03:00 to keep the
  served corpus current; putting it behind "required reviewers" would stall the corpus until a person
  noticed a pending run, which is the failure mode this repository keeps finding in its own automation.

So the split is asserted rather than remembered.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflows")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# Guarded credentials: a workflow that reads one of these must either use the environment or be
# justified here.
GUARDED_SECRETS = ("NPM_TOKEN", "CLOUDFLARE_API_TOKEN")
ENVIRONMENT = "release"

# Deliberately NOT behind the environment: scheduled or push-triggered automation, where an approval
# prompt would replace "runs every day" with "runs whenever someone notices".
UNGUARDED_BY_DESIGN = {
    "sync-d1.yml": "scheduled daily (03:00) and on push — an approval gate would stall the corpus sync",
    "sync-question-answers.yml": "scheduled daily (07:20) and on new issues — same reason: a stalled "
                                 "cron is not a safer cron",
}


def _workflows_using(secret: str) -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.yml") if secret in p.read_text(encoding="utf-8"))


def _jobs_with_environment(path: Path) -> dict[str, str | None]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: dict[str, str | None] = {}
    for name, job in (workflow.get("jobs") or {}).items():
        env = job.get("environment")
        out[name] = env.get("name") if isinstance(env, dict) else env
    return out


def test_the_split_has_files_to_check():
    # Guard the guard: if the secret names were wrong, everything below would pass vacuously.
    used = {secret: len(_workflows_using(secret)) for secret in GUARDED_SECRETS}
    assert all(count > 0 for count in used.values()), f"no workflow uses these secrets: {used}"


@pytest.mark.parametrize("secret", GUARDED_SECRETS)
def test_guarded_credentials_are_read_from_the_protected_environment(secret):
    offenders = []
    for path in _workflows_using(secret):
        if path.name in UNGUARDED_BY_DESIGN:
            continue
        jobs = _jobs_with_environment(path)
        unguarded = [name for name, env in jobs.items() if env != ENVIRONMENT]
        if unguarded:
            offenders.append(f"{path.name}: job(s) {unguarded} do not use `environment: {ENVIRONMENT}`")
    assert not offenders, (
        "these jobs read a publish/deploy credential without the environment, so the credential's "
        "protection rules (branch policy, and required reviewers once enabled) do not apply — a "
        "modified workflow on an unprotected branch can use it with nobody approving:\n  - "
        + "\n  - ".join(offenders)
    )


def test_the_deliberate_exception_is_still_deliberate():
    """`sync-d1.yml` may keep the repository secret — but only while it is still scheduled."""
    path = WORKFLOWS / "sync-d1.yml"
    triggers = (yaml.safe_load(path.read_text(encoding="utf-8")).get("on")
                or yaml.safe_load(path.read_text(encoding="utf-8")).get(True) or {})
    assert "schedule" in triggers, (
        "sync-d1.yml no longer runs on a schedule, so the reason it is exempt from the environment "
        "(an approval gate would stall a daily job) no longer holds — move it to the environment, or "
        "update UNGUARDED_BY_DESIGN with the new reason"
    )
    assert "CLOUDFLARE_API_TOKEN" in path.read_text(encoding="utf-8"), (
        "sync-d1.yml no longer uses the credential it is exempted for"
    )
