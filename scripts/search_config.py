#!/usr/bin/env python3
"""Search configuration — configurable weights for BM25/vector hybrid scoring.

Reads from config.yaml (if present) or uses defaults.

Usage:
    from scripts.search_config import get_search_config
    config = get_search_config()
    print(config.bm25_weight)  # 0.65
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = REPO_ROOT / "config.yaml"


@dataclass
class SearchConfig:
    """Search scoring weights and parameters."""
    bm25_weight: float = 0.65
    metadata_weight: float = 0.20
    baseline_weight: float = 0.15
    rrf_k: int = 60  # Reciprocal Rank Fusion constant (for future vector hybrid)
    cross_encoder_weight: float = 0.70  # Cross-encoder rerank weight
    bm25_rerank_weight: float = 0.30  # BM25 rerank weight

    def validate(self) -> list[str]:
        """Validate weights. Returns list of errors (empty = valid)."""
        errors = []
        total = self.bm25_weight + self.metadata_weight + self.baseline_weight
        if abs(total - 1.0) > 0.01:
            errors.append(f"Weights must sum to 1.0, got {total:.3f}")
        for name, val in [
            ("bm25_weight", self.bm25_weight),
            ("metadata_weight", self.metadata_weight),
            ("baseline_weight", self.baseline_weight),
            ("cross_encoder_weight", self.cross_encoder_weight),
            ("bm25_rerank_weight", self.bm25_rerank_weight),
        ]:
            if val < 0 or val > 1:
                errors.append(f"{name} must be 0-1, got {val}")
        if self.rrf_k < 1:
            errors.append(f"rrf_k must be >= 1, got {self.rrf_k}")
        return errors


def _load_config_from_yaml() -> Optional[dict]:
    """Try to load search config from config.yaml."""
    if not CONFIG_FILE.exists():
        return None
    try:
        # Simple YAML-like parser for search section (avoid pyyaml dependency)
        text = CONFIG_FILE.read_text(encoding="utf-8")
        in_search = False
        config = {}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "search:":
                in_search = True
                continue
            if in_search:
                if stripped and not stripped.startswith("#") and ":" in stripped:
                    key, val = stripped.split(":", 1)
                    key = key.strip()
                    val = val.strip().split("#")[0].strip()  # strip inline comments
                    config[key] = val
                elif stripped and not stripped.startswith(" ") and not stripped.startswith("\t"):
                    break  # exited search section
        return config if config else None
    except Exception:
        return None


def _load_config_from_env() -> dict:
    """Load search config from environment variables."""
    config = {}
    for key, env_key in [
        ("bm25_weight", "MISAKA_SEARCH_BM25_WEIGHT"),
        ("metadata_weight", "MISAKA_SEARCH_METADATA_WEIGHT"),
        ("baseline_weight", "MISAKA_SEARCH_BASELINE_WEIGHT"),
        ("rrf_k", "MISAKA_SEARCH_RRF_K"),
        ("cross_encoder_weight", "MISAKA_SEARCH_CROSS_ENCODER_WEIGHT"),
        ("bm25_rerank_weight", "MISAKA_SEARCH_BM25_RERANK_WEIGHT"),
    ]:
        val = os.environ.get(env_key)
        if val is not None:
            config[key] = val
    return config


def get_search_config() -> SearchConfig:
    """Load and return search configuration.

    Priority: env vars > config.yaml > defaults.
    """
    config = SearchConfig()

    # Layer 1: config.yaml
    yaml_config = _load_config_from_yaml()
    if yaml_config:
        for key in ("bm25_weight", "metadata_weight", "baseline_weight", "rrf_k"):
            if key in yaml_config:
                try:
                    val = float(yaml_config[key]) if key != "rrf_k" else int(yaml_config[key])
                    setattr(config, key, val)
                except (ValueError, TypeError):
                    pass

    # Layer 2: env vars (override yaml)
    env_config = _load_config_from_env()
    for key, val in env_config.items():
        try:
            setattr(config, key, float(val) if key != "rrf_k" else int(val))
        except (ValueError, TypeError):
            pass

    return config


# Module-level cached config
_cached_config: Optional[SearchConfig] = None


def get_cached_config() -> SearchConfig:
    """Get cached search config (loaded once per process)."""
    global _cached_config
    if _cached_config is None:
        _cached_config = get_search_config()
    return _cached_config


if __name__ == "__main__":
    config = get_search_config()
    errors = config.validate()
    print(f"Search Config:")
    print(f"  BM25 weight:     {config.bm25_weight}")
    print(f"  Metadata weight: {config.metadata_weight}")
    print(f"  Baseline weight: {config.baseline_weight}")
    print(f"  RRF k:           {config.rrf_k}")
    if errors:
        print(f"\n  ERRORS: {errors}")
    else:
        print(f"\n  Valid ✓")
