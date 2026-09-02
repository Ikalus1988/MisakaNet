"""Freshness decay model for MisakaNet lessons.

Implements quality decay over time to keep the knowledge base fresh.
Based on TeamMemory's model: protection period → decay → slow decay → tiers.

Usage:
    from misakanet.freshness import compute_freshness, FRESHNESS_TIERS

    score = compute_freshness(lesson)
    tier = get_tier(score)
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ── Configurable decay parameters ──

DECAY_CONFIG = {
    "protection_days": 14,      # no decay for first 14 days after merge
    "decay_rate": 1.0,          # points per day after protection
    "slow_threshold": 50,       # below this, decay slows
    "slow_decay_rate": 0.5,     # points per day when below threshold
    "pin_exempt": True,         # pinned lessons don't decay
    "base_score": 100,          # starting freshness score
}

# ── Freshness tiers ──

FRESHNESS_TIERS = {
    "fresh":    {"min": 80, "badge": "🟢", "label": "Fresh"},
    "stable":   {"min": 60, "badge": "🔵", "label": "Stable"},
    "aging":    {"min": 40, "badge": "🟡", "label": "Aging"},
    "stale":    {"min": 20, "badge": "🟠", "label": "Stale"},
    "outdated": {"min": 0,  "badge": "🔴", "label": "Outdated"},
}

# ── Boost signals ──

BOOST_VALUES = {
    "was_used": 5,        # lesson used in faithfulness evaluation
    "helpful_vote": 3,    # user marked as helpful
    "maintainer_edit": 10, # updated/edited by maintainer
    "pinned": 100,        # reset to 100 (pinned)
}


def get_tier(score: float) -> dict:
    """Get freshness tier for a score."""
    for tier_name, tier_info in FRESHNESS_TIERS.items():
        if score >= tier_info["min"]:
            return {"tier": tier_name, **tier_info}
    return {"tier": "outdated", **FRESHNESS_TIERS["outdated"]}


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string (YYYY-MM-DD or ISO format)."""
    if not date_str:
        return None
    # 规范化：移除 Z 后缀，处理微秒
    normalized = date_str.rstrip("Z").split(".")[0]
    # 尝试 ISO 格式
    try:
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        pass
    # 回退：简单日期格式
    try:
        return datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        pass
    return None


def compute_freshness(
    lesson: dict,
    config: Optional[dict] = None,
    today: Optional[datetime] = None,
) -> dict:
    """Compute freshness score for a lesson.

    Args:
        lesson: Lesson dict with frontmatter fields
        config: Override DECAY_CONFIG defaults
        today: Override current date (for testing)

    Returns:
        dict with score, tier, days_since_merge, is_pinned, boosts_applied
    """
    cfg = {**DECAY_CONFIG, **(config or {})}
    today = today or datetime.now()

    # Check if pinned
    is_pinned = lesson.get("pinned", False) or lesson.get("pin", False)
    if is_pinned and cfg["pin_exempt"]:
        tier = get_tier(cfg["base_score"])
        return {
            "score": cfg["base_score"],
            "tier": tier,
            "days_since_merge": 0,
            "is_pinned": True,
            "boosts_applied": [],
            "protected": False,
        }

    # Get merge date from provenance or created field
    merge_date = None
    provenance = lesson.get("provenance", {})
    if isinstance(provenance, dict):
        merge_date = parse_date(provenance.get("merged_at"))
    if not merge_date:
        merge_date = parse_date(lesson.get("created"))

    if not merge_date:
        # No date found — assume old, apply full decay
        score = max(0, cfg["base_score"] - 365 * cfg["decay_rate"])
        tier = get_tier(score)
        return {
            "score": round(score, 1),
            "tier": tier,
            "days_since_merge": 365,
            "is_pinned": False,
            "boosts_applied": [],
            "protected": False,
        }

    days_since_merge = (today - merge_date).days

    # Apply boosts first
    score = cfg["base_score"]
    boosts_applied = []

    boost_events = lesson.get("freshness_boosts", [])
    if isinstance(boost_events, list):
        for event in boost_events:
            event_type = event if isinstance(event, str) else event.get("type")
            if event_type in BOOST_VALUES:
                boost_value = BOOST_VALUES[event_type]
                score = min(100, score + boost_value)
                boosts_applied.append({"type": event_type, "value": boost_value})

    # Protection period
    if days_since_merge <= cfg["protection_days"]:
        return {
            "score": round(score, 1),
            "tier": get_tier(score),
            "days_since_merge": days_since_merge,
            "is_pinned": False,
            "boosts_applied": boosts_applied,
            "protected": True,
        }

    # Calculate decay
    decay_days = days_since_merge - cfg["protection_days"]
    decay_points = 0

    if score > cfg["slow_threshold"]:
        # Normal decay until threshold
        days_at_normal = min(decay_days, (score - cfg["slow_threshold"]) / cfg["decay_rate"])
        decay_points += days_at_normal * cfg["decay_rate"]
        remaining_days = decay_days - days_at_normal
        if remaining_days > 0:
            decay_points += remaining_days * cfg["slow_decay_rate"]
    else:
        # Already below threshold, slow decay
        decay_points = decay_days * cfg["slow_decay_rate"]

    final_score = max(0, score - decay_points)
    tier = get_tier(final_score)

    return {
        "score": round(final_score, 1),
        "tier": tier,
        "days_since_merge": days_since_merge,
        "is_pinned": False,
        "boosts_applied": boosts_applied,
        "protected": False,
    }


def compute_freshness_from_file(filepath: Path, config: Optional[dict] = None) -> dict:
    """Compute freshness for a lesson file."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    return compute_freshness_from_content(content, config)


def compute_freshness_from_content(content: str, config: Optional[dict] = None) -> dict:
    """Compute freshness for lesson content string."""
    fm = _extract_frontmatter(content)
    if fm is None:
        fm = {}
    return compute_freshness(fm, config)


def _extract_frontmatter(content: str) -> Optional[dict]:
    """Extract JSON or YAML-like frontmatter from lesson content."""
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None
    raw = m.group(1).strip()
    # Try JSON first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # YAML-like fallback
    try:
        fm = {}
        current_key = None
        current_list = None
        current_nested = None
        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Nested object (2-space indent)
            if line.startswith("  ") and ":" in stripped and current_key:
                if current_nested is None:
                    current_nested = {}
                nk, _, nv = stripped.partition(":")
                nk, nv = nk.strip(), nv.strip()
                if nv:
                    current_nested[nk] = nv.strip("\"'")
                continue
            # List item
            if stripped.startswith("- "):
                if current_key and current_list is not None:
                    current_list.append(stripped[2:].strip().strip("\"'"))
                continue
            # Save nested if we're leaving it
            if current_nested and current_key:
                fm[current_key] = current_nested
                current_nested = None
            # Key: value
            if ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip(), val.strip()
                if current_key and current_list is not None:
                    fm[current_key] = current_list
                    current_list = None
                if val == "":
                    current_key, current_list = key, []
                elif val.startswith("[") and val.endswith("]"):
                    fm[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",")]
                    current_key = None
                elif val.lower() in ("true", "false"):
                    fm[key] = val.lower() == "true"
                    current_key = None
                else:
                    fm[key] = val.strip("\"'")
                    current_key = None
        # Flush remaining
        if current_nested and current_key:
            fm[current_key] = current_nested
        elif current_key and current_list is not None:
            fm[current_key] = current_list
        return fm if fm else None
    except Exception:
        return None


# ── CLI interface ──

def main():
    """CLI entry point for freshness scoring."""
    import sys

    args = sys.argv[1:]
    if not args or "--help" in args:
        print("Usage: python3 -m misakanet.freshness <lesson_path> [--json]")
        print("       python3 -m misakanet.freshness --all [--json]")
        sys.exit(0)

    repo = Path(__file__).resolve().parent.parent
    lessons_dir = repo / "lessons"
    use_json = "--json" in args
    show_all = "--all" in args

    if show_all:
        results = []
        for md_file in sorted(lessons_dir.rglob("*.md")):
            if md_file.name.startswith("."):
                continue
            try:
                result = compute_freshness_from_file(md_file)
                result["file"] = str(md_file.relative_to(repo))
                results.append(result)
            except Exception as e:
                if not use_json:
                    print(f"Error: {md_file}: {e}", file=sys.stderr)

        if use_json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            for r in results:
                tier = r["tier"]
                print(f"{tier['badge']} {r['score']:5.1f}  {r['file']}")
    else:
        filepath = Path(args[0])
        if not filepath.exists():
            print(f"Error: {filepath} not found", file=sys.stderr)
            sys.exit(1)
        result = compute_freshness_from_file(filepath)
        if use_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            tier = result["tier"]
            print(f"Freshness: {result['score']:.1f} {tier['badge']} {tier['label']}")
            print(f"Days since merge: {result['days_since_merge']}")
            if result["is_pinned"]:
                print("Pinned: exempt from decay")
            if result["boosts_applied"]:
                print(f"Boosts: {result['boosts_applied']}")


if __name__ == "__main__":
    main()
