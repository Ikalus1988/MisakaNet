#!/usr/bin/env python3
"""The community-channel plugin package must be the official package plus two features.

The two channels drifted in both directions at once (2026-11-11): the community build kept the
read-retry and the interactive card gate but lost the `trust_notice` marking, the awaited replies
and the `new_lesson_candidate` classification, while the official build never got the card gate.
The community package is now rebuilt from the official one, and these gates are what keeps that
true: they fail the moment a fix lands in `.cindy-plugin/` and is not carried over.

`tests/test_cindy_plugin_package.py` covers the official package; this file covers the community
one and the relationship between the two.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OFFICIAL = REPO / ".cindy-plugin"
COMMUNITY = REPO / ".cindy-plugin-community"


def manifest(base: Path) -> dict:
    return json.loads((base / "ghost.json").read_text(encoding="utf-8"))


def test_the_community_package_is_a_package_this_repository_ships():
    entry = manifest(COMMUNITY)
    assert entry["schemaVersion"] == 3
    assert entry["id"] == "misakanet"
    assert re.fullmatch(r"\d+\.\d+\.\d+", entry["version"]), entry["version"]
    # The official manifest dropped the autonomous-network grant on the market review's advice;
    # the community copy must not bring it back.
    assert "network" not in entry, entry.get("network")
    names = [tool["name"] for tool in entry["tools"]]
    assert len(names) == len(set(names)), f"duplicate tool names: {names}"
    assert {
        "misakanet_search",
        "misakanet_get_lesson",
        "misakanet_preflight",
        "misakanet_submit_intake",
        "misakanet_me_inbox",
    } <= set(names)
    for tool in entry["tools"]:
        assert tool.get("description"), tool["name"]
        assert tool.get("parameters", {}).get("type") == "object", tool["name"]


def test_the_community_package_declares_its_card_gate():
    """The card gate is the community channel's own feature: without it, `confirm` means nothing."""
    entry = manifest(COMMUNITY)
    assert entry.get("card") is not None, "the community manifest lost its card declaration"
    source = (COMMUNITY / "main.js").read_text(encoding="utf-8")
    for marker in ("supplyIntakeCard", "handleCardAction", "CARD_CONFIRM_TIMEOUT_MS"):
        assert marker in source, f"the card gate lost {marker}"


def test_the_read_retry_only_covers_reads():
    """The retry is for flaky reads. A retried *upload* would publish the same issue twice."""
    source = (COMMUNITY / "main.js").read_text(encoding="utf-8")
    assert "callReadTool" in source, "the read retry is gone"
    read_calls = source.count("callReadTool(TOOLS.misakanet_")
    assert read_calls >= 4, read_calls
    # No upload path may go through the retry helper.
    assert "callReadTool(TOOLS.misakanet_submit_intake" not in source


def test_the_two_channels_keep_separate_version_slots():
    """The versions are deliberately offset: one channel must never take the other's slot."""
    official = manifest(OFFICIAL)["version"]
    community = manifest(COMMUNITY)["version"]
    assert official != community, (official, community)


def test_the_community_package_carries_the_official_fixes():
    """Every fix the official channel has must be in the community channel too.

    This is the gate that would have caught the 2026-11-11 drift: the community build was cut
    from an older base and shipped without the trust_notice marking, the awaited replies and the
    `new_lesson_candidate` classification while the official build had them.
    """
    official = (OFFICIAL / "main.js").read_text(encoding="utf-8")
    community = (COMMUNITY / "main.js").read_text(encoding="utf-8")
    for marker, minimum in (
        ("UNTRUSTED_NOTICE", 7),
        ("new_lesson_candidate", 1),
        ("kind_filtered_empty", 1),
        ("return await fail(", 6),
        ("return await sendResult(", 5),
    ):
        count = community.count(marker)
        assert count >= minimum, f"{marker}: community has {count}, need at least {minimum}"
        assert count >= official.count(marker), (
            f"{marker}: official has {official.count(marker)}, community has {count} — "
            "the community channel fell behind"
        )


def test_the_community_version_constant_matches_its_manifest():
    source = (COMMUNITY / "main.js").read_text(encoding="utf-8")
    match = re.search(r"const PLUGIN_VERSION = '([^']+)'", source)
    assert match, "PLUGIN_VERSION is gone from the community main.js"
    assert match.group(1) == manifest(COMMUNITY)["version"]


def test_the_community_manual_documents_the_card_gate():
    manual = (COMMUNITY / "manual" / "misakanet" / "MANUAL.md").read_text(encoding="utf-8")
    assert "确认卡" in manual, "the community manual does not document the confirmation card"
    assert "confirm" in manual, "the community manual does not document the confirm argument"
    assert "30" in manual, "the give-up window is not documented"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is what parses the entry point")
def test_the_community_entry_point_parses():
    node = shutil.which("node")
    done = subprocess.run(
        [node, "--check", str(COMMUNITY / "main.js")], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr


def test_every_locale_file_the_manifest_names_exists():
    entry = manifest(COMMUNITY)
    for lang, rel in entry["locales"].items():
        path = COMMUNITY / rel
        assert path.exists(), f"locale:{lang} → {path} does not exist"
        doc = json.loads(path.read_text(encoding="utf-8"))
        for key in ("name", "description", "whenToUse"):
            assert isinstance(doc.get(key), str) and doc[key].strip(), f"{lang}.{key}"
        for tool in entry["tools"]:
            value = doc["tools"][tool["name"]]
            assert isinstance(value, dict), f"{lang}.tools.{tool['name']} must be an object"
            assert value["description"].strip(), f"{lang}.tools.{tool['name']}.description"
            # The manifest's own limit is 1024 characters per tool description.
            assert len(value["description"]) <= 1024, (
                f"{lang}.tools.{tool['name']}.description is {len(value['description'])} characters"
            )


def test_the_storage_disclosure_reaches_both_channels():
    """The market review asked for the private directory to be described as it is.

    `did-turn-end` writes a per-session turn counter and the announcement state into
    `checkpoint.json` next to the client id. Wherever the copy says the private directory
    holds "only a client id" — the manifest description and every locale's search tool text —
    it has to name the counter as well, in that language.
    """
    counters = {
        "zh-CN": "轮次计数",
        "en": "turn counter",
        "ja": "ターン数",
        "ko": "턴 수",
    }
    for base in (OFFICIAL, COMMUNITY):
        description = manifest(base)["description"]
        assert "只留" in description, f"{base.name}: the manifest description must say what stays local"
        assert counters["zh-CN"] in description, f"{base.name}: the manifest must name the counter"
        for lang, word in counters.items():
            doc = json.loads((base / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
            tools = doc["tools"]
            entry = tools["misakanet_search"] if isinstance(tools, dict) else [
                t for t in tools if t["name"] == "misakanet_search"
            ][0]
            text = entry["description"] if isinstance(entry, dict) else entry
            assert word in text, f"{base.name}/{lang}: the search tool text must name the counter"


def test_the_kind_filter_only_hides_hits_when_there_were_hits():
    """`kind_filtered_empty` must not swallow a genuine zero hit (the market review's finding)."""
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "matchedBeforeFilter > 0" in source, f"{base.name}: the kind filter lost its condition"


def test_the_publisher_key_is_published_and_self_consistent():
    """The public key is the stamp users check the marketplace package against.

    It is published in the repository so anyone can verify a package's signature and so the
    official trust table can be extended with it. The keyId is not a separate fact: it is
    `sha256(SPKI DER)` truncated — so the two must agree, or the stamp does not check out.
    """
    import base64
    import hashlib

    key = json.loads(
        (REPO / "docs" / "integrations" / "cindy-publisher-key.json").read_text(encoding="utf-8")
    )
    spki = base64.b64decode(key["publicKey"])
    assert key["algorithm"] == "ed25519"
    assert key["keyId"] == "ed25519:" + hashlib.sha256(spki).hexdigest()[:32], (
        "the published keyId is not derived from the published public key"
    )
    # The signing tool has to be in the repository too, or the key is a stamp with no press.
    assert (REPO / "scripts" / "sign-plugin-package.mjs").exists()


def test_the_endpoint_cannot_hand_over_a_user_confirmed_flag():
    """The endpoint's routing advice is external data.

    `intake.args` used to be forwarded as-is, so a remote payload carrying `user_confirmed: true`
    reached the agent as "the user already confirmed this" — and the next call published text the
    user never saw as an irreversible public issue. Only the routing field may cross.
    """
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "Object.assign(rawKind ? { kind: rawKind } : {}, { source: 'cindy' })" in source, (
            f"{base.name}: the intake args still carry the endpoint's fields"
        )
        assert "Object.assign({}, rawIntake.args || {}" not in source, (
            f"{base.name}: the endpoint's intake args are still forwarded wholesale"
        )
