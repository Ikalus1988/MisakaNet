"""`config.yaml.example` must describe the keys the code actually reads — and only those.

Why this exists (2026-11-14)
----------------------------
The example had drifted into two contradictory halves. `config.yaml.example` was a 1.7 KB legacy
Hub template — `hub/`, `sync/`, `storage.graph|vector|arbitration`, `notifier.*`, `master.*` — for
a subsystem deleted on 2026-08-31, and it was **missing** `feishu.webhook_url`, the one key
`misakanet/scripts/draft_reminder.py` reads. A second file, `config.example.yaml`, carried the
`search:` weights — the section `scripts/search_config.py` does read — and nothing linked it.

So a reader copying the example got keys nothing reads and lost the one key something does. Two
`setup.py` copies the file verbatim into `config.yaml`, so the drift was delivered by the shipped
wizard, not just by a stale doc.

What this gate holds
--------------------
1. Every `search:` key in the example is one the YAML layer applies. `SearchConfig` has
   `cross_encoder_weight` / `bm25_rerank_weight`, but only their environment variables reach it —
   listing them in YAML would be configuration that does nothing.
2. The example's `search:` values pass `SearchConfig.validate()` (the weights sum to 1.0).
3. `feishu.webhook_url` is present, because dropping it silently downgrades the draft reminder to
   stdout.
4. None of the retired Hub sections come back.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "config.yaml.example"

# The four keys `_load_config_from_yaml()` applies. The two rerank weights are deliberately absent:
# `get_search_config()` reads them from the environment layer only.
YAML_APPLIED = {"bm25_weight", "metadata_weight", "baseline_weight", "rrf_k"}

# Sections of the retired Hub prototype (deleted 2026-08-31). Their return would be a regression:
# they look configurable, and nothing reads them.
RETIRED_SECTIONS = ("hub:", "sync:", "storage:", "notifier:", "master:")


def test_the_example_exists_and_the_wizard_template_is_the_only_one():
    assert EXAMPLE.exists(), "setup.py copies config.yaml.example into config.yaml"
    assert not (REPO / "config.example.yaml").exists(), (
        "two examples meant one of them was wrong; the search weights belong in config.yaml.example"
    )


def test_every_search_key_in_the_example_is_one_the_yaml_layer_applies():
    import scripts.search_config as mod

    old_file = mod.CONFIG_FILE
    mod.CONFIG_FILE = EXAMPLE
    try:
        loaded = mod._load_config_from_yaml() or {}
    finally:
        mod.CONFIG_FILE = old_file

    assert loaded, "the example must carry a search: section with at least the three weights"
    extra = set(loaded) - YAML_APPLIED
    assert not extra, (
        f"these keys read as configuration but the YAML layer ignores them: {sorted(extra)}. "
        "Use the MISAKA_SEARCH_* environment variables for them instead."
    )


def test_the_example_parses_to_a_valid_config():
    from scripts.search_config import SearchConfig

    import scripts.search_config as mod

    old_file = mod.CONFIG_FILE
    mod.CONFIG_FILE = EXAMPLE
    try:
        loaded = mod._load_config_from_yaml() or {}
    finally:
        mod.CONFIG_FILE = old_file

    assert {"bm25_weight", "metadata_weight", "baseline_weight"} <= set(loaded), (
        "the three weights that must sum to 1.0 all belong in the example"
    )
    cfg = SearchConfig()
    for key in ("bm25_weight", "metadata_weight", "baseline_weight"):
        setattr(cfg, key, float(loaded[key]))
    cfg.rrf_k = int(loaded["rrf_k"])
    assert cfg.validate() == [], f"the example's own values do not validate: {cfg.validate()}"


def test_the_feishu_key_that_has_a_reader_is_in_the_example():
    # The reader, not the prose, is the authority on the key name.
    reader = (REPO / "misakanet" / "scripts" / "draft_reminder.py").read_text(encoding="utf-8")
    assert 'cfg.get("feishu", {}).get("webhook_url", "")' in reader, (
        "draft_reminder.py changed how it reads the webhook — update this test and the example together"
    )
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "feishu:" in text and "webhook_url" in text, (
        "the example must carry the one config.yaml key that has a reader"
    )


@pytest.mark.parametrize("section", RETIRED_SECTIONS)
def test_the_retired_hub_sections_do_not_come_back(section):
    text = EXAMPLE.read_text(encoding="utf-8")
    # Commented-out mentions are fine (the file explains why they are gone); a real key is not.
    live = [line for line in text.splitlines()
            if line.split("#", 1)[0].strip() == section]
    assert not live, f"{section} belongs to the Hub prototype deleted on 2026-08-31"
