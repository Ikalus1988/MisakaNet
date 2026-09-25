#!/usr/bin/env python3
"""A workflow that lands changes through `land_change.py` must not persist checkout credentials.

`land_change.py` pushes with the PAT *in the URL*:

    url = f"https://x-access-token:{self.token}@github.com/{self.repo}.git"
    git("push", "--force", url, f"HEAD:refs/heads/{branch}")

`actions/checkout` stores its own token in `http.https://github.com/.extraheader` **and** in a credentials
file reached through `includeIf`, and those take precedence over the URL. So the push went out as
`github-actions[bot]`, GitHub created the pull request's runs as `action_required` — held, never executed —
and nothing could ever report the three required checks, which means the self-merging pull request could not
merge. The automation's own PRs were the ones being stranded.

Measured 2026-09-25:

| branch | held runs (07:00–08:00) |
|---|---|
| `bot/release-version-sync` | 39 |
| `bot/build-feed` | 24 |

and `bot/release-version-sync`'s PR (#2210, "docs: sync version to v2.34.0") sat with 13 of 13 runs held.

The rule is discovered, not listed: any workflow whose steps run `land_change.py` is covered, so a new lander
inherits it.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
LANDER = "scripts/ci/land_change.py"


def lander_workflows() -> dict[str, dict]:
    """Workflow name → parsed YAML, for every workflow that runs `land_change.py`."""
    out = {}
    for path in WORKFLOWS:
        text = path.read_text(encoding="utf-8")
        if LANDER not in text:
            continue
        data = yaml.safe_load(text)
        # A mention in a comment is not a call — and a shell comment lives *inside* a `run:` body, so the
        # bodies are scanned line by line with the comments removed (`pr-checks.yml` mentions the lander in
        # a comment explaining squash merges, and a substring search over the whole body counted it as a
        # caller; this is the third rule in this repository to be caught by its own documentation).
        calls = [step for job in (data.get("jobs") or {}).values()
                 for step in (job.get("steps") or [])
                 if any(LANDER in line for line in str(step.get("run") or "").splitlines()
                        if not line.lstrip().startswith("#"))]
        if calls:
            out[path.name] = data
    return out


def _checkouts(data: dict) -> list[dict]:
    return [step for job in (data.get("jobs") or {}).values()
            for step in (job.get("steps") or [])
            if str(step.get("uses", "")).startswith("actions/checkout")]


def credential_problems(workflows: dict[str, dict]) -> list[str]:
    problems = []
    for name, data in sorted(workflows.items()):
        checkouts = _checkouts(data)
        if not checkouts:
            problems.append(f"{name} runs {LANDER} but has no checkout — this rule cannot see it")
            continue
        for step in checkouts:
            if (step.get("with") or {}).get("persist-credentials") is not False:
                problems.append(
                    f"{name}: the checkout persists credentials, so `land_change.py`'s PAT push is "
                    f"attributed to `github-actions[bot]` and its pull request's runs are held")
    return problems


def test_every_lander_disables_persisted_checkout_credentials():
    workflows = lander_workflows()
    assert len(workflows) >= 5, f"only found {sorted(workflows)} — the discovery is broken"
    assert credential_problems(workflows) == [], "\n  - " + "\n  - ".join(credential_problems(workflows))


def test_the_rule_can_go_red():
    """Replayed on the state every lander was in before this fix."""
    fixture = {"x.yml": {"jobs": {"job": {"steps": [
        {"uses": "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"},
        {"run": f"python3 {LANDER} --branch bot/x --title 'x'"},
    ]}}}}
    problems = credential_problems(fixture)
    assert len(problems) == 1 and "held" in problems[0], problems
    # …and a lander that sets it, or one whose mention is only a comment, is fine.
    fixture["x.yml"]["jobs"]["job"]["steps"][0]["with"] = {"persist-credentials": False}
    assert credential_problems(fixture) == []
    assert lander_workflows() != {}, "guard: the real discovery found nothing"


def test_the_lander_still_pushes_with_its_own_token():
    """The setting above is only correct while `land_change.py` supplies the credential itself."""
    text = (REPO / "scripts" / "ci" / "land_change.py").read_text(encoding="utf-8")
    assert "x-access-token:{self.token}" in text, (
        "land_change.py no longer builds an authenticated push URL — with `persist-credentials: false` in "
        "every lander, its push would now fail instead of landing anything")
    assert "def push(self, branch: str)" in text, "the push implementation moved — re-check this rule"


def test_the_documented_reason_is_in_the_files_a_person_reads():
    """A bare `persist-credentials: false` with no reason is deleted by the next tidy-up."""
    import re

    for name in lander_workflows():
        text = (REPO / ".github" / "workflows" / name).read_text(encoding="utf-8")
        # The *setting*, not the first mention: the comment above it quotes the line it explains, and
        # `text.find` finds that mention first (which is how this rule failed the first time).
        match = re.search(r"(?m)^\s*persist-credentials: false\s*$", text)
        assert match, f"{name} has no `persist-credentials: false` setting line"
        window = text[max(0, match.start() - 900):match.start()]
        # Either name counts: both files document the same mechanism, and `release-please.yml` explains it
        # by pointing at `auto-sync-prs.yml` (its checkout serves its own PAT pushes as well as the
        # version-sync lander).
        assert "land_change.py" in window or "auto-sync-prs.yml" in window, (
            f"{name} sets persist-credentials without the measured reason next to it")
