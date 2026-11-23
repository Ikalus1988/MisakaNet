#!/usr/bin/env python3
"""Build `.cindy-plugin-community/` = the official plugin source + three substitutions.

The community channel (Cindy marketplace, personal submission) and the official channel (the
official plugin repo, platform-signed) ship **the same implementation**. They differ in exactly
three places, and this script is what keeps them that way:

1. `X-MisakaNet-Channel: official` → `community` — which version line the endpoint compares against;
2. `PLUGIN_VERSION` / `ghost.json` `version` — the two lines are deliberately offset (official 1.6.x,
   community 1.5.x) so neither channel takes the other's version slot;
3. `releaseNotes` — each channel's own release story.

Why a script at all, and why this one
------------------------------------
Before 2026-11-20 the community build was the *older* one and the official build was "the new one
minus two features": the community package had a conservative read retry and an interactive
confirmation card, the official package did not. That meant the two had to be kept in sync by hand,
and the drift was guarded by ~300 lines of marker-counting tests plus ~700 lines of patch
substitutions. Two fixes landed on the two channels at once, in both directions, and the guard was
what caught it.

Both features are now in the single official source (`.cindy-plugin/`), so the community package is
a **thin shell** over it: copy, substitute three things, and assert that nothing else differs.
The drift guard is now byte-level instead of marker-level: if the two packages are not identical
except for those three substitutions, the build fails.

What this script does NOT do
----------------------------
It does not publish. The community channel goes out through the client (prepare → submit → review);
the official channel goes out through the official repo's pipeline. Both are separate destinations —
see the official repo's README: "官方仓插件走上文的 PR 流程；客户端社区投稿和组织发布是其它目标".

Run: python scripts/build_cindy_plugin_community_variant.py
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OFFICIAL = REPO / ".cindy-plugin"
TARGET = REPO / ".cindy-plugin-community"

#: The community channel's version line. Deliberately offset from the official one (1.6.x) so the
#: two channels never take the same version slot on the same plugin id. Bump it when the community
#: package is published; keep it below the official line.
COMMUNITY_VERSION = "1.5.13"  # the published community release is 1.5.12; this is the next one

#: The community channel's own release story. The official package carries the official one.
COMMUNITY_RELEASE_NOTES = (
    "这一版修掉确认卡闸门里的四处缺陷（维护者 2026-11-23 点的名，社区通道的既有问题）："
    "一是**点击之后那次上报改用新的在途调用号**——卡片的归因号属于已经结卷的那次工具调用，"
    "复用它宿主会拒，于是点「确认提交」根本发不出去；"
    "二是**超时不再发第二个回执**——原调用已经结卷，同一个调用号上的第二个回执同样会被拒，"
    "超时的结论只落在卡上（第一次回执里已写明「等不到点击就改走 confirm=direct」）；"
    "三是**直接重发会作废上一张还开着的卡**——否则旧卡的 30 秒定时器照样触发、旧卡上的"
    "「确认提交」按钮还能点，那会把一份已经过期的原文发成公开 issue；"
    "四是**私有目录写不进去时不再发一个「每次会话都变」的假客户端标识**（改为不带这个标识，"
    "宁可没有，也不要一个会把端点的独立客户端数算歪、把复用证据稀释掉的假 id）。"
    "另：只读调用的一次保守重试与上报前的交互卡确认闸门现在两条通道共用同一份实现。"
    "版本号与官方通道继续刻意错开（官方 1.6.x / 社区 1.5.x）。"
)

#: The three substitutions, as (label, file, pattern, replacement).
SUBS = [
    ("channel header", "main.js", r"'X-MisakaNet-Channel': 'official'", "'X-MisakaNet-Channel': 'community'"),
    ("version constant", "main.js", r"const PLUGIN_VERSION = '[^']+';", f"const PLUGIN_VERSION = '{COMMUNITY_VERSION}';"),
]


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    """Replace exactly one occurrence; a silent no-op here is how the two channels drift."""
    found = len(re.findall(pattern, text))
    assert found == 1, f"{label}: expected 1 occurrence of {pattern!r}, found {found}"
    return re.sub(pattern, replacement, text, count=1)


def build() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(OFFICIAL, TARGET, ignore=shutil.ignore_patterns("*.cindy", "cindy-signatures.json"))

    main_path = TARGET / "main.js"
    text = main_path.read_text(encoding="utf-8")
    for label, _, pattern, replacement in SUBS:
        text = sub_once(text, pattern, replacement, label)
    main_path.write_text(text, encoding="utf-8", newline="\n")

    manifest_path = TARGET / "ghost.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = COMMUNITY_VERSION
    manifest["releaseNotes"] = COMMUNITY_RELEASE_NOTES
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    official_manifest = json.loads((OFFICIAL / "ghost.json").read_text(encoding="utf-8"))
    assert manifest["id"] == official_manifest["id"], "the two channels must be the same plugin id"
    assert manifest["version"] != official_manifest["version"], (
        "the two channels must not take the same version slot"
    )
    print(
        f"community built: version {manifest['version']} (official {official_manifest['version']}), "
        f"channel community"
    )


def assert_only_three_differences() -> None:
    """The build's own contract: the two packages differ in the three substitutions and nothing else.

    This is the guard that replaced the marker-counting tests. It compares the two trees file by
    file, so a stray edit on either side is caught here rather than in a marketplace review.
    """
    official_files = sorted(p.relative_to(OFFICIAL).as_posix() for p in OFFICIAL.rglob("*") if p.is_file())
    community_files = sorted(p.relative_to(TARGET).as_posix() for p in TARGET.rglob("*") if p.is_file())
    assert official_files == community_files, (
        f"file sets differ: only in official {set(official_files) - set(community_files)}, "
        f"only in community {set(community_files) - set(official_files)}"
    )
    allowed = {"main.js", "ghost.json"}
    for name in official_files:
        left_bytes = (OFFICIAL / name).read_bytes()
        right_bytes = (TARGET / name).read_bytes()
        if left_bytes == right_bytes:
            continue
        assert name in allowed, f"{name} differs between the two channels but is not a substitution"
        if name == "main.js":
            left = left_bytes.decode("utf-8").splitlines()
            right = right_bytes.decode("utf-8").splitlines()
            differing = [(a, b) for a, b in zip(left, right) if a != b]
            assert len(left) == len(right) and len(differing) == 2, (
                f"main.js may differ in exactly two lines (channel header, version), got {len(differing)}"
            )
            assert any("X-MisakaNet-Channel" in a for a, _ in differing), differing
            assert any("PLUGIN_VERSION" in a for a, _ in differing), differing
        else:  # ghost.json — version and releaseNotes
            official_manifest = json.loads(left_bytes.decode("utf-8"))
            community_manifest = json.loads(right_bytes.decode("utf-8"))
            differing_keys = {
                key for key in set(official_manifest) | set(community_manifest)
                if official_manifest.get(key) != community_manifest.get(key)
            }
            assert differing_keys <= {"version", "releaseNotes"}, differing_keys
    print("drift check: the two packages differ only in channel, version and release notes")


if __name__ == "__main__":
    build()
    assert_only_three_differences()
