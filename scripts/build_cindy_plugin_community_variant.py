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
COMMUNITY_VERSION = "1.5.22"  # 1.5.15 被审核退回（版本号已烧掉）→ 这一版走 1.5.16

#: The community channel's own release story. The official package carries the official one.
COMMUNITY_RELEASE_NOTES = (
    '这一版只改文档：随包手册补回与代码一致（相对上一上架的 1.5.21）。手册 §5.6.1 之前还在描述 1.5.17 之前那套旧闸门——「30 秒等不到点击就放弃」「改走 confirm=direct」「点击后要换一个新的在途调用号」「手机端按钮点不动」。这些在 1.5.20 之后都已经不成立：现在是一次点击就能走通（手机、桌面都行），票据一次性、15 分钟、绑定那一版原文。§5.8 也改成实情：插件不再假装在轮末替你查语料（那条路在宿主规则下必然失败），改成把失败交给下一轮的 agent、由它用自己的在途调用去查。功能与上报流程没有任何变化。**从市场装的版本会自动更新；从 .cindy 文件装的不会**。版本号继续与官方通道错开。'
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


def package_files(base: Path) -> list[Path]:
    """The files that actually go into a package (the packer's rule, in one place).

    A leftover `.cindy` package or the publisher signature in the source directory is **not** part
    of the package — comparing raw directory listings would report drift that isn't drift.
    """
    return sorted(
        (
            p
            for p in base.rglob("*")
            if p.is_file()
            and not p.name.startswith(".")
            and not p.name.endswith(".cindy")
            and p.name != "cindy-signatures.json"
            and p.name not in {".git", "node_modules", "__MACOSX"}
        ),
        key=lambda p: p.relative_to(base).as_posix(),
    )


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
    official_files = [p.relative_to(OFFICIAL).as_posix() for p in package_files(OFFICIAL)]
    community_files = [p.relative_to(TARGET).as_posix() for p in package_files(TARGET)]
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
