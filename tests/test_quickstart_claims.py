"""The Quickstart's factual claims, checked against the things that make them true.

Three claims on the first-run surfaces had drifted, and none of them had a gate:

1. **Which assistants are supported.** The intro named five; the npm installer has wired ten since
   2026-09-21 (`060a2ade`), and `README.md` already said ten. The sentence was written one day
   earlier, on 2026-09-20 (`d89c7c7a`), and nothing compared it to the installer afterwards.
2. **What a pairing code is for.** #3473 added a line to Track A step 2 ("Generate a pairing
   code") that reads as a requirement. It is not: reads are anonymous, the installer calls
   `misakanet_register` itself and writes the token, and `--verify` talks to `tools/list`. The
   pairing flow is a separate, optional door for a *human* handing a token to an agent.
3. **The anonymous read limit.** Six live doc lines still said "5 combined reads/day per IP" — two
   stale facts in one number. Reads stopped being a daily quota on 2026-09-18; what remains is a
   per-address burst window whose numbers live in the worker (`READ_BURST_LIMIT` /
   `READ_BURST_WINDOW_SECONDS`), currently 20 per 60 seconds. The doc sentence is built from those
   constants here, so changing the limit without changing the docs fails this file.

The point of each assertion is that the fact lives in **one** place (the installer's `AGENTS`, the
worker's constants, the flow's code paths) and every copy is compared to it — not that the copies
agree with each other.

**One assertion changed shape in #3641.** Claim 2 was checked on the homepage by pinning the
English wording "Search needs no pairing code". The issue #3641 implemented here asked for the
homepage's Quickstart block to be free of the words 注册/配对 — the same block the assertion read.
The two cannot both hold, so the assertion now pins the *claim* ("searching needs nothing beyond
the install, and the Start page is optional") in both languages and on both copies (the page's
fallback text and the dictionary), and the detail surface `docs/quickstart.md` keeps the jargon
where it explains it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUICKSTART_MD = ROOT / "docs" / "quickstart.md"
INDEX = ROOT / "docs" / "index.html"
LOCALES = {lang: ROOT / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}
NPM_INSTALLER = ROOT / "packages" / "misakanet-setup" / "bin" / "misakanet-setup.mjs"
WORKER = ROOT / "workers" / "register-proxy-sw.js"

# install-id → the name a reader recognises. The installer's ids are lowercase file names; the
# intro is prose, so the comparison has to go through this table rather than through the ids.
DISPLAY = {
    "claude": "Claude Code",
    "codex": "Codex",
    "hermes": "Hermes",
    "openclaw": "OpenClaw",
    "codewhale": "codewhale",
    "cursor": "Cursor",
    "gemini": "Gemini CLI",
    "copilot": "Copilot CLI",
    "opencode": "OpenCode",
    "kiro": "Kiro",
    # Issue #3777: MiniMax Code's MCP entry is a plugin manifest, but it is still one of the
    # assistants the installer wires — so the intro has to name it like the rest.
    "mcode": "MiniMax Code",
    # Same rule for the harness whose tools come from its own plugin: the installer wires its rules
    # half, so the intro names it, and the install text says which half is which.
    "dsh": "DeepSeek Harness",
}

# Dated snapshots and benchmark payloads quote whatever was true when they were written; a file
# whose name carries a date is an archive, not a claim about today.
NOT_LIVE = re.compile(
    r"(benchmarks/|journey-reports/|blog/|release/|analytics/|\d{4}-\d{2}-\d{2})"
)
STALE_READ_CLAIM = re.compile(
    r"(\b5\b[^.\n]{0,40}(combined reads|free reads|reads per day)"
    r"|reads/day"
    r"|per day per IP)",
    re.I,
)

# The claim the Start-page link has to carry next to it, in both languages. These are claims, not
# fixed wordings: the homepage may phrase them its own way, but it may not stop making them. The
# old wording ("Search needs no pairing code") still satisfies the English pattern — the gate lost
# the *jargon* requirement, not the claim (see the test's docstring).
SEARCH_CLAIM_EN = re.compile(r"search needs (no\b|nothing\b)", re.I)
SEARCH_CLAIM_ZH = re.compile(r"检索不需要")
OPTIONAL_EN = re.compile(r"\boptional\b", re.I)
OPTIONAL_ZH = re.compile(r"可选")
# A card element and the fallback copy inside it: <span data-i18n="qsStartNote">fallback</span>
CARD_COPY = re.compile(r'data-i18n="([^"]+)"[^>]*>([^<]*)<', re.S)


def installer_targets() -> list[str]:
    text = NPM_INSTALLER.read_text(encoding="utf-8")
    match = re.search(r"^const AGENTS = \[([^\]]+)\]", text, re.M)
    assert match, "the npm installer's AGENTS array moved; fix this gate rather than deleting it"
    return re.findall(r"'([^']+)'", match.group(1))


def burst_facts() -> tuple[int, int]:
    text = WORKER.read_text(encoding="utf-8")
    limit = re.search(r"^const READ_BURST_LIMIT = Number\([^)]*\|\| (\d+)\);", text, re.M)
    window = re.search(r"^const READ_BURST_WINDOW_SECONDS = (\d+);", text, re.M)
    assert limit and window, "the anonymous burst constants moved; fix this gate"
    return int(limit.group(1)), int(window.group(1))


def track_a_card() -> str:
    """The Track A card only — Track B legitimately does not mention assistants at all."""
    page = INDEX.read_text(encoding="utf-8")
    start = page.index("<!-- Track A -->")
    end = page.index("<!-- Track B -->", start)
    return page[start:end]


def surfaces() -> dict[str, str]:
    return {
        "docs/quickstart.md": QUICKSTART_MD.read_text(encoding="utf-8"),
        "docs/index.html (Track A)": track_a_card(),
        "docs/locales/en.json": json.loads(LOCALES["en"].read_text(encoding="utf-8"))["qsTrackASub"],
        "docs/locales/zh.json": json.loads(LOCALES["zh"].read_text(encoding="utf-8"))["qsTrackASub"],
    }


def test_every_intro_surface_names_exactly_the_assistants_the_installer_wires() -> None:
    targets = installer_targets()
    expected = [DISPLAY[t] for t in targets]
    failures = []
    for name, text in surfaces().items():
        named = [d for d in DISPLAY.values() if d in text]
        missing = sorted(set(expected) - set(named))
        extra = sorted(set(named) - set(expected))
        if missing or extra:
            failures.append(f"{name}: missing={missing} extra={extra}")
    assert not failures, (
        "the Quickstart's assistant list disagrees with the npm installer's AGENTS "
        f"({len(targets)} targets: {expected}).\n" + "\n".join(f"  {f}" for f in failures)
    )


def test_the_presentation_names_every_target_not_a_hand_picked_five() -> None:
    # Guards the gate above: a table that had silently shrunk to the five the old copy named would
    # make `extra` empty and `missing` empty at the same time, and the test would pass while the
    # screenshots stayed wrong.
    assert len(installer_targets()) >= 10, "the installer lost targets — re-read this gate"
    assert len(DISPLAY) == len(installer_targets())


def test_the_quickstart_says_pairing_is_not_needed_for_search() -> None:
    """The search path must not read as a step the reader still owes the installer.

    **Two surfaces, two jobs.**

    1. *The fact* lives in `docs/quickstart.md`: it explains what a pairing code is and says
       the install path does not involve one. That file is the detail surface, so the jargon
       stays there.
    2. *The claim next to the link* lives on the homepage's Track A card. #3641 took the jargon
       out of it — "Search needs no pairing code" became "Search needs nothing else" — because
       the homepage is the entry surface and "pairing code" is a word a first-time reader has no
       context for. The issue asked for exactly that ("首页快速开始区无注册/配对字样"), and this
       assertion used to contradict it: it pinned one English wording inside the very block the
       issue wanted free of the word.

    So the gate now pins the **claim** instead of the wording. The card must still say that
    searching needs nothing beyond the install, and the Start page must still be marked optional
    — a copy that drops either, or that turns the claim into a requirement ("Search needs a
    pairing code"), fails here.

    Both copies are checked: the page's own fallback text **and** the dictionary the JavaScript
    surface renders from. The dictionary is a separate copy that drifts on its own, and it is
    the one a reader with JS actually sees.
    """
    quickstart = QUICKSTART_MD.read_text(encoding="utf-8")
    assert "no pairing code" in quickstart.lower(), (
        "docs/quickstart.md no longer says the install path needs no pairing code. It is the "
        "surface that explains what a pairing code is, so the fact has to stay there."
    )

    card = track_a_card()
    notes = [(key, value) for key, value in CARD_COPY.findall(card) if SEARCH_CLAIM_EN.search(value)]
    assert notes, (
        "the Track A card no longer says that searching needs nothing beyond the install — the "
        "Start-page link reads as another step the reader owes the installer"
    )
    for key, fallback in notes:
        assert OPTIONAL_EN.search(fallback), (
            f"the Track A card's {key} says searching needs nothing else, but no longer marks the "
            "Start page as optional"
        )
        for lang, claim, optional in (
            ("en", SEARCH_CLAIM_EN, OPTIONAL_EN),
            ("zh", SEARCH_CLAIM_ZH, OPTIONAL_ZH),
        ):
            value = json.loads(LOCALES[lang].read_text(encoding="utf-8")).get(key, "")
            assert claim.search(value), (
                f"the {lang} dictionary's {key} does not carry the claim the homepage's fallback "
                f"copy carries: {value!r}"
            )
            assert optional.search(value), (
                f"the {lang} dictionary's {key} no longer marks the Start page as optional: {value!r}"
            )


def test_the_docs_state_the_burst_limit_the_worker_enforces() -> None:
    limit, window = burst_facts()
    phrase = f"{limit} reads per {window} seconds"
    for rel in ("docs/integrations/mcp-remote.md", "docs/auth.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert phrase in text, (
            f"{rel} must state the anonymous read window as '{phrase}' — the worker's own "
            "constants are the source, so a changed limit has to reach the docs in the same commit"
        )


def test_no_live_doc_states_an_anonymous_per_day_read_quota() -> None:
    offenders = []
    for path in sorted(ROOT.glob("docs/**/*.md")):
        rel = path.relative_to(ROOT).as_posix()
        if NOT_LIVE.search(rel):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            hit = STALE_READ_CLAIM.search(line)
            if hit:
                offenders.append(f"{rel}:{number}: {line.strip()[:160]}")
    assert not offenders, (
        "anonymous reads stopped being a per-day quota on 2026-09-18; the bound is a per-address "
        "burst window (currently %d reads / %ds). Lines still claiming a daily read limit:\n" % burst_facts()
        + "\n".join(f"  {o}" for o in offenders)
    )


def test_the_start_page_says_the_code_is_optional_in_both_twins() -> None:
    """Production serves the worker's inline copy, not `docs/start.html` (#3474).

    So a clarifying sentence added to one twin is invisible to users if it is missing from the
    other — which is exactly how the retired avatar copy stayed live for weeks. Both must carry the
    line, and the marker is the sentence itself, not a file hash.
    """
    marker = "不需要配对码"
    site = (ROOT / "docs" / "start.html").read_text(encoding="utf-8")
    served = WORKER.read_text(encoding="utf-8")
    assert marker in site, "docs/start.html lost the 'you do not need a code' line"
    assert marker in served, (
        "the worker's inline /start template — the copy production actually serves — lost the "
        "'you do not need a code' line, so the page a visitor sees still reads as mandatory"
    )
