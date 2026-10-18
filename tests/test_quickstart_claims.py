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
    assert "no pairing code is involved" in QUICKSTART_MD.read_text(encoding="utf-8").lower() or \
           "no pairing code" in QUICKSTART_MD.read_text(encoding="utf-8"), (
        "the Quickstart no longer says the install path needs no pairing code. #3473 added a line "
        "that read as a requirement; if the copy changed again, keep the qualifier next to the "
        "Start-page link."
    )
    assert "Search needs no pairing code" in track_a_card(), (
        "the Track A card must say search needs no pairing code — otherwise the Start-page link "
        "reads as another step the reader owes the installer"
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
