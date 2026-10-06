#!/usr/bin/env python3
"""Saying "zero bounty" while advertising a payout in the same repository is a contradiction.

Found in the wild (2026-10-06)
-----------------------------
`CONTRIBUTING.md:4` told every human contributor:

> MisakaNet is a zero-bounty open-source project.

Opire appeared **nowhere** in `CONTRIBUTING.md`. Meanwhile `scripts/question_autopilot.py:178`
says it attaches an Opire banner — carrying `/reward`, `/try`, `/claim` and payout language — to
*every* issue the repository files. The banner on #2874/#2875 advertises a Bitcoin wallet.

So the written policy denied a bounty the automation advertised on every issue. The consequence was
measured, not theorised: one account posted 475 identical payout claims across two issues at about
one every 97 seconds, and a real contributor's correctly-formatted `/try` sat invisible underneath
for roughly a day (#2903).

The rule this file pins down
---------------------------
Keeping the integration is a legitimate decision. Denying it in prose while advertising it in
every issue is not. So:

1. Wherever a contributor-facing document claims the project pays no bounty, it must also disclose
   that external platforms may attach reward offers to individual issues.
2. That disclosure must name the mechanism (`scripts/question_autopilot.py`) and say who administers
   the payout — so a reader can tell whose promise they are being asked to trust.

This is a wording gate over three files, deliberately. It cannot decide whether Opire should exist;
it only refuses to let the two statements drift apart again without someone noticing.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Every contributor-facing document that makes the no-bounty claim. A new one has to be added here
# deliberately, which is the point: adding a third copy is a choice, not an accident.
CLAIMING_DOCS = ("CONTRIBUTING.md", "README.md", "README.zh-CN.md")

NO_BOUNTY_CLAIM = re.compile(r"zero[- ]bounty|Zero bounty", re.I)

# The disclosure has to be more than "sometimes there are bounties". These three are the parts whose
# absence reproduces the original problem: who attaches it, who pays it, and what to do about it.
DISCLOSURE_MARKERS = {
    "mechanism": ("question_autopilot",),
    "not administered by us": ("not administer", "do not administer", "we do not pay",
                              "not part of"),
    "verify independently": ("verify", "unverified", "confirm it independently", "confirm it"),
}


def _no_bounty_claims(text: str) -> list[str]:
    return [m.group(0) for m in NO_BOUNTY_CLAIM.finditer(text)]


def test_every_document_claiming_zero_bounty_also_discloses_external_rewards():
    """The gate. Without it, the two statements drift apart again the moment a file is edited."""
    unchecked: list[str] = []
    for name in CLAIMING_DOCS:
        path = REPO / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        claims = _no_bounty_claims(text)
        if not claims:
            continue
        missing = [what for what, needles in DISCLOSURE_MARKERS.items()
                   if not any(n.lower() in text.lower() for n in needles)]
        if missing:
            unchecked.append(f"{name} claims {claims[0]!r} but never says {missing}")

    assert not unchecked, (
        "these documents tell contributors there is no bounty, without disclosing that issues "
        "carry third-party reward banners added by our own automation:\n  "
        + "\n  ".join(unchecked)
        + "\n\nThe gap is not cosmetic: a claim-spam account found the banner and worked it "
        "for a day while a real claimant went unseen (#2903)."
    )


def test_the_banner_is_still_attached_by_our_own_automation():
    """If the banner goes away, the disclosures above mislead in the other direction.

    This is the half that makes the wording gate honest: it does not just require a disclosure, it
    requires the disclosure to match reality.
    """
    autopilot = (REPO / "scripts" / "question_autopilot.py").read_text(encoding="utf-8")
    assert "Opire" in autopilot, (
        "scripts/question_autopilot.py no longer mentions Opire — if the banner was removed on "
        "purpose, drop the disclosure requirement in the test above along with it, or these "
        "documents will now describe an integration that does not exist"
    )
