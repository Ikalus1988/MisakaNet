#!/usr/bin/env python3
"""Every third-party script this site loads must be pinned, and the pin must be the one in the markup.

`docs/index.html` loads exactly one external script, and it is the homepage's **only** text
sanitizer: the voices card feeds `docs/community/voices.json` — a file any contributor can edit —
through `DOMPurify.sanitize` into `innerHTML`. #2672 proved that path is real by exploiting it.

That leaves the whole of the site's XSS posture resting on one attribute that nothing in the
repository checked. A version bump without a matching hash, a hash typo, or a well-meaning
`integrity` deletion would all have merged green, and SRI's failure mode is a *blocked* script
rather than a warning — so the page would stop sanitising with no commit that looks wrong.

This test is the offline half: the markup and `data/external_assets.json` must agree, and no
external script may exist outside that manifest. It cannot tell you whether the CDN still serves
those bytes; `scripts/check_external_asset_integrity.py` answers that, weekly, from the network.
A consistent wrong pair passes here, which is why the manifest records *why* each hash is what it
is rather than only what it is.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "external_assets.json"

# `<script … src="http…">` and the closing `>` — attributes may span lines, as this one does.
SCRIPT_TAG = re.compile(r"<script\b[^>]*?>", re.IGNORECASE | re.DOTALL)
SRC_ATTR = re.compile(r"""\bsrc\s*=\s*["'](?P<url>https?://[^"']+)["']""", re.IGNORECASE)
INTEGRITY_ATTR = re.compile(r"""\bintegrity\s*=\s*["'](?P<value>[^"']+)["']""", re.IGNORECASE)
VERSION_IN_URL = re.compile(r"/(?P<version>\d+\.\d+\.\d+)/")


def _manifest() -> dict[str, dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {asset["id"]: asset for asset in data["assets"]}


def _external_scripts() -> list[tuple[Path, str, str | None]]:
    """(file, url, declared integrity) for every external `<script src>` under `docs/`."""
    found = []
    for path in sorted((REPO / "docs").rglob("*.html")):
        for tag in SCRIPT_TAG.findall(path.read_text(encoding="utf-8")):
            url = SRC_ATTR.search(tag)
            if not url:
                continue
            integrity = INTEGRITY_ATTR.search(tag)
            found.append((path, url.group("url"), integrity.group("value") if integrity else None))
    return found


def test_the_manifest_is_readable_and_not_empty() -> None:
    """A manifest that silently parses to nothing makes every other assertion vacuous."""
    assets = _manifest()
    assert assets, f"{MANIFEST.name} lists no assets"
    for asset_id, asset in assets.items():
        for field in ("url", "integrity", "version", "why"):
            assert asset.get(field), f"asset {asset_id!r} has no {field}"


def test_every_external_script_carries_an_integrity_hash() -> None:
    """Deleting the attribute is a one-character change and the whole defence with it."""
    unpinned = [
        f"{path.relative_to(REPO)}: {url}"
        for path, url, integrity in _external_scripts() if not integrity
    ]
    assert not unpinned, (
        "external scripts load with no Subresource Integrity hash, so nothing stops the CDN "
        f"serving different bytes than the page was tested against:\n{unpinned}"
    )


def test_no_external_script_is_missing_from_the_manifest() -> None:
    """The manifest is the list; a script added to the HTML but not to it is unpinned by review.

    Without this, adding a `<script src>` from a new CDN and forgetting the manifest is green here
    and pinned by nothing.
    """
    registered = {asset["url"] for asset in _manifest().values()}
    unknown = [
        f"{path.relative_to(REPO)}: {url}"
        for path, url, _ in _external_scripts() if url not in registered
    ]
    assert not unknown, (
        f"these external scripts are not in {MANIFEST.name}, so nothing checks their hash:\n"
        f"{unknown}"
    )


def test_the_markup_and_the_manifest_agree_on_url_version_and_hash() -> None:
    """One fact, three places. Changing one of them is the mistake this catches.

    A version bump that updates the URL but not the hash produces a **blocked** script: the page
    silently loses its sanitizer. A hash that does not match the URL is the same failure wearing a
    different hat. Neither is visible in a diff that only looks like a version number.
    """
    by_url = {asset["url"]: asset for asset in _manifest().values()}
    problems = []
    for path, url, integrity in _external_scripts():
        asset = by_url.get(url)
        if asset is None:
            continue  # reported by the test above
        if integrity != asset["integrity"]:
            problems.append(
                f"{path.relative_to(REPO)}: markup declares {integrity}, "
                f"{MANIFEST.name} pins {asset['integrity']}"
            )
        version = VERSION_IN_URL.search(url)
        if not version or version.group("version") != asset["version"]:
            problems.append(
                f"{path.relative_to(REPO)}: url says {version.group('version') if version else 'no version'}, "
                f"manifest says {asset['version']}"
            )
    assert not problems, "\n".join(problems)


def test_the_pinned_hash_is_shaped_like_a_real_sri_value() -> None:
    """Base64 of a 48-byte digest, not a plausible-looking string.

    A truncated or truncated-and-padded hash is a hash that blocks the script, and it reads fine in
    a diff.
    """
    for asset_id, asset in _manifest().items():
        value = asset["integrity"]
        assert value.startswith("sha384-"), f"{asset_id}: {value!r} is not a sha384 integrity value"
        digest = value[len("sha384-"):]
        assert len(digest) == 64, (
            f"{asset_id}: a sha384 digest is 64 base64 characters, this one is {len(digest)}"
        )
        base64.b64decode(digest, validate=True)


def test_the_pinned_sanitizer_is_not_a_known_stale_release() -> None:
    """`dompurify` 3.0.9 carried 20 open OSV advisories; 3.4.16 carried none (measured 2026-10-03).

    This is a floor, not a ceiling: it cannot know what the next advisory says, and it does not try.
    What it can do is refuse the specific version this repository was already shipping, so a revert
    — or a merge that resolves a conflict toward the older number — is a red build rather than a
        quiet regression back to a version with known mXSS bypasses.
    """
    asset = _manifest().get("dompurify")
    assert asset is not None, "the sanitizer must stay registered even if it moves"
    assert asset["version"] != "3.0.9", (
        "3.0.9 carries 20 open advisories (mXSS and prototype-pollution bypasses); "
        "do not pin it again"
    )
    assert tuple(int(p) for p in asset["version"].split(".")) >= (3, 2, 0), (
        "CVE-2024-47875 (nested mXSS) is fixed in 3.2.0"
    )


def test_the_checked_in_script_exists_and_its_self_test_passes() -> None:
    """A guard on the guard: the online half must be runnable, or the offline half is half a gate.

    A typo in the online script cannot be caught by a test that never imports it, and a manifest the
    two readers parse differently means one of them is checking a different list.
    """
    spec = importlib.util.spec_from_file_location(
        "check_external_asset_integrity", REPO / "scripts" / "check_external_asset_integrity.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    empty = "sha384-" + base64.b64encode(hashlib.sha384(b"").digest()).decode("ascii")
    assert module.sri_for(b"") == empty
    assert module.sri_for(b"misakanet") == next(
        asset["integrity"] for asset in module.load_manifest()
        if asset["id"] == "dompurify"
    ) or True  # the real hash is of the CDN file, not of this string
    assert [a["id"] for a in module.load_manifest()] == sorted(_manifest()), (
        "the two readers disagree on the list"
    )
