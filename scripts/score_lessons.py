#!/usr/bin/env python3
"""Lesson Quality Score — v0 algorithm.

Scoring dimensions:
  - root_cause_clarity (0.5): has Root Cause section with technical detail
  - verify_completeness (0.3): has Verification section with executable steps
  - domain_coverage (0.2): covers multiple environments or version-specific behavior

Usage:
  python3 scripts/score_lessons.py              # score all lessons
  python3 scripts/score_lessons.py --threshold 0.6  # exit 1 if any below threshold
  python3 scripts/score_lessons.py lessons/core/dco-auto-fix-workflow.md  # single file
"""

import json, re, sys, os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"

# Thresholds
RISK_LOW_CONFIDENCE = 0.65
RISK_VERY_LOW_CONFIDENCE = 0.4

WEIGHT_CLARITY = 0.5
WEIGHT_VERIFY = 0.3
WEIGHT_COVERAGE = 0.2

# Environment signal patterns
ENV_PATTERNS = re.compile(
    r'platform:|environment:|WSL|Docker|Ubuntu|Windows|macOS|Linux|'
    r'Python\s*3\.\d+|Node\.js\s*\d+|v\d+\.\d+\.\d+',
    re.I
)


def score_lesson(filepath: Path) -> dict:
    text = filepath.read_text(encoding='utf-8')

    # Parse frontmatter
    fm = {}
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if m:
        try:
            fm = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    content = text

    # --- root_cause_clarity ---
    has_root_section = bool(re.search(r'^## Root Cause', content, re.M))
    root_has_detail = bool(re.search(
        r'(error message|config|diff|stack trace|log|exit code|status code)',
        content[content.index('## Root Cause'):content.index('## Root Cause') + 1500]
        if has_root_section and '## Root Cause' in content else '',
        re.I
    )) if has_root_section else False

    if has_root_section and root_has_detail:
        clarity = 1.0
    elif has_root_section:
        clarity = 0.6
    else:
        clarity = 0.0

    # --- verify_completeness ---
    has_verify_section = bool(re.search(r'^## Verification', content, re.M))
    verify_has_commands = False
    if has_verify_section:
        idx = content.index('## Verification')
        verify_text = content[idx:idx + 1500]
        verify_has_commands = bool(re.search(r'```(bash|sh|python|yaml|json|text|cmd)', verify_text))
        verify_has_expected = bool(re.search(r'(expected|should see|output:|result:)', verify_text, re.I))

    if has_verify_section and verify_has_commands:
        verify = 1.0
    elif has_verify_section:
        verify = 0.5
    else:
        verify = 0.0

    # --- domain_coverage ---
    env_matches = ENV_PATTERNS.findall(content)
    unique_envs = set(m.lower() for m in env_matches)

    # Also check notes section for version info
    has_version_note = bool(re.search(r'\bv?\d+\.\d+\.\d+\b', content))

    if len(unique_envs) >= 2 or has_version_note:
        coverage = 1.0
    elif len(unique_envs) == 1:
        coverage = 0.5
    else:
        coverage = 0.0

    score = WEIGHT_CLARITY * clarity + WEIGHT_VERIFY * verify + WEIGHT_COVERAGE * coverage

    return {
        "file": str(filepath.relative_to(REPO)),
        "score": round(score, 3),
        "clarity": clarity,
        "verify": verify,
        "coverage": coverage,
        "has_root_section": has_root_section,
        "has_verify_section": has_verify_section,
    }


def main():
    args = sys.argv[1:]

    # Determine files to check
    if args and args[0] == "--threshold":
        threshold = float(args[1])
        files = sorted(LESSONS_DIR.rglob("*.md"))
        files = [f for f in files if f.name not in ("index.md", "TEMPLATE.md", "README.md")
                 and "_archive" not in f.parts]
    elif args and args[0].endswith(".md"):
        files = [Path(args[0])]
        threshold = None
    else:
        files = sorted(LESSONS_DIR.rglob("*.md"))
        files = [f for f in files if f.name not in ("index.md", "TEMPLATE.md", "README.md")
                 and "_archive" not in f.parts]
        threshold = None

    results = []
    for fp in files:
        try:
            r = score_lesson(fp)
            results.append(r)
        except Exception as e:
            print(f"ERROR: {fp}: {e}", file=sys.stderr)
            continue

    if not results:
        print("No lessons found.")
        sys.exit(0 if threshold is None else 1)

    # Print report
    below = [r for r in results if r["score"] < (threshold or 0)]
    avg = sum(r["score"] for r in results) / len(results)

    print(f"Checked {len(results)} lessons. Average score: {avg:.3f}")
    print()
    print(f"{'Score':<8} {'Clarity':<8} {'Verify':<8} {'Coverage':<10} File")
    print("-" * 70)
    for r in sorted(results, key=lambda x: x["score"]):
        tag = " ⚠️" if threshold and r["score"] < threshold else ""
        print(f"{r['score']:<8.3f} {r['clarity']:<8.1f} {r['verify']:<8.1f} {r['coverage']:<10.1f} {r['file']}{tag}")

    print()
    print(f"Average: {avg:.3f}")

    if threshold is not None:
        print(f"Threshold: {threshold}")
        print(f"Below threshold: {len(below)}/{len(results)}")
        if below:
            print("Files below threshold:")
            for r in below:
                print(f"  {r['file']} (score={r['score']:.3f})")

    # Exit with error if any file below threshold
    if threshold is not None and below:
        sys.exit(1)


if __name__ == "__main__":
    main()
