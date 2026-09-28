#!/usr/bin/env python3
"""A public "contributor" ranking had `github-actions[bot]` at rank #2 (issue #908's board).

`scripts/leaderboard_watch.py` scores commit authors on `main` and excludes a hardcoded list of
identities. Measured 2026-09-25, on the board it publishes (`data/leaderboard.json`, 23 entries):

```
  #1  zsxh1990              94.81
  #2  github-actions[bot]    7.54   <- GitHub's own Actions App
  #5  misakanet-sync-bot     2.0    <- this repo's auto-sync-prs.yml git identity (no GitHub account)
 #18  misakanet agent        0.89   <- same, older tooling identity
 #22  misakanet-agent        0.51
```

The list named `dependabot[bot]`, `pre-commit-ci[bot]` and `cloudflare-workers-and-pages[bot]` — three
apps that barely appear here — and missed `github-actions[bot]`, the most active identity in the
repository. A list is the wrong shape for this: it only removes the bots somebody remembered.

There is a second reason the rule has to be about *shape*: contributors are taken from commit authors,
with `author.user.login` falling back to **the raw git author name** when no GitHub account matches. So
any string a `git config user.name` produced lands on a public contributor board — `misakanet-sync-bot`
has no `/users/` page at all and still ranked #5.

What this does **not** claim to do: tell whether a human is behind an account. GitHub's `type` only
separates Apps from users, and a user account can be driven by an agent. This answers the narrower,
checkable question — is this identity the project's own machinery? — and the docstring in
`docs/reputation.md` now says so where a reader would look for it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import leaderboard_watch as lw  # noqa: E402


# ── the identities that were on the board ───────────────────────────────────────────
@pytest.mark.parametrize("login", [
    "github-actions[bot]",       # the regression: rank #2 on the public board
    "misakanet-sync-bot",        # rank #5, and not a GitHub user at all
    "misakanet-bot",
    "misakanet agent",
    "misakanet-agent",
    "github-actions",
    "actions-user",
    "dependabot[bot]",
    "pre-commit-ci[bot]",
    "cloudflare-workers-and-pages[bot]",
    "GITHUB-ACTIONS[BOT]",       # case must not matter; the scorer lowercases
])
def test_the_projects_own_identities_are_excluded(login):
    assert lw.is_automation_login(login) is True, f"{login!r} would appear as a contributor"


@pytest.mark.parametrize("login", ["zsxh1990", "huyhoang2k5", "2lll5", "yashraj4", "misakanet-fan"])
def test_a_contributor_account_is_not_excluded(login):
    """The other direction: a filter that eats real contributors is worse than no filter."""
    assert lw.is_automation_login(login) is False, login


def test_any_github_app_is_excluded_by_shape_not_by_name():
    """`[bot]` is GitHub's own convention for an App, so a new App needs no list entry."""
    for name in ("some-new-app[bot]", "renovate[bot]", "copilot-swe-agent[bot]"):
        assert lw.is_automation_login(name) is True, name


def test_the_scorer_actually_uses_the_rule():
    """The rule is worthless if the scoring path still filters with a literal set."""
    src = (REPO / "scripts" / "leaderboard_watch.py").read_text(encoding="utf-8")
    body = "\n".join(line for line in src.splitlines() if not line.strip().startswith("#"))
    assert "is_automation_login(k)" in body or "is_automation_login(login)" in body, (
        "the scored dict is no longer filtered by the rule"
    )
    assert "EXCLUDE_LOGINS" not in body, "the hardcoded list is back"


# ── the gate that keeps it true when somebody adds an identity ──────────────────────
def _workflow_identities() -> set[str]:
    """Every `git config user.name "X"` the repository's workflows set."""
    names: set[str] = set()
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        names |= set(re.findall(r'user\.name\s+"([^"]+)"', text))
        names |= set(re.findall(r"user\.name\s+'([^']+)'", text))
    return names


def test_every_workflow_identity_is_excluded():
    """A new bot in a workflow must not need a second edit in the leaderboard script.

    This is the gate the original defect lacked: the identities that publish commits are discoverable
    from the workflows, so the filter can be checked against them instead of remembered.
    """
    names = _workflow_identities()
    assert names, "no git identities found in the workflows — the regex or the layout changed"
    missing = sorted(n for n in names if not lw.is_automation_login(n))
    assert missing == [], (
        f"these workflow identities would appear as contributors on the public board: {missing}. "
        "They are this repository's own machinery (see SELF_IDENTITIES)."
    )


def test_the_default_signoff_identity_is_excluded():
    """`scripts/adopt_pr.py` sets the identity most bot commits are authored with."""
    src = (REPO / "scripts" / "adopt_pr.py").read_text(encoding="utf-8")
    match = re.search(r'DEFAULT_SIGNOFF_NAME\s*=\s*"([^"]+)"', src)
    assert match, "the sign-off identity moved"
    assert lw.is_automation_login(match.group(1)) is True, match.group(1)


def test_the_board_file_is_not_silently_stale_about_this():
    """If `data/leaderboard.json` is present in a checkout, it must not still contain the bots.

    Skipped when the file is absent (a fresh clone of this repository does not track it) — but when a
    developer has one, it is the artifact that gets published, so it has to be checked.
    """
    path = REPO / "data" / "leaderboard.json"
    if not path.is_file():
        pytest.skip("no local leaderboard snapshot in this checkout")
    import json
    entries = json.loads(path.read_text(encoding="utf-8"))
    offenders = [e.get("login") for e in entries if lw.is_automation_login(e.get("login"))]
    assert offenders == [], (
        f"{path.name} still ranks {offenders} as contributors — regenerate it with "
        "`python3 scripts/leaderboard_watch.py` (it edits a snapshot published by leaderboard-watch.yml)"
    )
