#!/usr/bin/env python3
"""The two dictionaries must stay in step, and every key the code asks for must exist in both.

`lib/client.js` carries its dictionaries inline — `locale/*.json` are the *package metadata* the host reads
for the plugin page's title and description (`dsh-app-boot`'s `dictionariesOf`), not the UI copy, which goes
through `ctx.locale`. Two failure modes are silent: a key added to English only (a Chinese reader gets the
English string, or the raw key), and a `T("…")` call whose key was never added at all (the surface shows the
key). Both are caught here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLIENT = REPO / "lib/client.js"


def _dict_blocks() -> tuple[str, str]:
    text = CLIENT.read_text(encoding="utf-8")
    en = re.search(r"\n\t\tvar en = \{(.*?)\n\t\t\};", text, re.S)
    zh = re.search(r"\n\t\tvar zh = \{(.*?)\n\t\t\};", text, re.S)
    assert en, "the English dictionary is no longer a `var en = {…}` block"
    assert zh, "the Chinese dictionary is no longer a `var zh = {…}` block"
    return en.group(1), zh.group(1)


def _keys(block: str) -> set[str]:
    return set(re.findall(r'"([a-z][\w.]*)":\s*"', block))


def test_both_dictionaries_declare_the_same_keys():
    en, zh = _dict_blocks()
    en_keys, zh_keys = _keys(en), _keys(zh)
    assert en_keys, "the English dictionary is empty"
    assert en_keys == zh_keys, (
        f"missing from zh: {sorted(en_keys - zh_keys)}; missing from en: {sorted(zh_keys - en_keys)}")


def test_every_key_the_code_asks_for_exists():
    text = CLIENT.read_text(encoding="utf-8")
    asked = set(re.findall(r'T\(\s*"([a-z][\w.]*)"', text))
    en_keys = _keys(_dict_blocks()[0])
    assert asked, "no `T(\"key\")` calls found; the wiring moved"
    assert asked <= en_keys, f"asked for but never declared: {sorted(asked - en_keys)}"


def test_package_metadata_is_localized():
    """The plugin page's title and description come from these files, one per language."""
    for lang in ("en", "zh"):
        path = REPO / "locale" / f"{lang}.json"
        assert path.is_file(), f"{path.relative_to(REPO)} is missing (the host reads ./locale/*.json)"
        meta = json.loads(path.read_text(encoding="utf-8")).get("meta", {})
        assert meta.get("title") and meta.get("description"), f"{lang}.json needs meta.title and meta.description"
    zh_title = json.loads((REPO / "locale/zh.json").read_text(encoding="utf-8"))["meta"]["title"]
    assert any("\u4e00" <= ch <= "\u9fff" for ch in zh_title), "the Chinese metadata is not in Chinese"


def test_the_locale_files_ship():
    """`files` decides what npm publishes; a locale folder left out is a localization nobody receives."""
    listed = json.loads((REPO / "package.json").read_text(encoding="utf-8")).get("files", [])
    assert "locale/" in listed or "locale" in listed, f"package.json files does not include locale/: {listed}"
