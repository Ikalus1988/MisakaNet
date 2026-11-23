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


def test_both_packages_declare_the_card_gate():
    """The card gate needs a `card` declaration: without it, `confirm` means nothing."""
    for base in (OFFICIAL, COMMUNITY):
        entry = manifest(base)
        assert entry.get("card") is not None, f"{base.name} lost its card declaration"
        source = (base / "main.js").read_text(encoding="utf-8")
        for marker in ("supplyIntakeCard", "handleCardAction", "CARD_CONFIRM_TIMEOUT_MS"):
            assert marker in source, f"{base.name} lost {marker}"


def test_the_read_retry_only_covers_reads():
    """The retry is for flaky reads. A retried *upload* would publish the same issue twice."""
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "callReadTool" in source, f"{base.name} lost the read retry"
        read_calls = source.count("callReadTool(TOOLS.misakanet_")
        assert read_calls >= 4, read_calls
        # No upload path may go through the retry helper.
        assert "callReadTool(TOOLS.misakanet_submit_intake" not in source


def test_the_two_channels_keep_separate_version_slots():
    """The versions are deliberately offset: one channel must never take the other's slot."""
    official = manifest(OFFICIAL)["version"]
    community = manifest(COMMUNITY)["version"]
    assert official != community, (official, community)


def test_the_two_packages_are_one_implementation():
    """The community package is a thin shell over the official one: identical but for three things.

    The community build used to be an older variant with two extra features (the read retry and
    the confirmation card), and keeping the two in sync was guarded by counting markers. Both
    features are in the official source now, so the guard is byte-level: **if the two packages
    differ anywhere except the channel header, the version and the release notes, this fails.**
    """
    # The **package** file set, not the raw directory: a leftover `.cindy` package or the publisher
    # signature is not part of the package, and comparing raw listings would report drift that
    # isn't drift (the packer skips exactly these).
    def package_files(base: Path) -> list[str]:
        return sorted(
            p.relative_to(base).as_posix()
            for p in base.rglob("*")
            if p.is_file()
            and not p.name.startswith(".")
            and not p.name.endswith(".cindy")
            and p.name != "cindy-signatures.json"
            and p.name not in {".git", "node_modules", "__MACOSX"}
        )

    official_files = package_files(OFFICIAL)
    community_files = package_files(COMMUNITY)
    assert official_files == community_files, (
        f"file sets differ: only in official {set(official_files) - set(community_files)}, "
        f"only in community {set(community_files) - set(official_files)}"
    )
    for name in official_files:
        left = (OFFICIAL / name).read_bytes()
        right = (COMMUNITY / name).read_bytes()
        if left == right:
            continue
        assert name in {"main.js", "ghost.json"}, (
            f"{name} differs between the two channels but is not one of the three substitutions"
        )
        if name == "main.js":
            left_lines = left.decode("utf-8").splitlines()
            right_lines = right.decode("utf-8").splitlines()
            differing = [(a, b) for a, b in zip(left_lines, right_lines) if a != b]
            assert len(left_lines) == len(right_lines) and len(differing) == 2, (
                f"main.js may differ in exactly two lines (channel header, version), "
                f"got {len(differing)}: {differing}"
            )
            assert any("X-MisakaNet-Channel" in a for a, _ in differing), differing
            assert any("PLUGIN_VERSION" in a for a, _ in differing), differing
        else:
            official_manifest = json.loads(left.decode("utf-8"))
            community_manifest = json.loads(right.decode("utf-8"))
            differing_keys = {
                key for key in set(official_manifest) | set(community_manifest)
                if official_manifest.get(key) != community_manifest.get(key)
            }
            assert differing_keys <= {"version", "releaseNotes"}, differing_keys


def test_the_two_channels_say_their_own_channel():
    """Each package declares the channel it is on: the endpoint compares against the right line."""
    for base, channel in ((OFFICIAL, "official"), (COMMUNITY, "community")):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert f"'X-MisakaNet-Channel': '{channel}'" in source, (
            f"{base.name} does not declare its channel ({channel})"
        )


def test_the_version_constant_matches_its_manifest():
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        match = re.search(r"const PLUGIN_VERSION = '([^']+)'", source)
        assert match, f"PLUGIN_VERSION is gone from {base.name}/main.js"
        assert match.group(1) == manifest(base)["version"], base.name


def test_both_manuals_document_the_card_gate():
    for base in (OFFICIAL, COMMUNITY):
        manual = (base / "manual" / "misakanet" / "MANUAL.md").read_text(encoding="utf-8")
        assert "确认卡" in manual, f"{base.name} does not document the confirmation card"
        assert "confirm" in manual, f"{base.name} does not document the confirm argument"
        assert "30" in manual, f"{base.name} does not document the give-up window"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is what parses the entry point")
def test_both_entry_points_parse():
    node = shutil.which("node")
    for base in (OFFICIAL, COMMUNITY):
        done = subprocess.run(
            [node, "--check", str(base / "main.js")], capture_output=True, text=True
        )
        assert done.returncode == 0, done.stderr


def test_every_locale_file_the_manifest_names_exists():
    for base in (OFFICIAL, COMMUNITY):
        entry = manifest(base)
        for lang, rel in entry["locales"].items():
            path = base / rel
            assert path.exists(), f"{base.name} locale:{lang} → {path} does not exist"
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


def test_the_disclosure_names_both_halves_in_every_language():
    """Two different facts, and the copy has to name both.

    The random client id and the OS tag go to the endpoint on every request (it counts distinct
    clients) — they are not local-only; the per-session turn counter stays in the private
    directory and is never uploaded. A draft that fixed the second half while dropping the first
    is exactly what the market review caught.
    """
    counters = {"zh-CN": "轮次计数", "en": "turn counter", "ja": "ターン数", "ko": "턴 수"}
    sent = {"zh-CN": "发给端点", "en": "go to the endpoint", "ja": "端点へ送られ", "ko": "엔드포인트로 전송"}
    for base in (OFFICIAL, COMMUNITY):
        description = manifest(base)["description"]
        assert counters["zh-CN"] in description, f"{base.name}: the description must name the counter"
        assert sent["zh-CN"] in description, f"{base.name}: the description must say what is sent"
        assert "随机客户端 id" in description, f"{base.name}: the description must name the client id"
        for lang in counters:
            doc = json.loads((base / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
            tools = doc["tools"]
            entry = tools["misakanet_search"] if isinstance(tools, dict) else [
                t for t in tools if t["name"] == "misakanet_search"
            ][0]
            text = entry["description"] if isinstance(entry, dict) else entry
            assert counters[lang] in text, f"{base.name}/{lang}: must name the counter"
            assert sent[lang] in text, f"{base.name}/{lang}: must say what is sent"
            # `whenToUse` is how a model finds the preflight tool.
            assert re.search(r"高风险|high-risk|risky operation|高リスク|고위험", doc["whenToUse"]), (
                f"{base.name}/{lang}: whenToUse must mention risky operations"
            )


def test_a_kind_filtered_empty_result_carries_no_intake():
    """The filtered-empty branch is not a knowledge gap; the endpoint's intake must not ride along."""
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "kindFilteredEmpty ? undefined : (suggestion || undefined)" in source, (
            f"{base.name}: the filtered-empty branch still carries the endpoint's suggestion"
        )
        assert "kindFilteredEmpty ? undefined : intake" in source, (
            f"{base.name}: the filtered-empty branch still carries the endpoint's intake"
        )


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


def test_the_pre_send_failures_report_not_sent():
    """The irreversible tool promises three states on every failure path."""
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "'CONFIRM_REQUIRED'" in source, f"{base.name}: CONFIRM_REQUIRED is gone"
        assert "'MISSING_PROBLEM'," in source, f"{base.name}: MISSING_PROBLEM is gone"
        # Both pre-send failures must carry the delivery state (three states, every path).
        assert source.count("'not_sent'") >= 3, (
            f"{base.name}: the two pre-send failures must report not_sent"
        )


def test_the_intake_tool_name_is_pinned():
    """A tampered endpoint must not be able to point the agent at another installed tool."""
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "tool: 'misakanet_submit_intake'," in source, f"{base.name}: the tool name must be pinned"
        assert "asString(rawIntake.tool)" not in source, (
            f"{base.name}: the endpoint must not choose the local tool name"
        )


def test_the_manifest_default_copy_matches_the_zh_cn_locale():
    """The manifest's default tool description is the Chinese fallback — it must be the same text.

    2026-11-12: the manifest still said "the private directory holds only a client id and a turn
    counter", while every locale said the client id goes to the endpoint and only the counter stays
    local. The locales were right, the manifest was stale, and nothing noticed: the two copies are
    maintained by hand. This gate is that hand-check, run every time.
    """
    for base in (OFFICIAL, COMMUNITY):
        manifest_entry = manifest(base)
        locale = json.loads((base / "locales" / "zh-CN.json").read_text(encoding="utf-8"))
        for tool in manifest_entry["tools"]:
            default = tool["description"]
            localized = locale["tools"][tool["name"]]["description"]
            assert default == localized, (
                f"{base.name}/{tool['name']}: the manifest default copy and the zh-CN locale copy "
                "have drifted apart — the manifest is what a reader without a locale gets"
            )


def test_the_tracked_session_list_is_bounded():
    """Unbounded session state grows the file and the per-turn I/O without limit."""
    for base in (OFFICIAL, COMMUNITY):
        source = (base / "main.js").read_text(encoding="utf-8")
        assert "MAX_TRACKED_SESSIONS" in source, f"{base.name}: the session list must have a bound"
        assert "pruneSessions(state)" in source, f"{base.name}: the session list must be pruned"
