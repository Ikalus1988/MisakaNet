#!/usr/bin/env python3
"""The npm description must not manufacture a data-exfiltration worry — and must not understate it.

What happened (issue #3689): a third-party agent audited the npm metadata *before* installing,
read "and to distil the session at a checkpoint" as "distil the session and send it to a server",
and spent extra time reading 2151 lines of source to confirm it was safe. The risk did not exist —
the checkpoint hook counts user turns and injects a local reminder — but the description manufactured
it, and for an agent tool the description is the first link in the trust chain. One wrong sentence
cost the reader 2151 lines.

So this gate pins the two things a description of this installer owes its reader, and pins them
*against the code* rather than against a copy of the wording:

1. **What it writes** — an MCP endpoint into each agent config, rules blocks for the clients that
   take one, and a local hook for Claude Code.
2. **What leaves this machine** — at most one anonymous request while the installer runs (the
   anonymous registration); afterwards, only what the agent itself sends, *plus* the one opt-in
   path on which the hook itself sends something (`MISAKANET_HOOK_FETCH=1`, off by default).

Both layers must be present. A description that keeps only the first is as dishonest as the old
one: it invites the reader to assume the worst about the second. And the second has to be
complete: the hook's own opt-in lookup is the one thing that leaves the machine without the agent
sending it, so a description that says "only what the agent sends" without naming the opt-in is
*almost* true — and almost true is the failure mode this issue is about.

The wording rules this gate enforces, and why each is a gate rather than a style preference:

* **No "distil" / "distill" / "session".** These are the words that produced the false alarm. A
  future edit that reintroduces any of them has reintroduced the defect, so they are banned
  outright — a description that says "uploads the session" is wrong whatever else it says.
* **No partial client roster.** The description used to name five of the ten supported clients,
  which reads as "these five" and is a different lie from the same sentence. It names none of
  them now: the roster belongs to the README, which lists every client with a row of its own.
  A description that names one client as part of a per-client claim ("a Claude Code hook") is
  fine; one that names two to nine is a partial roster and fails.
* **A length budget.** npm truncates long descriptions, and a truncated description loses its
  second half — which is the half that answers the reader's actual question.
* **A hedged request count.** The installer sends one anonymous request on a first install, and
  **none at all** on a re-install that finds an existing token, so the count is "at most one".
  A description that says "one request" asserts a number the code does not guarantee.

Every assertion below is written so it can go red. Each one was checked by breaking the thing it
pins (see the mutation audit in the commit message): the banned words, the length budget, each
layer, the roster, and the README/description agreement.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "packages" / "misakanet-setup" / "package.json"
README = REPO / "packages" / "misakanet-setup" / "README.md"
INSTALLER = REPO / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"

# The words that produced the false alarm. Banned case-insensitively, as whole words: "distil",
# "distill" and "session" are what a reader pattern-matches on, and any of them back in the
# description means the same false alarm is being rebuilt.
BANNED_WORDS = ("distil", "distill", "session")

# npm shows a description truncated in some surfaces, and a truncated description loses the
# layer that answers "what leaves this machine". The budget is generous for two sentences.
MAX_LENGTH = 350

# The clients the installer actually supports, in the words a reader would use. The README holds
# the roster, and the test below keeps it in step with the installer's own `AGENTS` array, so
# adding a client there without naming it in the README fails the gate rather than leaving a
# roster that quietly stops being the whole one.
CLIENT_NAMES = (
    "Claude Code",
    "Codex",
    "Hermes",
    "OpenClaw",
    "codewhale",
    "Cursor",
    "Gemini CLI",
    "Copilot CLI",
    "OpenCode",
    "Kiro",
)


# The claims the description and the README's install section must both carry, each as an anchor
# plus the qualifiers that make it true of all ten clients. The qualifier is the substance:
# "rules blocks" alone is a lie for the five JSON-file clients, and "hook" alone is a lie for the
# nine that do not get one.
CLAIMS = (
    ("mcp endpoint", ()),
    ("rules block", (r"takes? one",)),
    ("hook", (r"claude code",)),
    ("anonymous", (r"install",)),
    ("agent", ()),
    # The one opt-in path by which the *hook* sends something. Both texts must name it and must
    # say it is off by default, or the egress half of the description is "almost true" — which is
    # the failure mode this issue exists to stop.
    ("MISAKANET_HOOK_FETCH", (r"off by default",)),
    # What that path sends: a fragment of the failed call's error text, or its command when the
    # tool gave no error text. Both markers, or the sentence is a partial truth.
    ("error text", (r"command",)),
)

# How far from the anchor a qualifier may sit and still count as part of the same claim. Wide
# enough for the README's line wrapping, narrow enough that the two halves of a sentence cannot
# pass each other's qualifiers off as agreement.
CLAIM_WINDOW = 160


def claim_present(text: str, anchor: str, qualifiers: tuple[str, ...], window: int = CLAIM_WINDOW) -> bool:
    """True when `anchor` appears and every qualifier sits close to one of its occurrences.

    Matching runs against a whitespace-normalised, lower-cased copy, so the README's line
    wrapping cannot hide a marker, and the window is searched on both sides of the anchor because
    the qualifier may sit before it ("a Claude Code hook") or after it ("the client takes one").

    `window` is the distance in characters on *each* side of the anchor. A tight window is for
    qualifiers that must sit next to their claim: "the hook sends nothing by default" only
    qualifies the claim if "by default" is attached to it, not if the row happens to say "off by
    default" somewhere else.
    """
    normalised = re.sub(r"\s+", " ", text.lower())
    anchor = anchor.lower()
    start = 0
    while True:
        index = normalised.find(anchor, start)
        if index == -1:
            return False
        span = normalised[max(0, index - window) : index + window]
        if all(re.search(qualifier, span) for qualifier in qualifiers):
            return True
        start = index + 1


def description() -> str:
    return json.loads(PACKAGE.read_text(encoding="utf-8"))["description"]


def readme_text() -> str:
    return README.read_text(encoding="utf-8")


def readme_install_section() -> str:
    """The README's install section — the part that describes what the installer does.

    Scoped deliberately: the README is long, and the later sections (the flags table, the safety
    notes) mention the same mechanisms in their own words. Checking the whole file would let any
    one of those mentions stand in for the install section, so a disagreement between the README's
    own install section and the npm description would pass unnoticed.
    """
    text = readme_text()
    start = text.index("\n## ")
    return text[:start]


def installer_agents() -> list[str]:
    """The client ids the installer supports, read from the installer's own list."""
    text = INSTALLER.read_text(encoding="utf-8")
    match = re.search(r"const AGENTS = \[(.*?)\];", text, re.DOTALL)
    assert match, "the installer must keep an AGENTS list for this gate to compare against"
    return re.findall(r"'([a-z]+)'", match.group(1))


def test_description_has_no_banned_wording():
    """No "distil" / "distill" / "session" — the three words that manufactured the worry."""
    text = description().lower()
    found = [word for word in BANNED_WORDS if re.search(rf"\b{word}", text)]
    assert not found, (
        f"the npm description contains {found}; these are the words that made a third-party agent "
        "read 'distil the session' as 'send the session to a server' and read 2151 lines of source "
        "to confirm it was safe (issue #3689). The checkpoint hook is a local reminder — say what "
        "it writes and what leaves the machine instead."
    )


def test_description_fits_the_length_budget():
    """Two sentences have to survive to the reader; npm truncates what does not fit."""
    text = description()
    assert len(text) <= MAX_LENGTH, (
        f"the npm description is {len(text)} characters, over the {MAX_LENGTH} budget; npm "
        "truncates it, and a truncated description loses the 'what leaves this machine' half"
    )


def test_description_says_what_it_writes():
    """Layer one: the endpoint, the rules blocks, and the local hook must all be named."""
    text = description().lower()
    missing = [
        what
        for what in ("mcp endpoint", "rules block", "hook")
        if what not in text
    ]
    assert not missing, (
        f"the npm description does not say {missing} — a reader cannot tell what the installer "
        "writes on their machine unless the description names the files it touches"
    )


def test_description_says_what_leaves_this_machine():
    """Layer two: the one anonymous request at install, and what happens afterwards."""
    text = description().lower()
    missing = [
        what
        for what in ("anonymous", "install", "agent")
        if what not in text
    ]
    assert not missing, (
        f"the npm description does not say {missing} — 'what leaves this machine' is the half a "
        "reader auditing before install is looking for, and omitting it is what left room for the "
        "false alarm (issue #3689)"
    )


# The count of the install-time request has to be hedged. Measured: a first install sends exactly
# one anonymous request (the registration); a re-install that finds an existing token sends none;
# `--no-register` and `--dry-run` send none. So the truthful count is "at most one" — a bare
# "one request" overstates what the code guarantees.
COUNT_HEDGES = ("at most", "up to", "no more than")


def test_description_does_not_overstate_the_install_request_count():
    """The install-time request count must be hedged, in the description and in the README."""
    desc = description().lower()
    assert any(word in desc for word in COUNT_HEDGES), (
        "the npm description states the install-time request count without hedging it; a first "
        "install sends one anonymous request but a re-install with an existing token sends none, "
        "so the count is 'at most one', not 'one' (issue #3689)"
    )
    readme = readme_install_section().lower()
    assert any(word in readme for word in COUNT_HEDGES), (
        "the README's install section states the request count without hedging it; it must agree "
        "with the npm description (issue #3689)"
    )


def test_description_carries_the_opt_in_egress_clause():
    """The description must name the one opt-in path on which the hook itself sends something.

    Three things have to be visible in the description, or a reader auditing before install is
    looking at a sentence that is *almost* true — and "almost true" is what this issue is about:
    the path exists, the *hook* is what uses it (the agent does not send that fragment), and it
    is off by default.
    """
    desc = description()
    assert "MISAKANET_HOOK_FETCH" in desc, (
        "the npm description does not mention MISAKANET_HOOK_FETCH; with it set, the hook itself "
        "sends the failed tool call's error text as a search query. A description that omits it "
        "is the 'almost true' sentence issue #3689 is about."
    )
    assert claim_present(desc, "MISAKANET_HOOK_FETCH", (r"off by default",)), (
        "the npm description names MISAKANET_HOOK_FETCH without saying it is off by default; the "
        "installer never sets it, so the default is the path that sends nothing (issue #3689)"
    )
    assert re.search(r"hook (itself )?sends", desc.lower()), (
        "the npm description does not say that the *hook* is what sends; the agent does not send "
        "that fragment, the hook does (issue #3689)"
    )


def test_description_has_no_partial_client_roster():
    """No partial roster: the description names at most one client, or all ten.

    A list of five of the ten supported clients reads as "these five" — the same defect as the
    old sentence, wearing a different hat. The roster belongs to the README, which lists every
    client with a row of its own; the description may name a single client only as part of a
    per-client claim ("a Claude Code hook", because the hook really is Claude Code's).
    """
    text = description()
    named = [name for name in CLIENT_NAMES if name in text]
    assert len(named) <= 1 or named == list(CLIENT_NAMES), (
        f"the npm description names {named} — a partial roster reads as the full set, which is "
        "the same lie the old sentence told (issue #3689). Name none, or all ten."
    )


def test_readme_roster_names_every_supported_client():
    """The README holds the roster, and the roster is the whole one."""
    agents = installer_agents()
    assert len(agents) == len(CLIENT_NAMES), (
        f"the installer supports {agents} but this gate knows {CLIENT_NAMES}; update both when a "
        "client is added, so the roster cannot silently go stale"
    )
    readme = readme_install_section().lower()
    missing = [name for name in CLIENT_NAMES if name.lower() not in readme]
    assert not missing, (
        f"the README's install section does not name {missing}; the README is where the client "
        "roster lives, so it must be the whole roster (issue #3689)"
    )


def test_readme_install_section_agrees_with_the_description():
    """The README's install section must not contradict the npm description.

    The README is where a reader lands after the npm page, so a README that says the opposite of
    the description reintroduces the same doubt with more words.

    Each claim is checked as an *anchor plus its qualifiers*, not as a bare noun. A bare
    substring check cannot see a negation: a README claiming "no rules blocks at all" still
    contains the string "rules block", so it would pass a substring gate while contradicting the
    description outright. The qualifier is what makes the claim true in the first place — five of
    the ten clients get no rules block, and only Claude Code gets the hook — so the qualifier has
    to be there, near the claim, in both texts.
    """
    desc = description()
    readme = readme_install_section()
    assert "distil" not in readme.lower() and "distill" not in readme.lower(), (
        "the package README still says 'distil'; that wording is what manufactured the "
        "'it uploads the session' reading (issue #3689)"
    )
    for anchor, qualifiers in CLAIMS:
        assert claim_present(desc, anchor, qualifiers), (
            f"the npm description does not carry the {anchor!r} claim "
            f"(with its qualifiers {qualifiers})"
        )
        assert claim_present(readme, anchor, qualifiers), (
            f"the README's install section does not carry the {anchor!r} claim "
            f"(with its qualifiers {qualifiers}), so it disagrees with the npm description"
        )


def test_readme_checkpoint_row_does_not_call_the_reminder_a_distillation():
    """The turn-20 row must describe what the hook does: inject a local reminder."""
    text = readme_text()
    row = [line for line in text.splitlines() if "the checkpoint **fires**" in line]
    assert row, "the README must keep its 'the checkpoint fires' row"
    assert "distil" not in row[0].lower() and "distill" not in row[0].lower(), (
        "the checkpoint row still calls the turn-20 reminder a 'distil and submit'; the hook "
        "injects a local reminder and sends nothing itself (issue #3689)"
    )
    # Banning the old word is not enough on its own: a row that dropped the reminder's wording
    # entirely would pass the check above and tell the reader nothing. Pin what the row must say
    # instead — what the hook injects, and that the hook itself is not what sends anything.
    lowered = row[0].lower()
    missing = [
        what
        for what in ("write up the reusable lessons", "sends nothing")
        if what not in lowered
    ]
    assert not missing, (
        f"the checkpoint row no longer says {missing}; the row must name the reminder it injects "
        "and state that the hook itself sends nothing (issue #3689)"
    )
    # "the hook sends nothing" is only true *by default*. Left unqualified, the row contradicts
    # the npm description, which names the opt-in that changes it — so the qualifier and the
    # opt-in both have to be in the row.
    assert claim_present(row[0], "sends nothing", (r"by default",), window=40), (
        "the checkpoint row says the hook sends nothing without qualifying it *there*; the hook "
        "sends the failed call's error text when MISAKANET_HOOK_FETCH=1 is set (issue #3689)"
    )
    assert "MISAKANET_HOOK_FETCH" in row[0], (
        "the checkpoint row does not name MISAKANET_HOOK_FETCH=1, the opt-in that makes the hook "
        "send; the row must not leave that path undocumented (issue #3689)"
    )
