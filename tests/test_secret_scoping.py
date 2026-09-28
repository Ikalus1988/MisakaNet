#!/usr/bin/env python3
"""Guarded credentials are read from an environment, and unattended jobs use the reviewer-free one.

`NPM_TOKEN` and the deploy-capable `CF_API_TOKEN` moved into the `release` environment
(2026-09-19), and the two scheduled syncs got their own D1-scoped credential in `automation`
(2026-09-20). Splitting credentials across two environments only buys something if the arrangement
cannot quietly rot, and the failure modes are not visible in the workflow files:

* **a job that reads a credential without declaring an environment** reads the repository-level
  secret instead — readable by any run on any branch, which is the thing the migration removed;
* **a scheduled job behind required reviewers does not become safer, it becomes unavailable** — the
  cron stops until a person approves it, which is how the served corpus quietly goes stale;
* **an unattended job holding the deploy-capable token** would mean a leak in a job nobody watches
  can replace the code served at misakanet.org.

So the split is asserted rather than remembered. The *scope* of a Cloudflare token (that
`automation`'s token really is D1-only) cannot be asserted from this repository: GitHub never reveals
a secret value, and only a green run proves the right value is installed. That check is a procedure,
written down in `docs/maintainer/credentials-and-environments.md` §4.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflows")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# Guarded credentials: a workflow that reads one of these must declare an environment, or the value
# comes from the repository (readable by every run on every branch). The names are the ones the
# workflows actually read — and each environment must carry exactly these names, because environment
# secrets shadow repository secrets **by name**.
# `CF_OBSERVABILITY_TOKEN` and `CF_BUILDS_TOKEN` are read-only rather than deploy-capable, which is
# exactly what makes them easy to leave unenforced — and the failure mode they share with the deploy
# token does not require a leak to matter: a value the document says is environment-scoped can be read
# from a repository secret any branch can print, and nothing in the file would say so. Same rule, so
# the same guard.
GUARDED_SECRETS = ("NPM_TOKEN", "CF_API_TOKEN", "CF_OBSERVABILITY_TOKEN", "CF_BUILDS_TOKEN")

# `release` gates on a required reviewer and holds the deploy-capable tokens; `automation` has no
# reviewers and holds a D1-only token, so that unattended jobs can run.
APPROVED_ENVIRONMENT = "release"
UNATTENDED_ENVIRONMENT = "automation"
KNOWN_ENVIRONMENTS = (APPROVED_ENVIRONMENT, UNATTENDED_ENVIRONMENT)

# Unattended workflows, and the credential scope their file has to record — the note is what makes
# reviewer-free access a decision rather than an accident.
UNATTENDED_WORKFLOWS = ("sync-d1.yml", "sync-question-answers.yml", "d1-backup.yml")

# Jobs that can change what is served in production. These must sit behind a human.
REVIEWED_JOBS = {"deploy-worker.yml": "deploy"}


def _workflows_using(secret: str) -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.yml") if secret in p.read_text(encoding="utf-8"))


def _job_environments(path: Path) -> dict[str, str | None]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: dict[str, str | None] = {}
    for name, job in (workflow.get("jobs") or {}).items():
        env = job.get("environment")
        out[name] = env.get("name") if isinstance(env, dict) else env
    return out


def _triggers(path: Path) -> set[str]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    # PyYAML resolves the bare key `on` to the boolean True (YAML 1.1), so look for both spellings.
    triggers = workflow.get("on") or workflow.get(True) or {}
    if isinstance(triggers, str):
        return {triggers}
    return set(triggers)


def test_the_split_has_files_to_check():
    # Guard the guard: if the secret names were wrong, everything below would pass vacuously.
    used = {secret: len(_workflows_using(secret)) for secret in GUARDED_SECRETS}
    assert all(count > 0 for count in used.values()), f"no workflow uses these secrets: {used}"


@pytest.mark.parametrize("secret", GUARDED_SECRETS)
def test_guarded_credentials_come_from_an_environment(secret):
    offenders = []
    for path in _workflows_using(secret):
        for name, env in _job_environments(path).items():
            if env not in KNOWN_ENVIRONMENTS:
                offenders.append(f"{path.name}: job `{name}` declares environment={env!r}")
    assert not offenders, (
        "these jobs read a guarded credential without declaring an environment that carries it, so "
        "the value is taken from the repository-level secret instead — readable by any workflow run "
        "on any branch, with nobody approving:\n  - " + "\n  - ".join(offenders)
    )


@pytest.mark.parametrize("secret", GUARDED_SECRETS)
def test_scheduled_jobs_use_the_environment_without_reviewers(secret):
    """A cron in a reviewed environment stops on the day nobody is there."""
    offenders = []
    for path in _workflows_using(secret):
        if "schedule" not in _triggers(path):
            continue
        for name, env in _job_environments(path).items():
            if env != UNATTENDED_ENVIRONMENT:
                offenders.append(f"{path.name}: scheduled job `{name}` uses environment={env!r}")
    assert not offenders, (
        f"a scheduled job must declare `environment: {UNATTENDED_ENVIRONMENT}` (no required "
        "reviewers, branch-restricted to main). Behind an approval gate the run waits for a person, "
        "so the automation silently stops being automation:\n  - " + "\n  - ".join(offenders)
    )


@pytest.mark.parametrize("filename,job", sorted(REVIEWED_JOBS.items()))
def test_jobs_that_change_production_keep_the_reviewed_environment(filename, job):
    """Least privilege runs both ways: the deploy credential stays where a human approves it."""
    env = _job_environments(WORKFLOWS / filename).get(job)
    assert env == APPROVED_ENVIRONMENT, (
        f"{filename}:{job} declares environment={env!r}. The deploy-capable credential belongs in "
        f"`{APPROVED_ENVIRONMENT}`, whose required reviewer is the only thing standing between a "
        "merged workflow edit and production."
    )


def test_the_unattended_workflows_record_the_scope_they_rely_on():
    """Unattended access is acceptable only because the credential inside cannot do much.

    The file has to say so — and say when the token expires, and where the rotation procedure lives.
    If someone swaps in a wider token, or deletes the note, the reason a reviewer-free environment is
    tolerable leaves with it.
    """
    for name in UNATTENDED_WORKFLOWS:
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "environment: automation" in text, f"{name} is no longer unattended"
        assert "D1:Edit" in text, (
            f"{name} relies on unattended access but no longer records that its Cloudflare token is "
            "scoped to D1:Edit — the note is what makes `automation` reviewer-free on purpose "
            "rather than by accident"
        )
        assert "credentials-and-environments.md" in text, (
            f"{name} lost the pointer to the document that explains the split and the rotation"
        )


def test_one_credential_has_exactly_one_name():
    """A workflow reading a differently-named secret is not guarded by the environment at all.

    Environment secrets shadow repository secrets **by name**. The first version of this migration put
    the Cloudflare value into `release` as `CLOUDFLARE_API_TOKEN` while every workflow read
    `secrets.CF_API_TOKEN`, so the environment would have been decoration: those jobs would have gone on
    reading the repository secret, and the change would have looked like a security improvement while
    changing nothing (found 2026-09-19, by checking the workflows' actual `secrets.*` references instead
    of grepping for the credential's *value* name — a grep that matched the environment-variable name
    rather than the secret name).
    """
    import re

    names: set[str] = set()
    for path in WORKFLOWS.glob("*.yml"):
        names |= set(re.findall(r"secrets\.([A-Z_]*API_TOKEN)", path.read_text(encoding="utf-8")))
    assert names == {"CF_API_TOKEN"}, (
        f"the Cloudflare credential is referenced under more than one secret name: {sorted(names)}. "
        "One credential, one name — otherwise whichever name the environment does not carry is read "
        "from the repository, unprotected."
    )
