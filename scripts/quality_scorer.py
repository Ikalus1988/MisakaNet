#!/usr/bin/env python3
"""Lesson Quality Scorer — 100-point rubric implementation.

Implements the scoring system from lessons/LESSON_QUALITY_SCORING.md:
  - Metadata completeness (20 pts)
  - Structure completeness (25 pts)
  - Content quality (35 pts)
  - Dedup & generalization (10 pts)
  - Source trust (10 pts)

Usage:
    python3 scripts/quality_scorer.py lessons/contrib/xxx.md   # single file
    python3 scripts/quality_scorer.py lessons/                  # all lessons
    python3 scripts/quality_scorer.py --threshold 75            # exit 1 if any < 75
    python3 scripts/quality_scorer.py --json                    # JSON output
    python3 scripts/quality_scorer.py --ci                      # CI mode (threshold=75, JSON, exit codes)
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"
sys.path.insert(0, str(REPO))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECTION_RE = re.compile(r"^##\s+(.+)", re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```(\w*)", re.MULTILINE)
LINK_RE = re.compile(r"https?://[^\s)>\]]+", re.I)
TABLE_RE = re.compile(r"^\|.*\|.*\|", re.MULTILINE)
LIST_RE = re.compile(r"^\s*[-*]\s+\S", re.MULTILINE)
WORD_RE = re.compile(r"\b\w+\b")
TODO_RE = re.compile(r"\b(TODO|FIXME|coming soon|to be written|placeholder)\b", re.I)

REQUIRED_SECTIONS = ["problem", "root cause", "solution", "verification"]
OPTIONAL_SECTIONS = ["notes"]

# Org-sensitive patterns that indicate non-generalizable content
ORG_SENSITIVE_RE = re.compile(
    r"(xiaomi|mify|mi\.feishu|内部域名|内部 API|公司内部)", re.I
)

# Credible source domains
CREDIBLE_DOMAINS = re.compile(
    r"github\.com|gitlab\.com|stackoverflow\.com|docs\.\w+\.\w+|"
    r"developer\.\w+\.\w+|wiki\.\w+\.\w+|learn\.\w+\.\w+", re.I
)

# Resolution signals
RESOLVED_RE = re.compile(
    r"(resolved|✅|merged|verified|fixed|closed|已解决|已修复|已验证)", re.I
)

BANNED_PREFIXES = ("cc-connect", "hermes-", "calico-", "prometheus-")


def read_file(path: Path) -> str:
    """Read file with fallback encodings."""
    data = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_frontmatter(content: str) -> tuple[dict | None, str | None]:
    """Extract JSON/YAML frontmatter from lesson content."""
    m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return None, "No frontmatter block"
    raw = m.group(1).strip()
    try:
        fm = json.loads(raw)
        return fm, None
    except json.JSONDecodeError:
        pass
    # YAML-like fallback
    try:
        fm = {}
        current_key = None
        current_list = None
        for line in raw.split("\n"):
            if line.strip().startswith("- "):
                if current_key and current_list is not None:
                    current_list.append(line.strip()[2:].strip().strip("\"'"))
                continue
            line = line.strip()
            if not line:
                continue
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
        if current_key and current_list is not None:
            fm[current_key] = current_list
        return (fm, None) if fm else (None, "Empty frontmatter")
    except Exception:
        return None, "Frontmatter parse error"


def get_body(content: str) -> str:
    """Strip frontmatter, return body."""
    return re.sub(r"^---\s*\n.*?\n---\s*\n?", "", content, count=1, flags=re.DOTALL)


def find_sections(body: str) -> list[str]:
    """Return lowercased section headings."""
    return [s.strip().lower() for s in SECTION_RE.findall(body)]


def word_count(text: str) -> int:
    """Count words (handles mixed CJK + latin)."""
    cjk = len(re.findall(r"[一-鿿㐀-䶿]", text))
    latin = len(WORD_RE.findall(text))
    return cjk + latin


# ---------------------------------------------------------------------------
# Scoring dimensions
# ---------------------------------------------------------------------------

def score_metadata(fm: dict | None, content: str) -> tuple[int, list[str]]:
    """Score metadata completeness (max 20)."""
    pts = 0
    notes = []

    # Frontmatter exists (4)
    if fm is None:
        return 0, ["No frontmatter"]

    pts += 4

    # JSON parseable (already passed if fm is not None)
    pts += 4

    # title >= 10 chars (2)
    title = fm.get("title", "")
    if len(title) >= 10:
        pts += 2
    else:
        notes.append(f"Title too short ({len(title)} chars, need >=10)")

    # domain non-empty (2)
    domain = fm.get("domain", "")
    if domain and len(domain) >= 2:
        pts += 2
    else:
        notes.append("Missing or empty domain")

    # tags >= 3 (3)
    tags = fm.get("tags", [])
    if isinstance(tags, list) and len(tags) >= 3:
        pts += 3
    else:
        notes.append(f"Tags: {len(tags) if isinstance(tags, list) else 0} (need >=3)")

    # source present (2)
    if fm.get("source"):
        pts += 2
    else:
        notes.append("Missing source")

    # created date valid (2)
    created = fm.get("created", "")
    if re.match(r"\d{4}-\d{2}-\d{2}", str(created)):
        pts += 2
    else:
        notes.append("Missing or invalid created date")

    # confidence in [0,1] (1)
    conf = fm.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if 0 <= c <= 1:
                pts += 1
            else:
                notes.append(f"Confidence out of range: {c}")
        except (ValueError, TypeError):
            notes.append(f"Confidence not numeric: {conf}")
    else:
        notes.append("Missing confidence")

    return min(pts, 20), notes


def score_structure(body: str) -> tuple[int, list[str]]:
    """Score structure completeness (max 25)."""
    pts = 0
    notes = []
    sections = find_sections(body)

    # Each required section (5 pts each, 20 total)
    for req in REQUIRED_SECTIONS:
        if any(req in s for s in sections):
            pts += 5
        else:
            notes.append(f"Missing section: {req.title()}")

    # Notes section (3 pts)
    if any("notes" in s for s in sections):
        pts += 3
    else:
        notes.append("Missing section: Notes")

    # Section order (2 pts)
    positions = []
    for req in REQUIRED_SECTIONS:
        for i, s in enumerate(sections):
            if req in s:
                positions.append(i)
                break
        else:
            positions.append(-1)
    if all(p >= 0 for p in positions) and positions == sorted(positions):
        pts += 2
    elif any(p < 0 for p in positions):
        notes.append("Cannot verify section order (missing sections)")
    else:
        notes.append("Sections out of order (expected Problem→Root Cause→Solution→Verification)")

    return min(pts, 25), notes


def score_content(body: str) -> tuple[int, list[str]]:
    """Score content quality (max 35)."""
    pts = 0
    notes = []

    # Code blocks (8 pts)
    code_blocks = CODE_BLOCK_RE.findall(body)
    if code_blocks:
        pts += 8
        # Language-tagged code (3 pts)
        if any(c for c in code_blocks if c):
            pts += 3
        else:
            notes.append("Code blocks without language tags")
    else:
        notes.append("No code blocks found")

    # Problem specificity (5 pts): has specific error/scenario
    if re.search(
        r"(error|fail|exception|timeout|crash|bug|issue|错误|失败|异常|超时)", body, re.I
    ):
        pts += 5
    else:
        notes.append("Problem description lacks specificity")

    # Actionable solution (8 pts)
    sol_match = re.search(
        r"##\s+Solution(.*?)(?=##\s|\Z)", body, re.DOTALL | re.I
    )
    if sol_match:
        sol_text = sol_match.group(1)
        actionable_signals = len(
            re.findall(
                r"(step|步骤|run|执行|set|配置|add|添加|install|安装|create|创建|update|更新|修改|修改|使用|使用|命令|command|```)",
                sol_text,
                re.I,
            )
        )
        if actionable_signals >= 3:
            pts += 8
        elif actionable_signals >= 1:
            pts += 4
            notes.append("Solution could be more actionable")
        else:
            notes.append("Solution lacks actionable steps")
    else:
        notes.append("No Solution section found")

    # Tables or structured lists (5 pts)
    if TABLE_RE.search(body) or len(LIST_RE.findall(body)) >= 3:
        pts += 5
    else:
        notes.append("No tables or structured lists")

    # External links (3 pts)
    if LINK_RE.search(body):
        pts += 3
    else:
        notes.append("No external links/references")

    # Word count >= 300 (3 pts)
    wc = word_count(body)
    if wc >= 300:
        pts += 3
    else:
        notes.append(f"Word count too low: {wc} (need >=300)")

    # TODO/FIXME penalty (already handled in validate, but flag here too)
    if TODO_RE.search(body):
        notes.append("Contains TODO/FIXME placeholders")

    return min(pts, 35), notes


def score_dedup(
    content: str,
    all_docs: list[tuple[str, set[str]]] | None = None,
    current_file: str = "",
) -> tuple[int, list[str]]:
    """Score dedup & generalization (max 10)."""
    pts = 0
    notes = []

    # No org-sensitive info (3 pts)
    if not ORG_SENSITIVE_RE.search(content):
        pts += 3
    else:
        notes.append("Contains org-sensitive information (xiaomi/mify/internal)")

    # Generalizable (2 pts): no hardcoded user paths, specific usernames
    if not re.search(r"/Users/\w+|/home/\w+|C:\\Users\\\w+", content):
        pts += 2
    else:
        notes.append("Contains hardcoded user paths")

    # No duplicate with existing (5 pts)
    if all_docs is not None:
        try:
            from misakanet.search.engine import _tokenize

            my_tokens = set(_tokenize(content[:2000]))
            max_sim = 0.0
            most_similar = ""
            current_basename = Path(current_file).name
            for fname, tokens in all_docs:
                # Skip self-comparison (match by basename since engine uses basenames)
                if fname == current_basename or fname == current_file:
                    continue
                if not tokens:
                    continue
                jaccard = len(my_tokens & tokens) / len(my_tokens | tokens) if my_tokens | tokens else 0
                if jaccard > max_sim:
                    max_sim = jaccard
                    most_similar = fname
            if max_sim < 0.5:
                pts += 5
            elif max_sim < 0.8:
                pts += 2
                notes.append(f"Similar to {most_similar} (sim={max_sim:.2f}), consider merging")
            else:
                notes.append(f"Near-duplicate of {most_similar} (sim={max_sim:.2f}), should merge")
        except ImportError:
            pts += 3  # partial credit if search engine not available
            notes.append("Cannot check dedup (search engine not available)")
    else:
        pts += 5  # no corpus to compare against

    return min(pts, 10), notes


def score_source_trust(fm: dict | None, content: str) -> tuple[int, list[str]]:
    """Score source trust (max 10)."""
    pts = 0
    notes = []

    if fm is None:
        return 0, ["No frontmatter"]

    # Source URL present and credible (3 pts)
    source = fm.get("source", "")
    if source:
        if CREDIBLE_DOMAINS.search(source):
            pts += 3
        elif LINK_RE.search(source):
            pts += 2
            notes.append("Source URL is not from a well-known domain")
        else:
            pts += 1
            notes.append("Source is a name, not a URL")
    else:
        notes.append("No source field")

    # Verified/expert endorsement (4 pts)
    if fm.get("verified_date") or fm.get("domain_expert"):
        pts += 4
    elif fm.get("status") == "published" and float(fm.get("confidence", 0)) >= 0.8:
        pts += 2
        notes.append("Published with high confidence but no verification date")

    # Problem resolved (3 pts): signals in body
    if RESOLVED_RE.search(content):
        pts += 3
    else:
        notes.append("No resolution signal in content")

    return min(pts, 10), notes


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_lesson(
    filepath: Path,
    all_docs: list[tuple[str, set[str]]] | None = None,
) -> dict:
    """Score a single lesson file. Returns full rubric breakdown."""
    content = read_file(filepath)
    fm, fm_err = extract_frontmatter(content)
    body = get_body(content)

    # Compute relative path safely (files outside REPO use basename)
    try:
        rel_path = str(filepath.relative_to(REPO))
    except ValueError:
        rel_path = filepath.name

    meta_pts, meta_notes = score_metadata(fm, content)
    struct_pts, struct_notes = score_structure(body)
    content_pts, content_notes = score_content(body)
    dedup_pts, dedup_notes = score_dedup(content, all_docs, current_file=rel_path)
    trust_pts, trust_notes = score_source_trust(fm, content)

    total = meta_pts + struct_pts + content_pts + dedup_pts + trust_pts

    if total >= 85:
        grade = "A"
    elif total >= 75:
        grade = "B"
    else:
        grade = "F"

    return {
        "file": rel_path,
        "score": total,
        "grade": grade,
        "pass": total >= 75,
        "breakdown": {
            "metadata": {"score": meta_pts, "max": 20, "notes": meta_notes},
            "structure": {"score": struct_pts, "max": 25, "notes": struct_notes},
            "content": {"score": content_pts, "max": 35, "notes": content_notes},
            "dedup": {"score": dedup_pts, "max": 10, "notes": dedup_notes},
            "trust": {"score": trust_pts, "max": 10, "notes": trust_notes},
        },
    }


def load_corpus() -> list[tuple[str, set[str]]]:
    """Load all lesson docs for dedup comparison."""
    try:
        from misakanet.search.engine import LESSONS, _load_docs_cached, _tokenize

        docs = _load_docs_cached(LESSONS, is_lesson=True)
        return [(d.filename, set(_tokenize(d.content[:2000]))) for d in docs]
    except ImportError:
        return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    json_mode = "--json" in args
    ci_mode = "--ci" in args
    threshold = 75 if ci_mode else None

    # Parse --threshold N
    for i, arg in enumerate(args):
        if arg == "--threshold" and i + 1 < len(args):
            threshold = int(args[i + 1])

    # Determine files
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        target = Path(positional[0]).resolve()
        if target.is_dir():
            files = sorted(target.rglob("*.md"))
            files = [
                f
                for f in files
                if f.name not in ("index.md", "TEMPLATE.md", "README.md")
                and "_archive" not in f.parts
            ]
        else:
            files = [target]
    else:
        files = sorted(LESSONS_DIR.rglob("*.md"))
        files = [
            f
            for f in files
            if f.name not in ("index.md", "TEMPLATE.md", "README.md")
            and "_archive" not in f.parts
        ]

    # Load corpus for dedup (only when scoring multiple files)
    all_docs = load_corpus() if len(files) > 1 else None

    results = []
    for fp in files:
        try:
            r = score_lesson(fp, all_docs)
            results.append(r)
        except Exception as e:
            print(f"ERROR: {fp}: {e}", file=sys.stderr)
            results.append({"file": str(fp.relative_to(REPO)), "score": 0, "grade": "F", "pass": False, "error": str(e)})

    if not results:
        print("No lessons found.")
        sys.exit(0 if threshold is None else 1)

    # Output
    if json_mode or ci_mode:
        output = {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("pass")),
            "failed": sum(1 for r in results if not r.get("pass")),
            "avg_score": round(sum(r.get("score", 0) for r in results) / len(results), 1),
            "threshold": threshold,
            "lessons": results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Human-readable report
        avg = sum(r.get("score", 0) for r in results) / len(results)
        below = [r for r in results if threshold and r.get("score", 0) < threshold]

        print(f"Lesson Quality Report (100-point rubric)")
        print(f"{'=' * 70}")
        print(f"Total: {len(results)}  Passed: {sum(1 for r in results if r.get('pass'))}  "
              f"Failed: {sum(1 for r in results if not r.get('pass'))}  Avg: {avg:.1f}")
        if threshold:
            print(f"Threshold: {threshold}  Below: {len(below)}")
        print()

        # Table header
        print(f"{'Score':>5} {'Grade':>5} {'Meta':>4} {'Stru':>4} {'Cont':>4} {'Dedup':>5} {'Trust':>5}  File")
        print("-" * 80)
        for r in sorted(results, key=lambda x: x.get("score", 0)):
            b = r.get("breakdown", {})
            tag = " ⚠️" if threshold and r.get("score", 0) < threshold else ""
            print(
                f"{r.get('score', 0):>5} {r.get('grade', '?'):>5} "
                f"{b.get('metadata', {}).get('score', 0):>4} "
                f"{b.get('structure', {}).get('score', 0):>4} "
                f"{b.get('content', {}).get('score', 0):>4} "
                f"{b.get('dedup', {}).get('score', 0):>5} "
                f"{b.get('trust', {}).get('score', 0):>5}  "
                f"{r['file']}{tag}"
            )

        # Details for failing lessons
        if below:
            print(f"\n{'=' * 70}")
            print(f"Lessons below threshold ({threshold}):")
            print(f"{'=' * 70}")
            for r in below:
                print(f"\n  ❌ {r['file']} — {r.get('score', 0)}/100 (grade {r.get('grade', '?')})")
                b = r.get("breakdown", {})
                for dim, info in b.items():
                    if info.get("notes"):
                        for note in info["notes"]:
                            print(f"     [{dim}] {note}")

    # Exit code
    if threshold is not None:
        below_threshold = [r for r in results if r.get("score", 0) < threshold]
        if below_threshold:
            if not json_mode and not ci_mode:
                print(f"\n❌ {len(below_threshold)}/{len(results)} lessons below threshold {threshold}")
            sys.exit(1)
        else:
            if not json_mode and not ci_mode:
                print(f"\n✅ All {len(results)} lessons pass threshold {threshold}")
            sys.exit(0)


if __name__ == "__main__":
    main()
