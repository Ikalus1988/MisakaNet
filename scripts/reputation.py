#!/usr/bin/env python3
"""Contributor Reputation Engine — reuse-weighted scoring with anti-gaming.

Formula:
    score = usage_reports × 2.0
          + lessons_contributed × 1.0
          + lessons_reused × 0.2
          + lessons_verified × 0.5

Anti-gaming:
    - Sigmoid cap: per-PR contribution capped at sigmoid(lessons) to prevent
      single massive PRs from dominating.
    - Time decay: recent contributions weighted more (half-life = 90 days).

Usage:
    python3 scripts/reputation.py                  # full reputation table
    python3 scripts/reputation.py --json            # JSON output
    python3 scripts/reputation.py --contributor zsxh1990  # single contributor
"""
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
USAGE_FILE = REPO / "data" / "usage_reports.json"
OUTPUT = REPO / "data" / "reputation.json"

# Weights
W_USAGE = 2.0       # usage_reports (strongest signal)
W_LESSONS = 1.0     # lessons contributed
W_REUSE = 0.2       # lessons reused by others
W_VERIFIED = 0.5    # lessons with verification section

# Anti-gaming
SIGMOID_K = 0.5     # steepness of sigmoid cap
SIGMOID_MID = 10    # midpoint (lessons count where cap = 0.5)

# Time decay
HALF_LIFE_DAYS = 90


def sigmoid_cap(x: float, k: float = SIGMOID_K, midpoint: float = SIGMOID_MID) -> float:
    """Sigmoid cap to limit per-PR weight explosion.

    Returns value in (0, 1). At x=midpoint, returns ~0.5.
    """
    return 1.0 / (1.0 + math.exp(-k * (x - midpoint)))


def time_decay(created: str, now: datetime = None) -> float:
    """Time decay factor. Recent contributions weighted more.

    Half-life = HALF_LIFE_DAYS. Returns value in (0, 1].
    """
    if not created:
        return 0.5  # unknown date → neutral weight

    now = now or datetime.now(timezone.utc)
    try:
        # Parse various date formats
        for fmt in ["%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                dt = datetime.strptime(created, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return 0.5

        days = max((now - dt).days, 0)
        return math.pow(0.5, days / HALF_LIFE_DAYS)
    except Exception:
        return 0.5


def parse_lesson(filepath: Path) -> dict:
    """Parse a lesson file for contributor and verification info."""
    text = filepath.read_text(encoding="utf-8", errors="replace")

    # Parse frontmatter
    fm = {}
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if m:
        try:
            fm = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            # Try YAML-like
            for line in m.group(1).strip().splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    fm[k.strip()] = v.strip()

    # Contributor: from frontmatter (author, contributor), NOT source (that's content origin)
    contributor = fm.get("author", fm.get("contributor", ""))
    if not contributor:
        # Fallback: git blame to find who committed this file
        try:
            import subprocess
            result = subprocess.run(
                ["git", "log", "--diff-filter=A", "--format=%an", "--", str(filepath)],
                capture_output=True, text=True, cwd=REPO, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                contributor = result.stdout.strip().splitlines()[0]
        except Exception:
            pass

    # Has verification section
    has_verification = bool(re.search(r'^## Verification', text, re.MULTILINE))

    # Created date
    created = fm.get("created", fm.get("date", ""))

    # Domain
    domain = fm.get("domain", "")

    # Status
    status = fm.get("status", "active")

    return {
        "path": str(filepath.relative_to(REPO)),
        "contributor": contributor,
        "has_verification": has_verification,
        "created": created,
        "domain": domain,
        "status": status,
    }


def scan_lessons() -> list[dict]:
    """Scan all lessons and extract metadata."""
    lessons = []
    for subdir in ["core", "contrib"]:
        dir_path = LESSONS_DIR / subdir
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("*.md")):
            if f.name == "README.md":
                continue
            lessons.append(parse_lesson(f))
    return lessons


def load_usage_reports() -> dict:
    """Load usage reports from data/usage_reports.json.

    Returns: {lesson_id: [{tool, outcome, date, contributor}, ...]}
    """
    if not USAGE_FILE.exists():
        return {}
    try:
        data = json.loads(USAGE_FILE.read_text())
        # Expected format: list of {lesson_id, tool, outcome, date}
        reports = defaultdict(list)
        for r in data:
            reports[r.get("lesson_id", "")].append(r)
        return dict(reports)
    except (json.JSONDecodeError, OSError):
        return {}


def compute_reputation(lessons: list[dict], usage: dict) -> list[dict]:
    """Compute reputation scores for all contributors."""
    contributors = defaultdict(lambda: {
        "login": "",
        "lessons_contributed": 0,
        "lessons_verified": 0,
        "lessons_reused": 0,
        "usage_reports": 0,
        "raw_score": 0.0,
        "decayed_score": 0.0,
        "sigmoid_capped_score": 0.0,
        "final_score": 0.0,
        "lesson_details": [],
    })

    now = datetime.now(timezone.utc)

    for lesson in lessons:
        author = lesson["contributor"]
        if not author:
            continue

        c = contributors[author]
        c["login"] = author
        c["lessons_contributed"] += 1

        if lesson["has_verification"]:
            c["lessons_verified"] += 1

        # Usage reports for this lesson
        lesson_id = Path(lesson["path"]).stem
        usage_count = len(usage.get(lesson_id, []))
        c["usage_reports"] += usage_count
        if usage_count > 0:
            c["lessons_reused"] += 1

        # Time decay weight for this lesson
        decay = time_decay(lesson["created"], now)

        # Per-lesson contribution
        lesson_score = (
            W_LESSONS * 1.0
            + W_VERIFIED * (1.0 if lesson["has_verification"] else 0.0)
            + W_REUSE * min(usage_count, 5)  # cap reuse per lesson
            + W_USAGE * min(usage_count, 10)  # cap usage per lesson
        ) * decay

        c["decayed_score"] += lesson_score
        c["lesson_details"].append({
            "path": lesson["path"],
            "score_contribution": round(lesson_score, 3),
            "decay": round(decay, 3),
            "usage_count": usage_count,
        })

    # Apply sigmoid cap and finalize
    for login, c in contributors.items():
        # Raw score (no decay, no cap)
        c["raw_score"] = (
            W_USAGE * c["usage_reports"]
            + W_LESSONS * c["lessons_contributed"]
            + W_REUSE * c["lessons_reused"]
            + W_VERIFIED * c["lessons_verified"]
        )

        # Sigmoid cap on the decayed score
        cap = sigmoid_cap(c["lessons_contributed"])
        c["sigmoid_capped_score"] = c["decayed_score"] * cap

        # Final score = sigmoid-capped decayed score
        c["final_score"] = round(c["sigmoid_capped_score"], 3)

    # Sort by final score
    ranked = sorted(contributors.values(), key=lambda x: x["final_score"], reverse=True)
    for i, c in enumerate(ranked):
        c["rank"] = i + 1

    return ranked


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compute contributor reputation scores")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--contributor", "-c", help="Show details for a single contributor")
    parser.add_argument("--save", action="store_true", help="Save to data/reputation.json")
    args = parser.parse_args()

    lessons = scan_lessons()
    usage = load_usage_reports()
    reputation = compute_reputation(lessons, usage)

    if args.contributor:
        match = [c for c in reputation if c["login"] == args.contributor]
        if not match:
            print(f"Contributor not found: {args.contributor}")
            sys.exit(1)
        if args.json:
            print(json.dumps(match[0], indent=2, ensure_ascii=False))
        else:
            c = match[0]
            print(f"\n{'=' * 50}")
            print(f"  {c['login']} (rank #{c['rank']})")
            print(f"{'=' * 50}")
            print(f"  Final score:        {c['final_score']}")
            print(f"  Raw score:          {c['raw_score']}")
            print(f"  Decayed score:      {round(c['decayed_score'], 3)}")
            print(f"  Sigmoid cap:        {round(sigmoid_cap(c['lessons_contributed']), 3)}")
            print(f"  Lessons:            {c['lessons_contributed']}")
            print(f"  Verified:           {c['lessons_verified']}")
            print(f"  Reused:             {c['lessons_reused']}")
            print(f"  Usage reports:      {c['usage_reports']}")
            print(f"\n  Lesson breakdown:")
            for ld in c["lesson_details"][:10]:
                print(f"    {ld['path']:50s} score={ld['score_contribution']:.3f} decay={ld['decay']:.3f}")
        return

    if args.json:
        print(json.dumps(reputation, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'Rank':<6} {'Contributor':<25} {'Score':<8} {'Lessons':<9} {'Verified':<10} {'Reused':<8} {'Usage':<6}")
        print("-" * 72)
        for c in reputation[:20]:
            print(f"#{c['rank']:<5} {c['login']:<25} {c['final_score']:<8} {c['lessons_contributed']:<9} {c['lessons_verified']:<10} {c['lessons_reused']:<8} {c['usage_reports']:<6}")

    if args.save:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(reputation, indent=2, ensure_ascii=False))
        print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
