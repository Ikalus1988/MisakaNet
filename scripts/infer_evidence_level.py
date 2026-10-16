#!/usr/bin/env python3
"""
Infer evidence_level for MisakaNet lessons based on content analysis.

This script reads a lesson's **own words**. That bounds what it can answer: E0–E3 are claims the
prose can carry (self-reported, reviewed, reproduced, CI-verified), and each is a hint at best —
the frontmatter is the authority and this is only the fallback for legacy lessons that declare
nothing.

**It never infers `E4`.** The top rung is an observation, not a statement: two or more distinct
clients actually retrieved the lesson, counted as `COUNT(DISTINCT client_hint)` over
`search_signals` in the hosted worker (`misakanet/evidence.py`, `docs/trust-semantics.md`). Until
2026-10-17 this script returned `E4` for bodies matching `reused by` / `verified by another
contributor` / `usage report` / `cross-node confirmation` — i.e. a lesson talking about itself
could confer the rung that means "somebody else proved it by using it". Two lessons reached the
public `E4` badge that way; the branch was removed and they read `E0` again — they declare no
level, which is what the default rule says. A helpful vote cannot confer `E4` either
(2026-10-16). Anything written in a lesson body is a declaration, and a declaration is not an
observation.

Usage:
    # From lesson content
    python3 scripts/infer_evidence_level.py --content "lesson content here"

    # From lesson file
    python3 scripts/infer_evidence_level.py --file path/to/lesson.md

    # With PR context
    python3 scripts/infer_evidence_level.py --file lesson.md --pr-comment

    # What a lesson's own inferred level would be (never E4)
    python3 scripts/infer_evidence_level.py --file lessons/contrib/example.md
"""

import argparse
import re
import sys
from pathlib import Path

# Evidence level definitions. `E4` is listed so the reference table a PR comment prints is
# complete, and it is deliberately unreachable from `infer_evidence_level` — it is observed in
# `search_signals`, not read out of a lesson.
EVIDENCE_LEVELS = {
    "E0": "Self-reported (default)",
    "E1": "Maintainer reviewed",
    "E2": "Locally reproduced",
    "E3": "CI/sandbox verified",
    "E4": "Observed reuse by distinct clients (not inferable from content)",
}


def infer_evidence_level(content: str) -> tuple[str, str]:
    """
    Infer evidence_level from lesson content. **Never returns `E4`.**

    A lesson may write "verified by two other agents" and it still reads as `E3` at most: the
    sentence is a declaration the lesson makes about itself, and `E4` is reserved for an
    observation made at the transport layer.

    Returns:
        (level, reasoning) tuple
    """
    content_lower = content.lower()

    # E3: CI/sandbox verification
    ci_patterns = [
        r"(?:ci|pipeline|workflow)\s+(?:pass|success|verified|run)",
        r"(?:github\s+actions?|gitlab\s+ci|jenkins|circle\s*ci)",
        r"ci[- ]?(?:verified|passed|success)",
        r"automated\s+(?:test|verification|check)\s+(?:pass|success)",
        r"workflow\s+(?:run|execution)\s+(?:#?\d+|link)",
        r"(?:sandbox|test[- ]?environment)\s+(?:verified|pass)",
        r"reproduc(?:ed?|ibility)\s+(?:in|via|through)\s+ci",
        r"passed?\s+(?:all\s+)?(?:ci|checks?|tests?|pipelines?)",
    ]
    for pattern in ci_patterns:
        if re.search(pattern, content_lower):
            return "E3", f"Contains CI verification evidence: '{pattern}'"

    # E2: Local reproduction evidence
    local_patterns = [
        r"locally\s+(?:reproduced?|verified?|confirmed?|tested?)",
        r"(?:i|we|author)\s+(?:reproduced?|verified?|confirmed?|tested?)\s+(?:this|it|the\s+fix)",
        r"reproduction\s+(?:steps?|log|output|result)",
        r"(?:before|after)\s+(?:fix|patch|change)\s*[:=]",
        r"(?:error|output)\s+(?:before|after)\s*(?:fix|patch|change)",
        r"smoke\s+test\s+(?:pass|success|verified)",
        r"verified?\s+(?:locally|on\s+(?:my|the)\s+(?:machine|environment|setup))",
        r"(?:my|the)\s+(?:local|dev|development)\s+(?:environment|setup)\s+(?:verified|pass)",
    ]
    for pattern in local_patterns:
        if re.search(pattern, content_lower):
            return "E2", f"Contains local reproduction evidence: '{pattern}'"

    # E1: Maintainer review evidence
    review_patterns = [
        r"maintainer\s+(?:reviewed?|approved?|accepted?)",
        r"(?:reviewed?|approved?|accepted?)\s+by\s+(?:maintainer|core\s+team)",
        r"(?:pr|pull\s+request)\s+(?:reviewed?|approved?|merged?)",
        r"(?:code\s+review|review\s+comment)",
        r"(?:lgmt|looks?\s+good\s+to\s+me|approved)",
    ]
    for pattern in review_patterns:
        if re.search(pattern, content_lower):
            return "E1", f"Contains review evidence: '{pattern}'"

    # Default to E0
    return "E0", "No evidence markers found (default level)"


def format_pr_comment(level: str, reasoning: str, content_preview: str) -> str:
    """Format evidence level as PR comment."""
    emoji = {"E0": "📝", "E1": "👀", "E2": "🔬", "E3": "✅", "E4": "🏆"}
    return f"""## Evidence Level Inference

**Suggested level: {emoji.get(level, "📝")} {level}** — {EVIDENCE_LEVELS[level]}

**Reasoning:** {reasoning}

### Content Preview
```
{content_preview[:500]}{'...' if len(content_preview) > 500 else ''}
```

### Evidence Levels Reference
| Level | Meaning | Weight |
|-------|---------|--------|
| E0 | Self-reported (default) | 0.00 |
| E1 | Maintainer reviewed | 0.25 |
| E2 | Locally reproduced | 0.50 |
| E3 | CI/sandbox verified | 0.75 |
| E4 | Observed reuse by distinct clients — never inferred from content | 1.00 |

*E4 is not suggested by this tool: it comes from `search_signals` (two or more distinct clients
retrieved the lesson), not from anything a lesson writes about itself.*

---
*Auto-generated by PR Genius evidence inference*"""


def main():
    parser = argparse.ArgumentParser(description="Infer evidence_level for lessons")
    parser.add_argument("--content", help="Lesson content string")
    parser.add_argument("--file", help="Path to lesson file")
    parser.add_argument("--pr-comment", action="store_true", help="Output as PR comment")
    args = parser.parse_args()

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        print("Error: --content or --file required", file=sys.stderr)
        sys.exit(1)

    level, reasoning = infer_evidence_level(content)

    if args.pr_comment:
        print(format_pr_comment(level, reasoning, content))
    else:
        print(f"Level: {level}")
        print(f"Reasoning: {reasoning}")


if __name__ == "__main__":
    main()
