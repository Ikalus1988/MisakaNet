"""Tests for search_config module (Issue #1220)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from scripts.search_config import SearchConfig, get_search_config, _load_config_from_yaml


def test_default_config():
    """Default weights should be 0.65/0.20/0.15."""
    cfg = SearchConfig()
    assert cfg.bm25_weight == 0.65
    assert cfg.metadata_weight == 0.20
    assert cfg.baseline_weight == 0.15
    assert cfg.rrf_k == 60


def test_validate_valid():
    """Valid config should have no errors."""
    cfg = SearchConfig()
    assert cfg.validate() == []


def test_validate_invalid_sum():
    """Weights not summing to 1.0 should fail."""
    cfg = SearchConfig(bm25_weight=0.8, metadata_weight=0.2, baseline_weight=0.2)
    errors = cfg.validate()
    assert len(errors) == 1
    assert "sum to 1.0" in errors[0]


def test_validate_negative_weight():
    """Negative weight should fail."""
    cfg = SearchConfig(bm25_weight=-0.1, metadata_weight=0.6, baseline_weight=0.5)
    errors = cfg.validate()
    assert len(errors) == 1
    assert "0-1" in errors[0]


def test_validate_rrf_k():
    """rrf_k < 1 should fail."""
    cfg = SearchConfig(rrf_k=0)
    errors = cfg.validate()
    assert len(errors) == 1
    assert "rrf_k" in errors[0]


def test_load_from_yaml(tmp_path):
    """Load weights from config.yaml."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "search:\n"
        "  bm25_weight: 0.70\n"
        "  metadata_weight: 0.15\n"
        "  baseline_weight: 0.15\n"
        "  rrf_k: 100\n"
    )
    # Monkey-patch CONFIG_FILE
    import scripts.search_config as mod
    old_file = mod.CONFIG_FILE
    mod.CONFIG_FILE = config_file
    try:
        cfg = _load_config_from_yaml()
        assert cfg["bm25_weight"] == "0.70"
        assert cfg["rrf_k"] == "100"
    finally:
        mod.CONFIG_FILE = old_file


def test_load_from_env(monkeypatch):
    """Env vars should override yaml."""
    monkeypatch.setenv("MISAKA_SEARCH_BM25_WEIGHT", "0.55")
    monkeypatch.setenv("MISAKA_SEARCH_RRF_K", "30")
    cfg = get_search_config()
    # Env overrides should be applied (but we can't test full integration
    # without mocking _cached_config)
    from scripts.search_config import _load_config_from_env
    env_cfg = _load_config_from_env()
    assert env_cfg["bm25_weight"] == "0.55"
    assert env_cfg["rrf_k"] == "30"


def test_config_no_yaml(tmp_path):
    """Missing config.yaml should use defaults."""
    import scripts.search_config as mod
    old_file = mod.CONFIG_FILE
    mod.CONFIG_FILE = tmp_path / "nonexistent.yaml"
    try:
        result = _load_config_from_yaml()
        assert result is None
    finally:
        mod.CONFIG_FILE = old_file


if __name__ == "__main__":
    test_default_config()
    test_validate_valid()
    test_validate_invalid_sum()
    test_validate_negative_weight()
    test_validate_rrf_k()
    test_config_no_yaml(Path(tempfile.mkdtemp()))
    print("All tests passed ✓")
