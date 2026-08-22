"""Portable, configurable PR Genius rule engine.

Rules are dictionaries with ``id``, ``name``, ``category`` and optional
``paths``/``enabled`` fields.  Repository configuration is deliberately
small and optional; without PyYAML a useful JSON-compatible YAML subset is
still accepted.
"""
from __future__ import annotations

from pathlib import Path
import json

DEFAULT_RULES = [
    {"id": "pr-size", "name": "PR size", "category": "core"},
    {"id": "tests", "name": "Test coverage", "category": "core"},
    {"id": "documentation", "name": "Documentation", "category": "core"},
    {"id": "issue-reference", "name": "Issue reference", "category": "core"},
    {"id": "dco", "name": "DCO sign-off", "category": "core"},
    {"id": "draft", "name": "Draft status", "category": "core"},
    {"id": "review-staleness", "name": "Review staleness", "category": "core"},
]


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        # Configs can use JSON, which is valid YAML and keeps the core portable.
        return json.loads(path.read_text(encoding="utf-8"))


def load_rules(config_path: str | Path | None = None) -> list[dict]:
    """Return ordered, deduplicated rules with config overrides applied."""
    config = _load(Path(config_path)) if config_path else {}
    configured = config.get("rules", [])
    if isinstance(configured, dict):
        configured = [dict(value, id=key) for key, value in configured.items()]
    by_id = {rule["id"]: dict(rule) for rule in DEFAULT_RULES}
    order = [rule["id"] for rule in DEFAULT_RULES]
    for rule in configured:
        if not isinstance(rule, dict) or not rule.get("id"):
            continue
        rid = rule["id"]
        if rid not in by_id:
            order.append(rid)
        by_id[rid] = {**by_id.get(rid, {}), **rule}
    return [by_id[rid] for rid in order if by_id[rid].get("enabled", True)]


def rules_for_paths(rules: list[dict], changed_paths: list[str]) -> list[dict]:
    """Filter path-triggered rules; rules without paths always apply."""
    result = []
    for rule in rules:
        patterns = rule.get("paths")
        if not patterns or any(Path(path).match(pattern) for path in changed_paths for pattern in patterns):
            result.append(rule)
    return result
