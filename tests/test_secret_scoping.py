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
# justified here. The names are the ones the workflows actually read — and the `release` environment
# must carry exactly these names, because environment secrets shadow repository secrets **by name**.
GUARDED_SECRETS = ("NPM_TOKEN", "CF_API_TOKEN")
ENVIRONMENT = "release"

# Nothing is exempt any more. The two scheduled syncs used to keep the repository secret on the grounds
# that an approval prompt stalls a cron; when the repository-level CF_API_TOKEN was deleted
# (2026-09-19), that choice stopped being available — the job could no longer read a credential at all.
# They now declare the environment like everything else, and the note in each file records the interim
# (a reviewer-free `automation` environment is the way to get unattended operation back).
EXEMPT: dict[str, str] = {}  # nothing is exempt today


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


def test_the_scheduled_syncs_record_that_they_are_interim():
    """They declare the environment, which means a person — that has to stay visible in the files.

    The tradeoff is real: a scheduled job on a reviewed environment runs when somebody approves it, not
    when the clock says so. Each file therefore carries the note, and the note names the way out (an
    `automation` environment without reviewers). If someone deletes the note without changing the
    arrangement, the reason for the arrangement disappears with it.
    """
    for name in ("sync-d1.yml", "sync-question-answers.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        assert "environment: release" in text, f"{name} lost its credential source"
        assert "INTERIM:" in text and "automation" in text, (
            f"{name} declares a *reviewed* environment for a scheduled job without recording why, or "
            "how to get unattended operation back"
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
