"""Evidence levels for failure-recovery lessons — Issue #786.

Lesson trust is graded E0–E4 instead of binary indexed/not-indexed, so a
self-reported guess and a CI-verified fix stop looking identical.

    E0  contributor self-reported          (default on intake)
    E1  maintainer reviewed
    E2  local smoke reproduced
    E3  sandbox / CI verified recovery
    E4  reused successfully by another contributor or agent

Anything unknown, missing, or malformed normalises to E0 — the claim is never
upgraded by accident.
"""
from __future__ import annotations

DEFAULT_EVIDENCE_LEVEL = "E0"

# level -> (label, how it is achieved, weight in [0, 1])
EVIDENCE_SEMANTICS: dict[str, tuple[str, str, float]] = {
    "E0": ("Contributor self-reported", "Default on intake", 0.0),
    "E1": ("Maintainer reviewed", "A maintainer accepted the intake", 0.25),
    "E2": ("Local smoke reproduced", "Maintainer or CI reproduced the fix", 0.5),
    "E3": ("Sandbox / CI verified recovery", "Automated verification in CI", 0.75),
    "E4": ("Reused by another contributor / agent", "Usage report from a different user", 1.0),
}

EVIDENCE_LEVELS = list(EVIDENCE_SEMANTICS)

# (from, to, what has to happen)
PROMOTION_RULES = [
    ("E0", "E1", "A maintainer reviews the lesson and accepts it (review)"),
    ("E1", "E2", "Someone reproduces the failure and the fix locally (reproduce)"),
    ("E2", "E3", "CI or a sandbox run verifies the recovery automatically (CI verify)"),
    ("E3", "E4", "A different contributor or agent reports reusing it successfully (external reuse)"),
]

# Quality score keeps its own 0–1 range; evidence rescales it into a trust
# score. An E0 lesson keeps 70% of its quality score, E4 keeps all of it —
# evidence adjusts confidence in a lesson, it does not replace writing quality.
TRUST_FLOOR = 0.7


def normalize_evidence_level(value) -> str:
    """Coerce any frontmatter value to a valid level, defaulting to E0."""
    if value is None:
        return DEFAULT_EVIDENCE_LEVEL
    if isinstance(value, bool):  # bools are ints in Python — reject explicitly
        return DEFAULT_EVIDENCE_LEVEL
    if isinstance(value, (int, float)):
        candidate = f"E{int(value)}"
    else:
        candidate = str(value).strip().upper()
    return candidate if candidate in EVIDENCE_SEMANTICS else DEFAULT_EVIDENCE_LEVEL


def evidence_weight(level) -> float:
    """Weight in [0, 1] for the given level."""
    return EVIDENCE_SEMANTICS[normalize_evidence_level(level)][2]


def evidence_label(level) -> str:
    return EVIDENCE_SEMANTICS[normalize_evidence_level(level)][0]


def evidence_of(frontmatter: dict | None) -> str:
    """Read the level out of lesson frontmatter (or an index entry)."""
    if not isinstance(frontmatter, dict):
        return DEFAULT_EVIDENCE_LEVEL
    return normalize_evidence_level(frontmatter.get("evidence_level"))


def next_level(level) -> str | None:
    """The level directly above this one, or None at E4."""
    current = normalize_evidence_level(level)
    index = EVIDENCE_LEVELS.index(current)
    return EVIDENCE_LEVELS[index + 1] if index + 1 < len(EVIDENCE_LEVELS) else None


def promotion_requirement(level) -> str | None:
    """What has to happen for this lesson to reach the next level."""
    current = normalize_evidence_level(level)
    for source, _target, requirement in PROMOTION_RULES:
        if source == current:
            return requirement
    return None


def trust_score(quality_score: float, level) -> float:
    """Combine a 0–1 quality score with the evidence level.

    Quality alone answers "is this lesson well written?"; trust answers "how
    much should I rely on it?".
    """
    try:
        quality = float(quality_score)
    except (TypeError, ValueError):
        quality = 0.0
    quality = max(0.0, min(1.0, quality))
    scale = TRUST_FLOOR + (1.0 - TRUST_FLOOR) * evidence_weight(level)
    return round(quality * scale, 3)


def describe(level) -> dict:
    """Everything a UI needs to render one level."""
    normalized = normalize_evidence_level(level)
    label, how, weight = EVIDENCE_SEMANTICS[normalized]
    return {
        "evidence_level": normalized,
        "label": label,
        "how_to_achieve": how,
        "weight": weight,
        "next_level": next_level(normalized),
        "promotion_requirement": promotion_requirement(normalized),
    }


def distribution(levels) -> dict[str, int]:
    """Count lessons per level, always reporting every level."""
    counts = {level: 0 for level in EVIDENCE_LEVELS}
    for level in levels:
        counts[normalize_evidence_level(level)] += 1
    return counts
