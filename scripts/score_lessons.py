#!/usr/bin/env python3
"""Lesson Quality Score — automated grading for all lessons.

Scoring dimensions (1.0 total):
  - root_cause_clarity (0.35): has Root Cause section with technical detail
  - verify_completeness (0.25): has Verification section with executable steps
  - domain_coverage (0.15): covers multiple environments or version-specific behavior
  - frontmatter_completeness (0.15): title, domain, tags, status, evidence_level
  - content_length (0.10): minimum word count for substantive content
  - link_validity (0.05): no obviously broken URLs

Grade mapping:
  A (>=0.80): Excellent — production-ready lesson
  B (>=0.60): Good — solid content, minor gaps
  C (>=0.40): Fair — needs improvement in key areas
  D (<0.40) : Poor — significant issues, rewrite recommended

Usage:
  python3 scripts/score_lessons.py                     # score all, print table
  python3 scripts/score_lessons.py --json              # JSON to stdout
  python3 scripts/score_lessons.py --output FILE       # JSON to file
  python3 scripts/score_lessons.py --threshold 0.6     # exit 1 if any below
  python3 scripts/score_lessons.py --ci                # CI mode (JSON + threshold=0.6)
  python3 scripts/score_lessons.py lessons/core/xxx.md # single file
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
DATA_DIR = REPO / "data"

sys.path.insert(0, str(REPO))
try:
    from misakanet.evidence import evidence_of, evidence_weight, trust_score
except ImportError:
    # Graceful degradation if evidence module unavailable
    def evidence_of(fm): return "E0"
    def evidence_weight(lvl): return 0.0
    def trust_score(score, lvl): return score

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
W_CLARITY    = 0.35
W_VERIFY     = 0.25
W_COVERAGE   = 0.15
W_FRONTCOMP  = 0.15
W_LENGTH     = 0.10
W_LINKS      = 0.05

# Grade thresholds
GRADE_A = 0.80
GRADE_B = 0.60
GRADE_C = 0.40

# Content minimums
MIN_WORDS = 100
TARGET_WORDS = 300

# Required frontmatter fields
REQUIRED_FM = ["title", "domain", "status"]
RECOMMENDED_FM = ["tags", "evidence_level"]

# Environment signal patterns
ENV_PATTERNS = re.compile(
    r'platform:|environment:|WSL|Docker|Ubuntu|Windows|macOS|Linux|'
    r'Python\s*3\.\d+|Node\.js\s*\d+|v\d+\.\d+\.\d+',
    re.I
)

# URL pattern (basic)
URL_RE = re.compile(r'https?://[^\s)>\]\"]+', re.I)


def parse_frontmatter(text: str) -> dict:
    """Parse JSON frontmatter from --- fenced content."""
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    return {}


def score_clarity(content: str) -> float:
    """Root cause clarity: 0.0 – 1.0"""
    has_root = bool(re.search(r'^## Root Cause', content, re.M))
    if not has_root:
        return 0.0

    idx = content.index('## Root Cause')
    chunk = content[idx:idx + 1500]
    has_detail = bool(re.search(
        r'(error message|config|diff|stack trace|log|exit code|status code|command|output)',
        chunk, re.I
    ))
    return 1.0 if has_detail else 0.6


def score_verify(content: str) -> float:
    """Verification completeness: 0.0 – 1.0"""
    has_verify = bool(re.search(r'^## Verification', content, re.M))
    if not has_verify:
        return 0.0

    idx = content.index('## Verification')
    chunk = content[idx:idx + 1500]
    has_commands = bool(re.search(r'```(bash|sh|python|yaml|json|text|cmd)', chunk))
    has_expected = bool(re.search(
        r'(expected|should see|output:|result:|✅|success)', chunk, re.I
    ))

    if has_commands and has_expected:
        return 1.0
    elif has_commands or has_expected:
        return 0.7
    else:
        return 0.3


def score_coverage(content: str) -> float:
    """Domain/environment coverage: 0.0 – 1.0"""
    env_matches = ENV_PATTERNS.findall(content)
    unique_envs = set(m.lower() for m in env_matches)
    has_version = bool(re.search(r'\bv?\d+\.\d+\.\d+\b', content))

    if len(unique_envs) >= 2 or (len(unique_envs) >= 1 and has_version):
        return 1.0
    elif len(unique_envs) == 1 or has_version:
        return 0.5
    else:
        return 0.0


def score_frontmatter(fm: dict) -> float:
    """Frontmatter completeness: 0.0 – 1.0"""
    if not fm:
        return 0.0

    score = 0.0
    total = len(REQUIRED_FM) + len(RECOMMENDED_FM)

    for field in REQUIRED_FM:
        val = fm.get(field)
        if val and (isinstance(val, str) and len(val.strip()) > 0 or
                    isinstance(val, list) and len(val) > 0):
            score += 2.0 / total  # required fields weighted 2x

    for field in RECOMMENDED_FM:
        val = fm.get(field)
        if val and (isinstance(val, str) and len(val.strip()) > 0 or
                    isinstance(val, list) and len(val) > 0):
            score += 1.0 / total

    return min(score, 1.0)


def score_content_length(text: str) -> float:
    """Content length score: 0.0 – 1.0"""
    # Strip frontmatter for word count
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, count=1, flags=re.DOTALL)
    words = len(re.findall(r'\b\w+\b', body))

    if words >= TARGET_WORDS:
        return 1.0
    elif words >= MIN_WORDS:
        return 0.5 + 0.5 * (words - MIN_WORDS) / (TARGET_WORDS - MIN_WORDS)
    else:
        return words / MIN_WORDS * 0.5


def score_links(text: str) -> float:
    """Link validity (basic format check): 0.0 – 1.0"""
    urls = URL_RE.findall(text)
    if not urls:
        return 1.0  # no links = no broken links

    broken = 0
    for url in urls:
        # Basic sanity: must have domain.tld pattern
        if not re.search(r'https?://[\w.-]+\.\w{2,}', url):
            broken += 1
        # Check for common broken patterns
        elif url.endswith(('.png', '.jpg', '.gif')) and 'example.com' in url:
            broken += 1

    return 1.0 - (broken / len(urls)) if urls else 1.0


def grade_from_score(score: float) -> str:
    """Map numeric score to A/B/C/D grade."""
    if score >= GRADE_A:
        return "A"
    elif score >= GRADE_B:
        return "B"
    elif score >= GRADE_C:
        return "C"
    else:
        return "D"


def score_lesson(filepath: Path) -> dict:
    """Score a single lesson file across all dimensions."""
    text = filepath.read_text(encoding='utf-8')
    fm = parse_frontmatter(text)

    clarity     = score_clarity(text)
    verify      = score_verify(text)
    coverage    = score_coverage(text)
    frontcomp   = score_frontmatter(fm)
    length      = score_content_length(text)
    links       = score_links(text)

    raw_score = (W_CLARITY * clarity + W_VERIFY * verify + W_COVERAGE * coverage +
                 W_FRONTCOMP * frontcomp + W_LENGTH * length + W_LINKS * links)

    level = evidence_of(fm)
    trust  = trust_score(raw_score, level)
    grade  = grade_from_score(raw_score)

    # Word count for reporting
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, count=1, flags=re.DOTALL)
    word_count = len(re.findall(r'\b\w+\b', body))

    return {
        "file": str(filepath.relative_to(REPO)),
        "grade": grade,
        "score": round(raw_score, 3),
        "dimensions": {
            "clarity": round(clarity, 2),
            "verify": round(verify, 2),
            "coverage": round(coverage, 2),
            "frontmatter": round(frontcomp, 2),
            "length": round(length, 2),
            "links": round(links, 2),
        },
        "evidence_level": level,
        "trust_score": round(trust, 3),
        "word_count": word_count,
        "frontmatter": {
            "title": fm.get("title", ""),
            "domain": fm.get("domain", ""),
            "status": fm.get("status", ""),
            "tags": fm.get("tags", []),
        },
    }


def collect_files(target: Path) -> list:
    """Collect lesson files to score."""
    if target.is_file():
        return [target]

    files = sorted(target.rglob("*.md"))
    skip = {"index.md", "TEMPLATE.md", "README.md", "LESSON_QUALITY_SCORING.md"}
    return [f for f in files
            if f.name not in skip and "_archive" not in f.parts]


def print_table(results: list, threshold: float = None):
    """Print human-readable scoring table."""
    below = [r for r in results if r["score"] < (threshold or 0)]
    avg = sum(r["score"] for r in results) / len(results)
    avg_trust = sum(r["trust_score"] for r in results) / len(results)

    grades = Counter(r["grade"] for r in results)

    print(f"Checked {len(results)} lessons. Average: {avg:.3f} (trust: {avg_trust:.3f})")
    print(f"Grades: A={grades.get('A',0)} B={grades.get('B',0)} C={grades.get('C',0)} D={grades.get('D',0)}")
    print()
    print(f"{'Grade':<7} {'Score':<8} {'Trust':<8} {'Ev':<4} {'Words':<7} File")
    print("-" * 80)
    for r in sorted(results, key=lambda x: x["score"]):
        tag = " ⚠️" if threshold and r["score"] < threshold else ""
        print(f"{r['grade']:<7} {r['score']:<8.3f} {r['trust_score']:<8.3f} "
              f"{r['evidence_level']:<4} {r['word_count']:<7} {r['file']}{tag}")

    print()
    if threshold is not None:
        print(f"Threshold: {threshold}")
        print(f"Below threshold: {len(below)}/{len(results)}")
        if below:
            for r in below:
                print(f"  {r['file']} (score={r['score']:.3f}, grade={r['grade']})")

    # Evidence distribution
    levels = Counter(r["evidence_level"] for r in results)
    print("Evidence: " + "  ".join(
        f"{lvl}={levels.get(lvl, 0)}" for lvl in ("E0", "E1", "E2", "E3", "E4")
    ))


def write_json_report(results: list, output_path: Path):
    """Write JSON report to data/lesson-scores.json."""
    grades = Counter(r["grade"] for r in results)
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0
    avg_trust = sum(r["trust_score"] for r in results) / len(results) if results else 0

    report = {
        "meta": {
            "total": len(results),
            "average_score": round(avg_score, 3),
            "average_trust": round(avg_trust, 3),
            "grade_distribution": {
                "A": grades.get("A", 0),
                "B": grades.get("B", 0),
                "C": grades.get("C", 0),
                "D": grades.get("D", 0),
            },
        },
        "lessons": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\nJSON report written to {output_path.relative_to(REPO)}")


def main():
    args = sys.argv[1:]

    # Parse flags
    threshold = None
    json_output = False
    ci_mode = False
    output_file = None
    targets = []

    i = 0
    while i < len(args):
        if args[i] == "--threshold" and i + 1 < len(args):
            threshold = float(args[i + 1])
            i += 2
        elif args[i] == "--json":
            json_output = True
            i += 1
        elif args[i] == "--output" and i + 1 < len(args):
            output_file = Path(args[i + 1])
            i += 2
        elif args[i] == "--ci":
            ci_mode = True
            threshold = 0.6
            json_output = True
            i += 1
        elif args[i] == "--help" or args[i] == "-h":
            print(__doc__)
            sys.exit(0)
        else:
            targets.append(Path(args[i]))
            i += 1

    if not targets:
        targets = [LESSONS_DIR]

    # Collect files
    files = []
    for t in targets:
        files.extend(collect_files(t.resolve()))

    if not files:
        print("No lessons found.")
        sys.exit(0 if threshold is None else 1)

    # Score all
    results = []
    for fp in files:
        try:
            r = score_lesson(fp)
            results.append(r)
        except Exception as e:
            print(f"ERROR: {fp}: {e}", file=sys.stderr)

    if not results:
        print("No lessons scored.")
        sys.exit(0 if threshold is None else 1)

    # Output
    if json_output:
        report = {
            "meta": {
                "total": len(results),
                "average_score": round(sum(r["score"] for r in results) / len(results), 3),
                "average_trust": round(sum(r["trust_score"] for r in results) / len(results), 3),
                "grade_distribution": dict(Counter(r["grade"] for r in results)),
            },
            "lessons": results,
        }
        if output_file:
            write_json_report(results, output_file)
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_table(results, threshold)

    # Always write to data/lesson-scores.json unless single file mode
    if len(files) > 1:
        default_output = DATA_DIR / "lesson-scores.json"
        write_json_report(results, default_output)

    # CI exit code
    if threshold is not None:
        below = [r for r in results if r["score"] < threshold]
        if below:
            sys.exit(1)


if __name__ == "__main__":
    main()
