"""PR Genius rule engine — repo-agnostic core + repo-specific config.

Layer 1 (repo-agnostic): portable rules built into the engine.
Layer 2 (repo-specific): loaded from .pr-genius.yaml path_rules + custom_patterns.
"""

from __future__ import annotations

import re
from typing import Any

# ── Repo-agnostic rules (Layer 1) ──────────────────────────────────────────

REPO_AGNOSTIC_RULES: list[dict[str, Any]] = [
    {
        "id": "pr_too_large",
        "layer": "core",
        "severity": "high",
        "enabled": True,
        "description": "PR exceeds max line threshold",
    },
    {
        "id": "missing_tests",
        "layer": "core",
        "severity": "medium",
        "enabled": True,
        "description": "Code changed but no test files updated",
    },
    {
        "id": "doc_code_mismatch",
        "layer": "core",
        "severity": "low",
        "enabled": True,
        "description": "Docs-only PR with no code or test changes",
    },
    {
        "id": "mixed_concerns",
        "layer": "core",
        "severity": "medium",
        "enabled": True,
        "description": "PR touches 3+ unrelated component areas",
    },
    {
        "id": "no_issue_reference",
        "layer": "core",
        "severity": "low",
        "enabled": True,
        "description": "No linked issue found in PR body",
    },
    {
        "id": "missing_dco",
        "layer": "core",
        "severity": "medium",
        "enabled": True,
        "description": "One or more commits lack Signed-off-by",
    },
    {
        "id": "draft_pr",
        "layer": "core",
        "severity": "info",
        "enabled": True,
        "description": "PR is in draft state",
    },
    {
        "id": "review_stale",
        "layer": "core",
        "severity": "medium",
        "enabled": True,
        "description": "PR has been open >14 days without approval",
    },
]

# ── Rule engine ────────────────────────────────────────────────────────────


def build_rule_list(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge repo-agnostic rules with repo-specific config.

    Returns ordered list of rule dicts with id, layer, severity, enabled,
    and optional trigger (path glob pattern).
    """
    cfg_rules = config.get("rules", {})
    pattern_cfg = cfg_rules.get("patterns", {})

    # Start with repo-agnostic rules, apply config overrides
    rules: list[dict[str, Any]] = []
    for rule in REPO_AGNOSTIC_RULES:
        merged = dict(rule)
        override = pattern_cfg.get(rule["id"], {})
        if override:
            merged["enabled"] = override.get("enabled", rule["enabled"])
            merged["severity"] = override.get("severity", rule["severity"])
        rules.append(merged)

    # Add repo-specific path_rules (Layer 2)
    path_rules = cfg_rules.get("path_rules", [])
    for pr in path_rules:
        if not isinstance(pr, dict):
            continue
        rules.append({
            "id": pr.get("id", "custom_path_rule"),
            "layer": "repo",
            "severity": pr.get("severity", "medium"),
            "enabled": pr.get("enabled", True),
            "description": pr.get("description", ""),
            "trigger": pr.get("trigger", ""),  # path glob pattern
            "message": pr.get("message", ""),
        })

    # Add repo-specific custom_patterns (Layer 2)
    custom_patterns = cfg_rules.get("custom_patterns", [])
    for cp in custom_patterns:
        if not isinstance(cp, dict):
            continue
        rules.append({
            "id": cp.get("id", "custom_pattern"),
            "layer": "repo",
            "severity": cp.get("severity", "medium"),
            "enabled": cp.get("enabled", True),
            "description": cp.get("description", ""),
            "pattern": cp.get("pattern", ""),  # regex on PR body/title
            "message": cp.get("message", ""),
        })

    return rules


def _match_path(path: str, pattern: str) -> bool:
    """Match a file path against a glob pattern.

    Supports ``**`` for recursive directory matching and ``*``/``?``
    for single-segment wildcards.
    """
    import fnmatch

    if "**" not in pattern:
        return fnmatch.fnmatch(path, pattern)

    # Split into prefix (before **) and suffix (after **)
    prefix, _, suffix = pattern.partition("**")
    prefix = prefix.rstrip("/")
    suffix = suffix.lstrip("/")

    # Path must start with prefix
    if prefix and not path.startswith(prefix):
        return False
    remaining = path[len(prefix):].lstrip("/")

    # If no suffix, ** at end matches everything
    if not suffix:
        return True

    # Check if any path segment (or the whole remaining) matches suffix
    # migrations/**/*.sql → suffix = *.sql
    # Match against each possible suffix of the remaining path
    parts = remaining.split("/")
    for i in range(len(parts)):
        subpath = "/".join(parts[i:])
        if fnmatch.fnmatch(subpath, suffix):
            return True
    return False


def evaluate_path_rules(
    rules: list[dict[str, Any]], paths: list[str]
) -> list[dict[str, str]]:
    """Evaluate path-triggered rules against changed file paths."""
    findings: list[dict[str, str]] = []
    for rule in rules:
        if not rule.get("enabled") or rule.get("layer") != "repo":
            continue
        trigger = rule.get("trigger", "")
        if not trigger:
            continue
        matched = [p for p in paths if _match_path(p, trigger)]
        if matched:
            findings.append({
                "rule": rule["id"],
                "severity": rule.get("severity", "medium"),
                "detail": rule.get("message") or rule.get("description", ""),
                "matched_files": ", ".join(matched[:5]),
            })
    return findings


def evaluate_body_rules(
    rules: list[dict[str, Any]], body: str, title: str = ""
) -> list[dict[str, str]]:
    """Evaluate regex pattern rules against PR body and title."""
    combined = f"{title}\n{body}"
    findings: list[dict[str, str]] = []
    for rule in rules:
        if not rule.get("enabled") or rule.get("layer") != "repo":
            continue
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        if re.search(pattern, combined, re.IGNORECASE):
            findings.append({
                "rule": rule["id"],
                "severity": rule.get("severity", "medium"),
                "detail": rule.get("message") or rule.get("description", ""),
            })
    return findings


def get_enabled_rules(
    rules: list[dict[str, Any]], layer: str | None = None
) -> list[dict[str, Any]]:
    """Return enabled rules, optionally filtered by layer."""
    return [
        r for r in rules
        if r.get("enabled", True) and (layer is None or r.get("layer") == layer)
    ]
