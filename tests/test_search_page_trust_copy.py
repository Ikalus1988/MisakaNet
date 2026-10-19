"""The search page must not claim verification the corpus does not have (#3539 D1).

The defect was a keyword heuristic that fell through to a green "Verified" badge and never read
`evidence_level`, while the card already printed its E0-E4 grade beside it. 241 of 388 "Verified"
cards were E0. A page title saying "Search Verified Failure Lessons" made the same claim one level
up, in both languages.

These assertions are copy-level on purpose: the next person to add a badge needs the page to fail
before it ships the same sentence again.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "docs" / "search" / "index.html").read_text(encoding="utf-8")
LOCALES = {lang: (ROOT / "docs" / "locales" / f"{lang}.json").read_text(encoding="utf-8")
           for lang in ("en", "zh")}


def test_the_kind_badge_never_falls_through_to_verified():
    assert "badgeVerified" not in PAGE, (
        "the unclassified badge is a failure *kind*, not a trust claim — the trust claim is the "
        "E-level badge on the same card"
    )
    assert "badgeOther" in PAGE


def test_the_page_does_not_call_the_corpus_verified_in_either_language():
    for text, lang in ((PAGE, "page"), (LOCALES["en"], "en"), (LOCALES["zh"], "zh")):
        assert "Verified Failure Lessons" not in text, lang
        assert "已验证失败教训" not in text, lang


def test_the_two_languages_describe_the_page_the_same_way():
    # `tests/test_site_i18n.py` checks key parity, not meaning; this is the meaning.
    import json
    en = json.loads(LOCALES["en"])
    zh = json.loads(LOCALES["zh"])
    assert "verified" not in en["searchPanelTitle"].lower()
    assert "已验证" not in zh["searchPanelTitle"]
