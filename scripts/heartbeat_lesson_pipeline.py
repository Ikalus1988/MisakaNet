#!/usr/bin/env python3
"""Heartbeat Lesson Pipeline — fetch → extract → score → PR.

Automated daily lesson extraction from HN/Dev.to high-quality posts.
Each lesson must pass quality gate (≥75) before PR creation.

Usage:
    python3 scripts/heartbeat_lesson_pipeline.py                # full pipeline
    python3 scripts/heartbeat_lesson_pipeline.py --dry-run      # preview only
    python3 scripts/heartbeat_lesson_pipeline.py --target 5     # target count
    python3 scripts/heartbeat_lesson_pipeline.py --sources hn   # HN only
    python3 scripts/heartbeat_lesson_pipeline.py --threshold 80 # stricter gate
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons" / "contrib"
SCORER = REPO / "scripts" / "quality_scorer.py"
DOMAIN_KEYWORDS = {
    "security": ["vulnerability", "injection", "exploit", "CVE", "breach", "leak", "attack", "auth"],
    "mcp": ["MCP", "model context protocol", "tool server", "tool use"],
    "agent": ["agent", "autonomous", "multi-agent", "agentic", "orchestration"],
    "devops": ["CI/CD", "deploy", "kubernetes", "docker", "infrastructure", "SRE"],
    "llm": ["LLM", "GPT", "Claude", "Gemini", "fine-tune", "RAG", "embedding", "token"],
    "python": ["Python", "asyncio", "FastAPI", "Django", "pip", "virtualenv"],
    "frontend": ["React", "Vue", "Next.js", "TypeScript", "CSS", "Tailwind"],
}

# Content type filters — only these produce real lessons
LESSON_WORTHY_PATTERNS = [
    # Incident/postmortem (real event with timeline)
    r"(?i)(incident|postmortem|outage|downtime|breach|leak(ed)?|security incident|survival guide)",
    # Bug/fix (real code issue)
    r"(?i)(bug|fix(ed|es)?|patch|regression|crash|error|exception|segfault|broke|broken|doesn.t work)",
    # How-to/tutorial (teaches a procedure)
    r"(?i)(how to|tutorial|guide|step[- ]by[- ]step|walkthrough|setup|explained|built .*(?:server|tool|app|system))",
    # Lessons learned (explicit experience)
    r"(?i)(lessons? learned|what I learned|mistakes?|pitfall|gotcha|heads?[- ]up|what I built|what broke|what.s fixed)",
    # Performance/debugging (measurable problem)
    r"(?i)(performance|latency|memory leak|OOM|timeout|slow|optimiz(e|ation)|faster|speed up)",
    # Show HN with technical depth (not just a product launch)
    r"(?i)Show HN:.*(?:built|made|created|open[- ]source|library|tool|framework|server|engine|compiler)",
    # Configuration/deployment issue
    r"(?i)(config|deploy|migration|upgrade|compat|breaking change|deprecat|didn.t fix|it didn.t)",
    # Security vulnerability (concrete, not policy)
    r"(?i)(vulnerability|CVE|exploit|injection|token.*leak|secret.*expos|admin.*token|SQL.*inject)",
    # MCP/Agent technical content
    r"(?i)(MCP server|agent.*stack|tool.*use|context.*protocol|prompt.*inject)",
    # "I tried X" experience posts
    r"(?i)(I (?:tried|rewrote|replaced|migrated|built|debugged|fixed)|here.s what I)",
    # Database/infrastructure lessons
    r"(?i)(postgres|redis|kubernetes|docker|nginx|sqlite|database.*guide|database.*lesson)",
]

# Anti-patterns — these are NOT lessons (news/opinion/announcement)
NOT_LESSON_PATTERNS = [
    r"(?i)^(?:Announcing|Introducing|Launch|Release)",   # product announcements
    r"(?i)(opinion|editorial|think piece|perspective)",    # opinion pieces
    r"(?i)(has died|obituary|memorial)",                   # obituaries
    r"(?i)(regulation|policy|government|FCC|EU|congress)", # policy news
    r"(?i)(advertise|ad|sponsor|pricing)",                 # ads/pricing
    r"(?i)(competitive with|so ta|state[- ]of[- ]the[- ]art|benchmark)", # benchmark comparisons
    r"(?i)(strategy|winning|losing|market|revenue)",       # business strategy
]

# ─── Sources ───────────────────────────────────────────────────────────────

def fetch_hn_stories(min_points: int = 100, days: int = 7) -> list[dict]:
    """Fetch high-point HN stories from Algolia API."""
    cutoff = int((datetime.utcnow() - timedelta(days=days)).timestamp())
    url = (
        f"https://hn.algolia.com/api/v1/search?"
        f"tags=story&hitsPerPage=30"
        f"&numericFilters=points>{min_points},created_at_i>{cutoff}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MisakaNet-Heartbeat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"⚠️  HN API error: {e}", file=sys.stderr)
        return []

    stories = []
    for h in data.get("hits", []):
        stories.append({
            "source": "hn",
            "id": h["objectID"],
            "title": h.get("title", ""),
            "url": h.get("url", ""),
            "points": h.get("points", 0),
            "comments": h.get("num_comments", 0),
            "author": h.get("author", ""),
            "created_at": h.get("created_at", ""),
            "hn_url": f"https://news.ycombinator.com/item?id={h['objectID']}",
        })
    return stories


def fetch_hn_by_keyword(keyword: str, min_points: int = 30, limit: int = 5) -> list[dict]:
    """Search HN by keyword for targeted technical content."""
    url = (
        f"https://hn.algolia.com/api/v1/search?"
        f"query={urllib.request.quote(keyword)}&tags=story"
        f"&hitsPerPage={limit}&numericFilters=points>{min_points}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MisakaNet-Heartbeat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"⚠️  HN keyword search error for '{keyword}': {e}", file=sys.stderr)
        return []

    stories = []
    for h in data.get("hits", []):
        stories.append({
            "source": "hn",
            "id": h["objectID"],
            "title": h.get("title", ""),
            "url": h.get("url", ""),
            "points": h.get("points", 0),
            "comments": h.get("num_comments", 0),
            "author": h.get("author", ""),
            "created_at": h.get("created_at", ""),
            "hn_url": f"https://news.ycombinator.com/item?id={h['objectID']}",
        })
    return stories


TECH_KEYWORDS = [
    "postmortem incident",
    "prompt injection",
    "debugging lesson",
    "performance optimization",
    "memory leak",
    "database migration",
    "deploy rollback",
    "security vulnerability",
    "CI CD broken",
    "kubernetes crash",
    "MCP server",
    "agent architecture",
    "Redis cache",
    "Postgres tuning",
    "Docker networking",
]


def fetch_devto_articles(tag: str = "mcp", days: int = 7, top: int = 7) -> list[dict]:
    """Fetch top Dev.to articles."""
    url = f"https://dev.to/api/articles?tag={tag}&top={top}&per_page=20"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MisakaNet-Heartbeat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"⚠️  Dev.to API error: {e}", file=sys.stderr)
        return []

    cutoff = datetime.utcnow() - timedelta(days=days)
    articles = []
    for a in data:
        pub = a.get("published_at", "")
        if pub:
            try:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if pub_dt.replace(tzinfo=None) < cutoff:
                    continue
            except ValueError:
                pass
        articles.append({
            "source": "devto",
            "id": str(a["id"]),
            "title": a["title"],
            "url": a["url"],
            "points": a.get("public_reactions_count", 0),
            "comments": a.get("comments_count", 0),
            "author": a.get("user", {}).get("username", ""),
            "tags": a.get("tag_list", []),
        })
    return articles


# ─── Scoring & Ranking ────────────────────────────────────────────────────

def classify_domain(title: str, url: str = "") -> str:
    """Auto-classify domain from title/URL."""
    text = f"{title} {url}".lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            return domain
    return "engineering"


def is_lesson_worthy(item: dict) -> bool:
    """Coarse filter: reject obvious non-lesson content (news/ads/obituaries).
    Let borderline cases through — LLM will do the real filtering."""
    title = item.get("title", "")
    url = item.get("url", "")

    # Hard reject: these are NEVER lessons
    for pattern in NOT_LESSON_PATTERNS:
        if re.search(pattern, title):
            return False

    # Accept: explicit lesson-worthy patterns
    for pattern in LESSON_WORTHY_PATTERNS:
        if re.search(pattern, f"{title} {url}"):
            return True

    # Accept Dev.to with technical tags
    if item.get("source") == "devto":
        tech_tags = {"mcp", "agent", "devops", "python", "typescript", "security", "debugging"}
        if set(item.get("tags", [])) & tech_tags:
            return True

    # Accept HN posts with decent engagement (let LLM decide if it's a lesson)
    if item.get("source") == "hn" and item.get("points", 0) >= 200:
        return True

    return False



def llm_is_lesson_worthy(candidate: dict, content: str) -> bool:
    """Fine filter: ask LLM if article contains a reusable lesson."""
    prompt = (
        "You are a technical content evaluator. Read this article and decide:\n"
        "Does it contain a REUSABLE technical lesson that an engineer could apply?\n\n"
        "A lesson must have:\n"
        "- A specific technical problem (not generic advice)\n"
        "- A concrete cause (not vague 'it's hard')\n"
        "- An actionable solution or mitigation (not just commentary)\n\n"
        "NOT lessons: product announcements, opinion pieces, news, benchmarks, strategy analysis.\n\n"
        'Reply with ONLY a JSON object like: {"is_lesson": true, "reason": "one sentence why"}\n\n'
        f"ARTICLE TITLE: {candidate['title']}\n"
        f"ARTICLE CONTENT:\n{content[:3000]}"
    )
    result = call_llm(prompt, max_tokens=100)
    if not result:
        return False  # conservative: skip if LLM fails
    try:
        # Extract JSON from response
        m = re.search(r"\{[^}]+\}", result)
        if m:
            data = json.loads(m.group())
            worthy = data.get("is_lesson", False)
            reason = data.get("reason", "")
            if not worthy:
                print(f"         🚫 LLM skip: {reason}")
            return worthy
    except (json.JSONDecodeError, KeyError):
        pass
    return False


def rank_candidate(item: dict) -> float:
    """Weighted score for prioritization."""
    score = 0.0
    score += min(item.get("points", 0), 500) * 0.1  # cap at 50 pts
    score += min(item.get("comments", 0), 200) * 0.05  # cap at 10 pts
    # Bonus for security/MCP topics
    title_lower = item.get("title", "").lower()
    if any(kw in title_lower for kw in ["security", "vulnerability", "injection"]):
        score += 20
    if "mcp" in title_lower:
        score += 15
    if "agent" in title_lower:
        score += 10
    # Strong bonus for incident/postmortem patterns
    if any(kw in title_lower for kw in ["incident", "postmortem", "outage", "breach", "leak"]):
        score += 30
    if any(kw in title_lower for kw in ["how to", "tutorial", "lesson", "pitfall"]):
        score += 25
    return score


def deduplicate(candidates: list[dict], existing_titles: set[str]) -> list[dict]:
    """Remove duplicates by title similarity and already-covered topics."""
    seen = set()
    unique = []
    for c in candidates:
        # Normalize title for dedup
        norm = re.sub(r"[^a-z0-9]", "", c["title"].lower())[:40]
        if norm in seen:
            continue
        # Check against existing lessons
        if any(norm[:20] in t for t in existing_titles):
            continue
        seen.add(norm)
        unique.append(c)
    return unique


# ─── Lesson Generation ────────────────────────────────────────────────────

def fetch_article_content(url: str) -> str | None:
    """Fetch article text content."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MisakaNet/1.0)"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Strip HTML
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", "\n", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r" +", " ", text).strip()
        return text[:8000]  # cap for LLM context
    except Exception as e:
        print(f"⚠️  Fetch failed for {url}: {e}", file=sys.stderr)
        return None


def call_llm(prompt: str, max_tokens: int = 4000) -> str | None:
    """Call LLM via Anthropic-compatible gateway (uses ANTHROPIC_* env vars)."""
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not base_url or not api_key:
        print("❌ ANTHROPIC_BASE_URL and ANTHROPIC_API_KEY required", file=sys.stderr)
        return None

    url = f"{base_url}/v1/messages"
    body = json.dumps({
        "model": "ppio/pa/claude-haiku-4-5",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data.get("content", [{}])[0].get("text", "")
    except Exception as e:
        print(f"⚠️  LLM call failed: {e}", file=sys.stderr)
        return None


def generate_lesson_prompt(candidate: dict, content: str) -> str:
    """Generate LLM prompt for lesson extraction."""
    return textwrap.dedent(f"""\
    Extract a MisakaNet lesson from this article. Output ONLY the lesson markdown file, nothing else.

    REQUIREMENTS (must follow exactly or quality gate fails):
    1. First line: JSON frontmatter between --- delimiters with these fields:
       {{"title": "...", "domain": "...", "tags": [...], "language": "en", "status": "published",
         "source": "article_url", "created": "{datetime.now().strftime('%Y-%m-%d')}", "confidence": "0.85"}}
    2. Required sections in this exact order:
       - ## Problem (specific scenario, not generic)
       - ## Root Cause (technical detail, not vague)
       - ## Solution (actionable steps with code/config examples)
       - ## Verification (executable commands with expected output)
       - ## Notes (generalization to other contexts)
       - ## References (source URL + HN discussion if applicable)
    3. Code blocks MUST have language tags (```python, ```sql, ```bash, etc.)
    4. Problem section must describe a CONCRETE scenario (who, what tool, what action, what went wrong)
    5. Solution must have numbered steps with code examples
    6. Verification must have copy-pasteable commands

    SOURCE: {candidate['url']}
    TITLE: {candidate['title']}
    POINTS: {candidate.get('points', 0)}

    ARTICLE CONTENT:
    {content[:6000]}
    """)


# ─── Quality Gate ──────────────────────────────────────────────────────────

def run_quality_scorer(lesson_path: Path, threshold: int = 75) -> dict:
    """Run quality scorer on a single lesson file."""
    result = subprocess.run(
        [sys.executable, str(SCORER), str(lesson_path), "--json"],
        capture_output=True, text=True, cwd=str(REPO),
    )
    try:
        data = json.loads(result.stdout)
        lesson = data["lessons"][0]
        return {
            "score": lesson["score"],
            "grade": lesson["grade"],
            "pass": lesson["score"] >= threshold,
            "breakdown": lesson["breakdown"],
        }
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return {"score": 0, "grade": "F", "pass": False, "error": str(e)}


def save_and_score_lesson(content: str, slug: str, threshold: int = 75) -> dict | None:
    """Save lesson to disk and run quality gate. Returns None if fails."""
    path = LESSONS_DIR / f"{slug}.md"
    path.write_text(content, encoding="utf-8")

    result = run_quality_scorer(path, threshold)
    if result["pass"]:
        print(f"  ✅ {slug}: {result['score']}/100 ({result['grade']})")
        return result
    else:
        print(f"  ❌ {slug}: {result['score']}/100 ({result['grade']}) — below {threshold}")
        # Clean up failed lesson
        path.unlink(missing_ok=True)
        return None


# ─── Git Operations ────────────────────────────────────────────────────────

def git_operations(lesson_files: list[Path], branch_name: str, push_target: str = "origin") -> bool:
    """Create branch, commit, push, and create PR.

    push_target: "origin" (fork, default) or "upstream" (Ikalus1988/MisakaNet)
    """
    try:
        # Ensure upstream remote exists
        if push_target == "upstream":
            result = subprocess.run(["git", "remote", "get-url", "upstream"], capture_output=True, text=True, cwd=REPO)
            if result.returncode != 0:
                subprocess.run(["git", "remote", "add", "upstream", "https://github.com/Ikalus1988/MisakaNet.git"], cwd=REPO, check=True, capture_output=True)
            fetch_ref = "upstream/main"
            push_ref = f"upstream {branch_name}"
        else:
            fetch_ref = "origin/main"
            push_ref = f"origin {branch_name}"

        # Create branch
        subprocess.run(["git", "fetch", push_target if push_target == "upstream" else "origin", "main"], cwd=REPO, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-b", branch_name, fetch_ref], cwd=REPO, check=True, capture_output=True)

        # Add files
        for f in lesson_files:
            subprocess.run(["git", "add", str(f.relative_to(REPO))], cwd=REPO, check=True, capture_output=True)

        # Commit
        count = len(lesson_files)
        msg = f"feat(lessons): {count} high-quality lessons from heartbeat pipeline\n\n"
        msg += "Lessons extracted from HN/Dev.to high-point posts.\n"
        msg += f"All passed quality gate (≥75/100).\n\n"
        msg += "Signed-off-by: Eric Jia <445655361@qq.com>"
        subprocess.run(["git", "commit", "-m", msg], cwd=REPO, check=True, capture_output=True)

        # Push
        subprocess.run(["git", "push", push_target, branch_name], cwd=REPO, check=True, capture_output=True)

        # Create PR (only needed when pushing to fork)
        pr_body = f"## Heartbeat Lesson Batch\n\n"
        pr_body += f"**{count} lessons** extracted from high-point HN/Dev.to posts.\n\n"
        pr_body += "### Quality Scores\n\n"
        pr_body += "| Lesson | Score | Source |\n|--------|-------|--------|\n"
        for f in lesson_files:
            pr_body += f"| `{f.stem}` | ✅ ≥75 | auto-extracted |\n"
        pr_body += "\n---\n🤖 Auto-generated by heartbeat lesson pipeline"

        title_count = min(count, 10)
        pr_title = f"feat(lessons): {title_count} community lessons (heartbeat batch)"

        if push_target == "upstream":
            # Direct push to upstream — create PR from branch
            result = subprocess.run(
                ["gh", "pr", "create", "--repo", "Ikalus1988/MisakaNet",
                 "--head", branch_name, "--base", "main",
                 "--title", pr_title, "--body", pr_body],
                capture_output=True, text=True, cwd=REPO,
            )
        else:
            # Push to fork — create PR from fork:branch to upstream
            result = subprocess.run(
                ["gh", "pr", "create", "--repo", "Ikalus1988/MisakaNet",
                 "--head", f"zsxh1990:{branch_name}", "--base", "main",
                 "--title", pr_title, "--body", pr_body],
                capture_output=True, text=True, cwd=REPO,
            )
        if result.returncode == 0:
            pr_url = result.stdout.strip()
            print(f"\n🎉 PR created: {pr_url}")
            return True
        else:
            print(f"❌ PR creation failed: {result.stderr}")
            return False

    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        return False


# ─── Main Pipeline ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Heartbeat Lesson Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't create PR")
    parser.add_argument("--target", type=int, default=10, help="Target lesson count")
    parser.add_argument("--threshold", type=int, default=75, help="Quality gate threshold")
    parser.add_argument("--sources", default="hn,devto", help="Comma-separated sources")
    parser.add_argument("--min-points", type=int, default=100, help="Min HN points")
    parser.add_argument("--days", type=int, default=7, help="Lookback days")
    args = parser.parse_args()

    print(f"=== Heartbeat Lesson Pipeline ===")
    print(f"Target: {args.target} lessons | Threshold: {args.threshold} | Sources: {args.sources}")
    print()

    # 1. Fetch candidates
    candidates = []
    if "hn" in args.sources:
        print("📡 Fetching HN stories (popularity)...")
        candidates.extend(fetch_hn_stories(args.min_points, args.days))
        print("📡 Fetching HN stories (keyword search)...")
        for kw in TECH_KEYWORDS:
            candidates.extend(fetch_hn_by_keyword(kw, min_points=30, limit=3))
    if "devto" in args.sources:
        print("📡 Fetching Dev.to articles...")
        for tag in ["mcp", "agent", "devops", "python"]:
            candidates.extend(fetch_devto_articles(tag, args.days))

    print(f"📊 Raw candidates: {len(candidates)}")

    # 2. Deduplicate & rank
    existing = set()
    for f in LESSONS_DIR.glob("*.md"):
        title_match = re.search(r'"title":\s*"([^"]+)"', f.read_text(errors="replace"))
        if title_match:
            norm = re.sub(r"[^a-z0-9]", "", title_match.group(1).lower())[:40]
            existing.add(norm)

    candidates = deduplicate(candidates, existing)
    # Filter for lesson-worthy content (not news/opinion/announcement)
    before_filter = len(candidates)
    candidates = [c for c in candidates if is_lesson_worthy(c)]
    print(f"📊 After lesson-worthiness filter: {len(candidates)} (dropped {before_filter - len(candidates)} news/opinion)")
    candidates.sort(key=rank_candidate, reverse=True)
    candidates = candidates[:args.target * 3]  # fetch 3x to account for quality failures

    print(f"📊 After dedup & rank: {len(candidates)}")
    print()

    if args.dry_run:
        print("=== DRY RUN — Top candidates ===")
        for i, c in enumerate(candidates[:args.target], 1):
            domain = classify_domain(c["title"], c.get("url", ""))
            print(f"  {i}. [{domain}] ⭐{c.get('points',0)} | {c['title'][:60]}")
            print(f"     {c.get('url','')}")
        return

    # 3. Extract & score via LLM
    print(f"📝 Extracting lessons via LLM (target={args.target})...")
    passed = []
    failed = 0
    for i, candidate in enumerate(candidates[:args.target + 5]):  # extra buffer for failures
        if len(passed) >= args.target:
            break
        domain = classify_domain(candidate["title"], candidate.get("url", ""))
        url = candidate.get("url", "")
        if not url:
            print(f"  ⏭️  [{domain}] No URL: {candidate['title'][:50]}")
            continue

        print(f"\n  [{i+1}/{args.target+5}] [{domain}] {candidate['title'][:60]}")
        print(f"         Fetching {url[:80]}...")

        content = fetch_article_content(url)
        if not content or len(content) < 200:
            print(f"         ⏭️  Content too short or fetch failed")
            continue

        # LLM gate: check if article is actually lesson-worthy
        if not llm_is_lesson_worthy(candidate, content):
            print(f"         ⏭️  Not a reusable lesson (news/opinion/announcement)")
            continue

        # Generate slug from title
        slug = re.sub(r"[^a-z0-9]+", "-", candidate["title"].lower())[:60].strip("-")
        prompt = generate_lesson_prompt(candidate, content)

        print(f"         Calling LLM...")
        lesson_text = call_llm(prompt)
        if not lesson_text:
            print(f"         ❌ LLM returned nothing")
            failed += 1
            continue

        # Strip markdown fences if LLM wrapped them
        lesson_text = re.sub(r"^```(?:markdown)?\s*\n", "", lesson_text)
        lesson_text = re.sub(r"\n```\s*$", "", lesson_text)

        # Save and score
        result = save_and_score_lesson(lesson_text, slug, args.threshold)
        if result:
            passed.append(LESSONS_DIR / f"{slug}.md")
        else:
            failed += 1

        # Rate limit — 1 req/sec
        if i < args.target + 4:
            import time
            time.sleep(1)

    # 4. Create PR if lessons passed
    print(f"\n{'='*50}")
    print(f"Results: {len(passed)} passed, {failed} failed, target was {args.target}")

    if passed and not args.dry_run:
        branch = f"feat/heartbeat-lessons-{datetime.now().strftime('%Y%m%d')}"
        push_target = "origin"
        git_operations(passed, branch, push_target)
    elif passed and args.dry_run:
        print("\nDRY RUN — would create PR with:")
        for f in passed:
            print(f"  ✅ {f.name}")
    else:
        print("\n❌ No lessons passed quality gate — no PR created")


if __name__ == "__main__":
    main()
