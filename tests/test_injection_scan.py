from pathlib import Path

from scripts.injection_scan import findings


def test_public_docs_are_clean():
    assert findings() == []


def test_detects_private_key_and_assignment(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "public.md").write_text(
        "-----BEGIN RSA PRIVATE KEY-----\napi_key = '123456789012'\n",
        encoding="utf-8",
    )
    assert findings((docs,)) == [f"{docs / 'public.md'}:1", f"{docs / 'public.md'}:2"]


def test_ignores_private_handoff_file(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "handoff-round.md").write_text(
        "password: intentionally-private-placeholder\n", encoding="utf-8"
    )
    assert findings((docs,)) == []
