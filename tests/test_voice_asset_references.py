#!/usr/bin/env python3
"""Every `/assets/voice/*.mp3` this repository references must be a file that exists.

#2918 was found by a human diffing two lists: the four cues the registration page
asked for, and the four files actually in `docs/assets/voice/`. The two disagreed —
the page wanted `*.v2.mp3`, the repository had never committed a `.v2` file, and all
four requests returned 404. The user-visible effect was the worst kind: "Enable
voice" flips a label to a confirmed state and then plays nothing, with no error
anywhere to notice. Two places had drifted (`workers/register-proxy-sw.js` and
`docs/start.html`) while `docs/connect.html` and `lib/client.js` were already
correct, which is exactly why reading the code did not surface it.

That is the shape this test removes: reference drift against a file list is
mechanical, so it should be caught mechanically rather than by whoever happens to
compare the two lists next. A new cue added to `docs/assets/voice/` and not
referenced is not this test's business — that direction breaks nothing.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VOICE_DIR = REPO / "docs" / "assets" / "voice"

# Absolute site paths as they appear in markup and in JS string literals, and as
# `lib/client.js` builds them: `/assets/voice/<cue>.mp3`. The leading `/` is part of
# the URL, not of the repository path, so it is stripped before resolving.
VOICE_REF = re.compile(r"""["'(](/assets/voice/([A-Za-z0-9._-]+)\.mp3)["')]""")

# Every file type that can carry such a reference. `node_modules` is excluded by the
# walk below rather than by a fragile ignore list.
SCANNED_SUFFIXES = {".js", ".mjs", ".cjs", ".ts", ".html", ".md", ".json", ".yml", ".yaml"}

SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build", ".pytest_cache"}


def _committed_voice_files() -> set[str]:
    return {p.name for p in VOICE_DIR.glob("*.mp3")}


def _references() -> dict[str, set[str]]:
    """{mp3 file name -> {repo-relative files that reference it}}."""
    found: dict[str, set[str]] = {}
    for path in sorted(REPO.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(REPO).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in VOICE_REF.finditer(text):
            cue = f"{match.group(2)}.mp3"
            found.setdefault(cue, set()).add(str(path.relative_to(REPO)))
    return found


def test_the_voice_asset_directory_exists() -> None:
    """Without this every other assertion below is vacuous.

    Deleting the whole directory would otherwise leave zero references to check and
    the gate green — a gate that approves of having no voices at all.
    """
    files = _committed_voice_files()
    assert files, f"{VOICE_DIR} is empty or missing; the cue checks below would be vacuous"
    assert "lesson-found.mp3" in files, f"expected the standard cue set, found {sorted(files)}"


def test_every_referenced_voice_asset_exists_on_disk() -> None:
    """The #2918 check: a referenced cue that is not a committed file is a 404.

    `lib/client.js` builds its path from a cue name at runtime, so it is listed by
    the call site rather than by a literal; that direction is covered separately
    below, because the literal form cannot express it.
    """
    present = _committed_voice_files()
    refs = _references()
    assert refs, "no /assets/voice/*.mp3 reference found; the scan itself is broken"

    missing = {
        cue: sorted(where)
        for cue, where in refs.items()
        if cue not in present
    }
    assert not missing, (
        "these cues are referenced but no such file exists under docs/assets/voice/, "
        "so every request 404s:\n"
        + "\n".join(
            f"  {cue}  <- {', '.join(where)}"
            for cue, where in sorted(missing.items())
        )
    )


def test_the_server_named_cue_path_is_the_one_being_scanned() -> None:
    """`lib/client.js` composes the URL at runtime, so no literal exists to scan for it.

    `playCue(cue)` builds `API + "/assets/voice/" + cue + ".mp3"` where `cue` comes
    from the **server's** response body, not from a literal in this repository. That
    makes it uncheckable here — there is no name to enumerate — and it is also why
    the client was never affected by #2918: the server names a cue, and the four
    committed files cover it.

    So this test does not pretend to check the dynamic branch. It asserts the part
    that *is* statically knowable and that a future edit could plausibly break: that
    the concatenation still produces the same path shape this file scans for, and
    that the shape has not drifted into something the scan below would miss.
    """
    client = (REPO / "lib" / "client.js").read_text(encoding="utf-8")
    assert '"/assets/voice/" + cue + ".mp3"' in client, (
        "lib/client.js no longer builds the path as /assets/voice/<cue>.mp3; the literal "
        "scan in this file checks that shape, so if the shape changed this file needs "
        "updating rather than quietly passing"
    )
    present = _committed_voice_files()
    # The committed set is what the server is allowed to name. If it ever empties, the
    # dynamic path has nothing to resolve to and the literal scan becomes the only
    # thing standing between the two.
    assert present, "docs/assets/voice/ is empty, so the runtime-built path resolves to nothing"


def test_no_versioned_suffix_survives() -> None:
    """A `.v2` suffix is the specific shape #2918 took, so it is refused by name.

    Versioned asset names are not wrong in general — they are only wrong while the
    repository holds exactly the unversioned set. Rather than encode a rule about
    versioning, this asserts the fact that actually broke: the referenced file must
    exist. Kept as a separate test because the failure message differs, and because
    a reviewer reading the first failure should not have to infer this one.
    """
    present = _committed_voice_files()
    refs = _references()
    versioned = {
        cue: sorted(where)
        for cue, where in refs.items()
        if cue not in present and re.search(r"\.v\d+\.mp3$", cue)
    }
    assert not versioned, (
        "versioned cue referenced but absent from docs/assets/voice/ (#2918):\n"
        + "\n".join(f"  {cue}  <- {', '.join(w)}" for cue, w in sorted(versioned.items()))
    )


def test_the_two_registration_blocks_stay_in_step() -> None:
    """`register-proxy-sw.js` and `docs/start.html` carry the same map; drift is the bug.

    They are not generated from one another today, which is why both had to be
    edited for #2918 and why a future edit can easily touch one and not the other.
    Comparing the parsed cue maps is cheaper than re-deriving the whole failure.
    """
    pattern = re.compile(r"""const MISAKA_VOICE = \{(.*?)\};""", re.S)
    cue_re = re.compile(r"""["'](/assets/voice/([A-Za-z0-9._-]+\.mp3))["']""")
    maps = {}
    for rel in ("workers/register-proxy-sw.js", "docs/start.html"):
        text = (REPO / rel).read_text(encoding="utf-8")
        block = pattern.search(text)
        assert block, f"{rel}: MISAKA_VOICE map not found; rename it and update this test"
        maps[rel] = dict(cue_re.findall(block.group(1)))

    a, b = maps["workers/register-proxy-sw.js"], maps["docs/start.html"]
    assert a == b, (
        "the two registration pages point at different voice assets:\n"
        f"  register-proxy-sw.js: {a}\n"
        f"  docs/start.html      : {b}"
    )
    assert a, "the MISAKA_VOICE map parsed to nothing"
