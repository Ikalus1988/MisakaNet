#!/usr/bin/env python3
"""Intake coverage checker — normalize intake titles into search queries
and determine whether existing lessons cover the reported problem.

Usage:
    python3 scripts/intake_coverage.py --issue 1460
    python3 scripts/intake_coverage.py --title "Docker build fails with exit code 137..."
    python3 scripts/intake_coverage.py --issue 1460 --json
    python3 scripts/intake_coverage.py --issue 1460 --min-score 8

Normalizes intake titles (strips boilerplate, stop words, metadata) and
generates 1-3 candidate search queries. Calls the local search engine
directly (not the CLI, to avoid IP quota consumption).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Add repo root to path for imports
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from misakanet.search.engine import MisakaNetSearchEngine

# === Boilerplate patterns (mirrors intake_auto_review.py) ===
PIPELINE_PATTERNS = [
    r"^\*\*(?:Kind|Source|Dedup|Contributor|Node|Matched lesson[^*]*):\*\*.*$",
    r"^_Submitted via remote MCP.*$",
    r"^_Submitted via.*account.*$",
    r"^<br/?>\s*$",
    r"^<hr/?>\s*$",
    r"^---\s*$",
]

# Opire block
OPIRE_PATTERN = r"<details>.*?</details>"

# Metadata lines to strip
METADATA_LINES = [
    r"^##\s*(Problem|Error|Fix|Verification|Acceptance criteria|Background|任务|验收标准).*",
    r"^\*\*Kind:\*\*.*",
    r"^\*\*Source:\*\*.*",
    r"^\*\*Dedup:\*\*.*",
    r"^Signed-off-by:.*",
]

# Stop words (English + Portuguese + Chinese common words)
STOP_WORDS = {
    # English
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "out", "off", "over",
    "under", "again", "further", "then", "once", "here", "there", "when",
    "where", "why", "how", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "because", "but", "and", "or",
    "if", "while", "about", "up", "down", "that", "this", "these", "those",
    "it", "its", "he", "she", "they", "them", "we", "you", "i", "me",
    "my", "your", "his", "her", "their", "our", "what", "which", "who",
    "whom", "whose",
    # Portuguese
    "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da",
    "dos", "das", "em", "no", "na", "nos", "nas", "por", "para", "com",
    "que", "se", "não", "é", "são", "foi", "era", "tem", "tinha", "ter",
    "ser", "estar", "foi", "como", "mas", "ou", "se", "quando", "onde",
    "porque", "então", "muito", "mais", "menos", "já", "ainda", "também",
    "apenas", "mesmo", "outro", "outra", "outros", "outras", "este",
    "esta", "estes", "estas", "esse", "essa", "esses", "essas", "aquele",
    "aquela", "aqueles", "aquelas",
    # Chinese
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那",
    "被", "从", "把", "让", "用", "为", "以", "所", "但", "而", "如果",
    "或", "与", "及", "等", "能", "可以", "对", "中", "来", "个",
}


def strip_boilerplate(text: str) -> str:
    """Remove pipeline boilerplate, Opire blocks, and metadata lines."""
    # Remove Opire details blocks
    text = re.sub(OPIRE_PATTERN, "", text, flags=re.DOTALL)
    # Remove pipeline patterns
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(re.match(p, stripped, re.IGNORECASE) for p in PIPELINE_PATTERNS):
            continue
        if any(re.match(p, stripped, re.IGNORECASE) for p in METADATA_LINES):
            continue
        lines.append(line)
    return "\n".join(lines)


def normalize_title(title: str) -> str:
    """Normalize a title into a clean search query.

    Strip prefixes like [Intake]/[Question]/[Lesson], remove special chars,
    collapse whitespace.
    """
    # Strip bracket prefixes
    title = re.sub(r"^\[(?:Intake|Question|Lesson|Bug|Feature)\]\s*", "", title, flags=re.IGNORECASE)
    # Remove markdown formatting
    title = re.sub(r"[*_`#]", "", title)
    # Remove parenthetical references
    title = re.sub(r"\([^)]*\)", "", title)
    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()
    return title


def extract_queries(title: str, body: str = "") -> list[str]:
    """Generate 1-3 candidate search queries from intake title and body.

    Returns:
        List of query strings, most specific first.
    """
    queries = []

    # Query 1: full normalized title (minus stop words)
    normalized = normalize_title(title)
    words = re.findall(r"[a-zA-Z0-9_.\-/]+|[一-鿿]+", normalized)
    meaningful = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 1]
    if meaningful:
        queries.append(" ".join(meaningful))

    # Query 2: error strings / technical tokens (paths, codes, commands)
    error_tokens = []
    # Error codes: exit code 137, HTTP 404, etc.
    error_codes = re.findall(r"(?:exit\s*code|error|status|code)\s*[:=]?\s*(\d{2,3})", title, re.IGNORECASE)
    error_tokens.extend(error_codes)
    # Technical identifiers with dots/underscores/slashes
    tech_tokens = re.findall(r"[a-zA-Z0-9_]+\.[a-zA-Z0-9_.]+|[a-zA-Z0-9]+/[a-zA-Z0-9_/]+", title)
    error_tokens.extend(tech_tokens)
    # Quoted strings
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", title)
    error_tokens.extend(quoted)
    # Commands
    commands = re.findall(r"\b(?:docker|npm|pip|git|kubectl|alembic|webpack|vite|cargo|go)\b", title, re.IGNORECASE)
    error_tokens.extend(commands)
    # Specific technical words (not stop words)
    tech_words = [w for w in meaningful if re.match(r"^[a-z]+-[a-z]|^[a-z]+_[a-z]|error|fail|crash|timeout|denied", w, re.IGNORECASE)]
    error_tokens.extend(tech_words)

    if error_tokens and len(error_tokens) >= 2:
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in error_tokens:
            tl = t.lower()
            if tl not in seen:
                seen.add(tl)
                unique.append(t)
        queries.append(" ".join(unique[:6]))

    # Query 3: short keyword combo (domain + error)
    if body:
        body_clean = strip_boilerplate(body)
        body_words = re.findall(r"[a-zA-Z0-9_.\-/]+|[一-鿿]+", body_clean)
        body_meaningful = [w for w in body_words if w.lower() not in STOP_WORDS and len(w) > 2]
        # Take first few meaningful words from body
        if body_meaningful:
            short_query = " ".join(body_meaningful[:5])
            if short_query not in queries:
                queries.append(short_query)

    # Deduplicate
    seen = set()
    unique = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique[:3]


def fetch_issue(number: int) -> tuple[str, str]:
    """Fetch issue title and body via gh CLI."""
    result = subprocess.run(
        ["gh", "issue", "view", str(number), "--repo", "Ikalus1988/MisakaNet",
         "--json", "title,body", "--jq", "{title: .title, body: .body}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: Failed to fetch issue #{number}: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)
    return data["title"], data["body"]


def classify_results(results: list[dict], min_score: float) -> str:
    """Classify search results into coverage categories.

    Returns:
        'lesson-covered' if a non-FAQ lesson is found above threshold
        'faq-only' if only FAQ hits
        'no-coverage' if nothing relevant
    """
    has_lesson = False
    has_faq = False
    for r in results:
        if r["score"] < min_score:
            continue
        if r.get("status") == "faq" or "faq" in r.get("tags", []):
            has_faq = True
        else:
            has_lesson = True

    if has_lesson:
        return "lesson-covered"
    if has_faq:
        return "faq-only"
    return "no-coverage"


def run_coverage(title: str, body: str, min_score: float, top: int, as_json: bool) -> dict:
    """Run coverage check and return structured result."""
    engine = MisakaNetSearchEngine(REPO / "lessons")
    queries = extract_queries(title, body)

    result = {
        "title": title,
        "queries": [],
        "conclusion": "no-coverage",
    }

    best_conclusion = "no-coverage"
    for query in queries:
        hits = engine.search(query, top=top)
        classification = classify_results(hits, min_score)

        query_result = {
            "query": query,
            "hits": hits,
            "classification": classification,
        }
        result["queries"].append(query_result)

        # Upgrade conclusion: no-coverage < faq-only < lesson-covered
        if classification == "lesson-covered":
            best_conclusion = "lesson-covered"
        elif classification == "faq-only" and best_conclusion != "lesson-covered":
            best_conclusion = "faq-only"

    result["conclusion"] = best_conclusion
    return result


def print_human(result: dict, min_score: float):
    """Print human-readable output."""
    print(f"\n{'='*60}")
    print(f"Title: {result['title']}")
    print(f"{'='*60}")

    for i, qr in enumerate(result["queries"], 1):
        print(f"\nQuery {i}: {qr['query']}")
        print(f"  Classification: {qr['classification']}")
        if qr["hits"]:
            print(f"  Top hits:")
            for h in qr["hits"][:3]:
                marker = "★" if h["score"] >= min_score else "·"
                print(f"    {marker} [{h['score']:.1f}] {h['title'][:60]} ({h.get('status', '?')})")
        else:
            print("  No hits")

    conclusion_emoji = {"lesson-covered": "✅", "faq-only": "⚠️", "no-coverage": "❌"}
    print(f"\nConclusion: {conclusion_emoji.get(result['conclusion'], '?')} {result['conclusion']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Check intake coverage against existing lessons")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--issue", type=int, help="Issue number to check")
    group.add_argument("--title", type=str, help="Title text to check directly")
    parser.add_argument("--body", type=str, default="", help="Body text (with --title)")
    parser.add_argument("--min-score", type=float, default=0.7,
                        help="Minimum score threshold (default: 0.7, calibrated: #1460→0.7 hits CrashLoopBackOff, filters unrelated <0.6)")
    parser.add_argument("--top", type=int, default=5,
                        help="Top-N results to consider (default: 5)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.issue:
        title, body = fetch_issue(args.issue)
    else:
        title = args.title
        body = args.body

    result = run_coverage(title, body, args.min_score, args.top, args.json)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human(result, args.min_score)

    # Exit code: 0 if covered, 1 if not
    return 0 if result["conclusion"] == "lesson-covered" else 1


if __name__ == "__main__":
    sys.exit(main())
