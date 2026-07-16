"""MisakaNet 搜索引擎 — BM25 + 元数据加权 + 分层缓存。
BM25 核心算法委托给 misakanet-core 包。
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from misakanet_core import BM25, ScoredDocument

REPO = Path(__file__).resolve().parent.parent.parent
LESSONS = REPO / "lessons"
LESSONS_CORE = LESSONS / "core"
LESSONS_CONTRIB = LESSONS / "contrib"
REFERENCES = REPO / "reference"
INDEX = LESSONS / "index.md"

K1 = 1.5
B = 0.75
WEIGHT_DOMAIN_MATCH = 0.25
WEIGHT_STATUS = {"published": 0.0, "active": 0.1, "draft": 0.0}
WEIGHT_TITLE_EXACT = 0.8
WEIGHT_TITLE_PARTIAL = 0.4
WEIGHT_HAS_REF = 0.12
MAX_METADATA = 1.0

# Feature #228: boost core/verified/recent lessons, penalize drafts.
# Multipliers added to the final composite score (not the BM25 term),
# so they don't compete with the existing 0.65 / 0.20 / 0.15 weights.
BOOST_CORE = 0.15
BOOST_VERIFIED = 0.10
BOOST_RECENT = 0.05
BOOST_DRAFT = -0.20
BOOST_RECENT_DAYS = 30

# ── 分层缓存 ──
_CACHE_DIR = REPO / ".cache"
_CACHE_DB = _CACHE_DIR / "search_cache.db"
_L1_CACHE = {}
_L1_MAX = 50
_L2_CONN = None


def _l2():
    global _L2_CONN
    if _L2_CONN is None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _L2_CONN = sqlite3.connect(str(_CACHE_DB))
        _L2_CONN.execute("PRAGMA journal_mode=WAL")
        _L2_CONN.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                path TEXT PRIMARY KEY, mtime REAL, size INT,
                title TEXT, domain TEXT, status TEXT,
                reference TEXT, scope TEXT, source TEXT, tags TEXT, language TEXT
            )""")
        # Migration: add language column if upgrading from older schema
        try:
            _L2_CONN.execute("ALTER TABLE file_cache ADD COLUMN language TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        _L2_CONN.commit()
    return _L2_CONN


@dataclass
class CachedDoc:
    filename: str
    filepath: Path
    content: str
    title: str = ""
    domain: str = ""
    status: str = ""
    reference: str = ""
    scope: str = ""
    source: str = ""
    tags: list = field(default_factory=list)
    language: str = ""
    mtime: float = 0.0
    is_lesson: bool = True

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"

    @property
    def score_baseline(self) -> float:
        return 0.0 if self.is_draft else 0.1


def _parse_json_frontmatter(text: str) -> dict | None:
    m = re.match(r"^---\s*\n?(\{.*?\})\n?---", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _parse_yaml_frontmatter(text: str) -> dict:
    meta = {}
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith("[") and val.endswith("]"):
            try:
                meta[key] = json.loads(val.replace("'", '"'))
            except json.JSONDecodeError:
                meta[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
        else:
            meta[key] = val
    return meta


def _load_docs_cached(directory: Path, is_lesson: bool = True) -> list[CachedDoc]:
    """L2缓存加载 — 只重新解析有变动的文件。
    如果 is_lesson=True，同时扫描 core/ 和 contrib/ 子目录。"""
    docs = []
    conn = _l2()
    known = {
        row[0]: (row[1], row[2])
        for row in conn.execute("SELECT path, mtime, size FROM file_cache").fetchall()
    }
    changed = 0
    # For lessons, scan both core/ and contrib/; for references, scan single directory
    search_dirs = [directory]
    if is_lesson:
        search_dirs = [LESSONS_CORE, LESSONS_CONTRIB]
    for dir_path in search_dirs:
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("**/*.md")):
            if f.name == "index.md" or f.name.startswith("."):
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            rel = str(f.relative_to(REPO))
            cached = known.get(rel)
            if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
                row = conn.execute(
                    "SELECT title,domain,status,reference,scope,source,tags,language "
                    "FROM file_cache WHERE path=?",
                    (rel,),
                ).fetchone()
                if row:
                    tags = json.loads(row[6]) if row[6] else []
                    doc = CachedDoc(
                        filename=f.name,
                        filepath=f,
                        content="",
                        mtime=st.st_mtime,
                        is_lesson=is_lesson,
                        title=row[0] or f.stem,
                        domain=row[1] or "",
                        status=row[2] or "",
                        reference=row[3] or "",
                        scope=row[4] or "",
                        source=row[5] or "",
                        tags=tags,
                        language=row[7] or "",
                    )
                    doc.content = f.read_text(encoding="utf-8", errors="replace")
                    docs.append(doc)
                    continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            if not content.strip():
                continue
            doc = CachedDoc(
                filename=f.name, filepath=f, content=content, mtime=st.st_mtime, is_lesson=is_lesson
            )
            meta = _parse_json_frontmatter(content) or _parse_yaml_frontmatter(content)
            doc.title = meta.get("title", f.stem)
            doc.domain = meta.get("domain", "")
            if isinstance(doc.domain, list):
                doc.domain = doc.domain[0] if doc.domain else ""
            doc.status = meta.get("status", "")
            doc.reference = meta.get("reference", "")
            doc.scope = meta.get("scope", "")
            doc.source = meta.get("source", "")
            doc.language = meta.get("language", "")
            raw_tags = meta.get("tags", "")
            doc.tags = raw_tags if isinstance(raw_tags, list) else []
            docs.append(doc)
            conn.execute(
                "INSERT OR REPLACE INTO file_cache "
                "(path,mtime,size,title,domain,status,reference,scope,source,tags,language) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rel,
                    st.st_mtime,
                    st.st_size,
                    doc.title,
                    doc.domain,
                    doc.status,
                    doc.reference,
                    doc.scope,
                    doc.source,
                    json.dumps(doc.tags, ensure_ascii=False),
                    doc.language,
                ),
            )
            changed += 1
    conn.commit()
    if changed:
        print(f"  📦 L2缓存: {changed} 篇变动")
    return docs


def _doc_cache_id(doc: CachedDoc) -> str:
    return str(doc.filepath.relative_to(REPO))


def _search_cached(
    query: str, docs: list[CachedDoc], titles_only: bool = False, broad_only: bool = False
) -> list[tuple[float, CachedDoc]]:
    """L1缓存 — 相同 query 直接返回上次结果。"""
    key = f"{query}_{titles_only}_{broad_only}"
    if key in _L1_CACHE:
        doc_map = {_doc_cache_id(d): d for d in docs}
        result = [(s, doc_map[fid]) for s, fid in _L1_CACHE[key] if fid in doc_map]
        if len(result) == len(_L1_CACHE[key]):
            return result
    result = _rank_docs_impl(query, docs, titles_only, broad_only)
    _L1_CACHE[key] = [(s, _doc_cache_id(d)) for s, d in result[:20]]
    if len(_L1_CACHE) > _L1_MAX:
        del _L1_CACHE[next(iter(_L1_CACHE))]
    return result


# Extended Latin character range: includes accented chars (é, ü, ñ, etc.)
_LATIN_EXT = "a-zA-Z\u00c0-\u024f"
_TOKEN_RE = re.compile(f"[{_LATIN_EXT}0-9_]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lower-case tokens with extended character support.

    Handles:
    - Accented Latin characters (é, ü, ñ, ï, etc.) — preserved, not dropped
    - Internal underscores kept (test_123 stays as one token)
    - Leading/trailing underscores stripped (_italic_ → italic)
    - CJK characters split individually for BM25 recall
    """
    text = text.lower()
    # Split CJK into individual chars surrounded by spaces
    text = re.sub(r"([\u4e00-\u9fff])", r" \1 ", text)
    tokens = _TOKEN_RE.findall(text)
    result = []
    for t in tokens:
        t = t.strip("_")  # strip markdown-style wrapping underscores
        if len(t) >= 1:
            result.append(t)
    return result


def _compute_bm25_scores(query: str, docs: list[CachedDoc]) -> list[float]:
    """BM25 scoring delegated to misakanet-core."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return [0.0] * len(docs)

    # Build ScoredDocument list for core engine
    scored_docs = [ScoredDocument(d.filename, _tokenize(d.content)) for d in docs]

    engine = BM25(scored_docs)
    results = engine.search(query, top_k=len(docs))

    # Map results back to original order
    result_scores = {r.doc_id: r.score for r in results}
    return [result_scores.get(d.filename, 0.0) for d in docs]


def _metadata_bonus(query: str, doc: CachedDoc) -> float:
    bonus = 0.0
    q = query.lower()
    t = doc.title.lower()
    if doc.domain and doc.domain.lower() in q:
        bonus += WEIGHT_DOMAIN_MATCH
    if t == q:
        bonus += WEIGHT_TITLE_EXACT
    elif q in t or any(word in t for word in q.split()):
        bonus += WEIGHT_TITLE_PARTIAL
    bonus += WEIGHT_STATUS.get(doc.status, 0.0)
    if doc.reference:
        bonus += WEIGHT_HAS_REF
    if doc.source and doc.source != "bootstrap":
        bonus += 0.05
    return min(bonus, MAX_METADATA)


def _metadata_bonus_breakdown(query: str, doc: CachedDoc) -> list[tuple[str, float]]:
    """Return per-field metadata bonus breakdown for --explain mode."""
    parts = []
    q = query.lower()
    t = doc.title.lower()
    if doc.domain and doc.domain.lower() in q:
        parts.append(("domain_match", WEIGHT_DOMAIN_MATCH))
    if t == q:
        parts.append(("title_exact", WEIGHT_TITLE_EXACT))
    elif q in t or any(word in t for word in q.split()):
        parts.append(("title_partial", WEIGHT_TITLE_PARTIAL))
    status_w = WEIGHT_STATUS.get(doc.status, 0.0)
    if status_w:
        parts.append((f"status({doc.status})", status_w))
    if doc.reference:
        parts.append(("has_reference", WEIGHT_HAS_REF))
    if doc.source and doc.source != "bootstrap":
        parts.append(("source", 0.05))
    return parts


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return values
    mn, mx = min(values), max(values)
    if mx - mn < 1e-10:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def _compute_boost(doc: CachedDoc) -> float:
    """Feature #228: per-doc boost factor summed into the final score.

    Sum of the applicable multipliers. Kept additive (not multiplicative)
    so the constants stay easy to reason about and tune.
    """
    boost = 0.0
    if _is_core(doc):
        boost += BOOST_CORE
    if _is_verified(doc):
        boost += BOOST_VERIFIED
    if _is_recent(doc):
        boost += BOOST_RECENT
    if doc.is_draft:
        boost += BOOST_DRAFT
    return boost


def _compute_boost_breakdown(doc: CachedDoc) -> list[tuple[str, float]]:
    """Return per-factor boost breakdown for --explain mode."""
    parts = []
    if _is_core(doc):
        parts.append(("core", BOOST_CORE))
    if _is_verified(doc):
        parts.append(("verified", BOOST_VERIFIED))
    if _is_recent(doc):
        parts.append(("recent", BOOST_RECENT))
    if doc.is_draft:
        parts.append(("draft", BOOST_DRAFT))
    return parts


def _rank_docs_impl(
    query: str, docs: list[CachedDoc], titles_only: bool = False, broad_only: bool = False
) -> list[tuple[float, CachedDoc]]:
    if not docs:
        return []
    if broad_only:
        docs = [d for d in docs if d.scope == "broad"]
    if not titles_only:
        visible = [d for d in docs if not d.is_draft]
        if visible:
            docs = visible
    bm25_raw = _compute_bm25_scores(query, docs)
    bm25_norm = _normalize(bm25_raw)
    scored = [
        (
            0.65 * bm25_norm[i]
            + 0.20 * _metadata_bonus(query, d)
            + 0.15 * d.score_baseline
            + _compute_boost(d),
            d,
        )
        for i, d in enumerate(docs)
    ]
    scored.sort(key=lambda x: -x[0])
    return scored


def _matching_terms(text: str, query: str) -> list[str]:
    text_l = text.lower()
    matches = []
    for token in _tokenize(query):
        token_l = token.lower()
        if token_l and token_l in text_l and token_l not in matches:
            matches.append(token_l)
    return matches


def _highlight(text: str, query: str) -> str:
    tokens = _tokenize(query)
    if not tokens:
        return text
    for t in sorted(set(tokens), key=len, reverse=True):
        if len(t) < 1:
            continue
        text = re.sub(
            re.escape(t), lambda m: f"\033[33m{m.group()}\033[0m", text, flags=re.IGNORECASE
        )
    return text


def _highlight_plain(text: str, query: str) -> str:
    """Highlight matching terms without ANSI escapes for JSON consumers."""
    highlighted = text
    for token in sorted(set(_tokenize(query)), key=len, reverse=True):
        highlighted = re.sub(
            re.escape(token),
            lambda m: f"[{m.group()}]",
            highlighted,
            flags=re.IGNORECASE,
        )
    return highlighted


def _score_bar(score: float, width: int = 10) -> str:
    pct = max(0.0, min(score, 1.0))
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled) + f" {pct:.0%}"


def _get_match_reason(query: str, doc: CachedDoc, score: float | None = None) -> str:
    """Show why this result was matched, including field names and terms."""
    reasons = []

    for term in _matching_terms(doc.title, query):
        reasons.append(f"title keyword '{term}'")

    for term in _matching_terms(doc.domain, query):
        if term == doc.domain.lower():
            reasons.append(f"domain '{doc.domain}'")
        else:
            reasons.append(f"domain keyword '{term}'")

    for tag in doc.tags:
        tag_text = str(tag)
        for term in _matching_terms(tag_text, query):
            if term == tag_text.lower():
                reasons.append(f"tag '{tag_text}'")
            else:
                reasons.append(f"tag keyword '{term}'")

    for term in _matching_terms(doc.content, query):
        if not any(f"'{term}'" in reason for reason in reasons):
            reasons.append(f"content keyword '{term}'")

    if doc.scope == "broad":
        reasons.append("broad")

    if not reasons and score is not None and score > 0:
        reasons.append("BM25 content score")

    return " + ".join(dict.fromkeys(reasons))


# ── Heuristic confidence / result_type classification ──

# Patterns that indicate actionable lessons (have concrete fix steps)
_ACTIONABLE_SIGNALS = re.compile(
    r"(fix|solution|workaround|step\s*\d|verify|verification|"
    r"error.code|exit.code|return.code|"
    r"```|pip install|git |curl |chmod |mkdir |export )",
    re.IGNORECASE,
)

# Patterns that indicate common/reference content (generic, not specific)
_COMMON_PATTERNS = re.compile(
    r"(github.com.*443|connectivity|checklist|basic|intro|overview|"
    r"getting.started|quick.start|faq|troubleshooting.general|"
    r"network.*basics|git.*basics|config.*general|auth.*basics)",
    re.IGNORECASE,
)

# Error code pattern (specific technical signal)
_ERROR_CODE_PATTERN = re.compile(
    r"(GH\d{3,4}|E\d{3,5}|W\d{3,5}|SEC\d+|INTP-\d+|KL-\d+|"
    r"exit\s+(?:code|status)\s+\d+|HTTP\s+\d{3}|error\s+code\s+\d+)",
    re.IGNORECASE,
)


def _classify_confidence(
    doc: CachedDoc, query: str, match_reasons: str, score: float
) -> str:
    """Classify result confidence: high | medium | low.

    Heuristic rules (no schema migration required):
    - high: error codes in title/content, clear fix steps, verification section,
            high match score, title match
    - low: common patterns, generic titles, low score, only content keyword match
    - medium: everything else
    """
    title_lower = doc.title.lower()
    content_lower = doc.content[:2000].lower()
    reasons_lower = match_reasons.lower()

    # High confidence signals
    has_error_code = bool(_ERROR_CODE_PATTERN.search(doc.title + " " + doc.content[:500]))
    has_actionable = bool(_ACTIONABLE_SIGNALS.search(content_lower))
    has_verification = "## verification" in content_lower or "## verify" in content_lower
    has_title_match = "title keyword" in reasons_lower or "title exact" in reasons_lower
    high_score = score >= 0.6

    if has_error_code and has_title_match:
        return "high"
    if has_verification and has_actionable and high_score:
        return "high"
    if has_title_match and high_score and has_actionable:
        return "high"

    # Low confidence signals
    is_common = bool(_COMMON_PATTERNS.search(title_lower + " " + content_lower[:500]))
    only_content_match = "content keyword" in reasons_lower and "title" not in reasons_lower and "tag" not in reasons_lower
    low_score = score < 0.35
    generic_title = len(title_lower.split()) <= 3 and not has_error_code

    if is_common and low_score:
        return "low"
    if only_content_match and low_score:
        return "low"
    if generic_title and low_score and not has_actionable:
        return "low"

    return "medium"


def _classify_result_type(doc: CachedDoc, confidence: str) -> str:
    """Classify result type: actionable | common | related.

    - actionable: high/medium confidence with fix steps or verification
    - common: low confidence or generic reference content
    - related: medium confidence but no clear fix steps (background/context)
    """
    if confidence == "low":
        return "common"

    content_lower = doc.content[:2000].lower()
    has_actionable = bool(_ACTIONABLE_SIGNALS.search(content_lower))

    if confidence == "high":
        return "actionable"
    if confidence == "medium" and has_actionable:
        return "actionable"
    if confidence == "medium":
        return "related"

    return "common"


def _get_signal_level(doc: CachedDoc, confidence: str) -> str:
    """Classify signal level: canonical | common.

    - canonical: specific error codes, clear fix steps, verification, multi-case reuse
    - common: generic content, basic guides, background knowledge
    """
    if confidence == "low":
        return "common"

    content_lower = doc.content[:2000].lower()
    has_error_code = bool(_ERROR_CODE_PATTERN.search(doc.title + " " + doc.content[:500]))
    has_verification = "## verification" in content_lower or "## verify" in content_lower
    has_actionable = bool(_ACTIONABLE_SIGNALS.search(content_lower))

    if has_error_code or (has_verification and has_actionable):
        return "canonical"
    if confidence == "high":
        return "canonical"

    return "common"


def _get_search_boost(signal_level: str, confidence: str) -> float:
    """Get search boost multiplier based on signal level and confidence.

    Canonical results get boosted, common results get suppressed.
    """
    if signal_level == "canonical":
        return 0.6
    if signal_level == "common":
        return -0.4
    return 0.0


def _get_why_matched(match_reasons: str) -> dict:
    """Parse match reasons into structured explanation.

    Returns dict with matched_terms, match_fields, and summary.
    """
    if not match_reasons:
        return {"matched_terms": [], "match_fields": [], "summary": "no match"}

    parts = [r.strip() for r in match_reasons.split("+")]
    matched_terms = []
    match_fields = []

    for part in parts:
        # Extract quoted terms
        quoted = re.findall(r"'([^']+)'", part)
        matched_terms.extend(quoted)

        # Extract field names
        if part.startswith("title"):
            match_fields.append("title")
        elif part.startswith("domain"):
            match_fields.append("domain")
        elif part.startswith("tag"):
            match_fields.append("tags")
        elif part.startswith("content"):
            match_fields.append("content")
        elif part == "broad":
            match_fields.append("broad")

    return {
        "matched_terms": list(dict.fromkeys(matched_terms)),
        "match_fields": list(dict.fromkeys(match_fields)),
        "summary": match_reasons,
    }


def _score_breakdown(query: str, doc: CachedDoc) -> dict:
    bm25 = _compute_bm25_scores(query, [doc])[0]
    meta_parts = _metadata_bonus_breakdown(query, doc)
    boost_parts = _compute_boost_breakdown(doc)
    return {
        "bm25": round(float(bm25), 6),
        "metadata": {key: round(float(value), 6) for key, value in meta_parts},
        "baseline": round(float(doc.score_baseline), 6),
        "boost": {key: round(float(value), 6) for key, value in boost_parts},
    }


def _get_related_lessons(
    doc: CachedDoc, all_docs: list[CachedDoc], max_related: int = 3
) -> list[tuple[str, str]]:
    """Find related lessons by shared tags. Returns [(title, filename), ...]."""
    if not doc.tags or not all_docs:
        return []
    doc_tags = set(t.lower() for t in doc.tags)
    scored = []
    for other in all_docs:
        if other.filename == doc.filename:
            continue
        if not other.tags:
            continue
        other_tags = set(t.lower() for t in other.tags)
        overlap = doc_tags & other_tags
        if len(overlap) >= 1:
            # Score by number of shared tags
            scored.append((len(overlap), other.title, other.filename))
    scored.sort(key=lambda x: -x[0])
    return [(t, f) for _, t, f in scored[:max_related]]


def _format_output(
    scored: list[tuple[float, CachedDoc]],
    titles_only: bool = False,
    top_k: int = 10,
    mode_label: str = "",
    query: str = "",
    explain: bool = False,
    all_docs: list[CachedDoc] | None = None,
) -> bool:
    if not scored:
        return False
    n = len(scored)
    shown = min(top_k, n)
    print(f"\\n📋 {mode_label} ({n} matches, showing top {shown})")
    print("-" * 60)
    for score, doc in scored[:top_k]:
        # Feature #227: Credibility badges
        core_tag = "[core]" if _is_core(doc) else "[contrib]"
        verified_tag = "[verified]" if _is_verified(doc) else ""
        domain_tag = f"[{doc.domain}]" if doc.domain else ""
        status_tag = f"({doc.status})" if doc.status else ""
        ref_tag = f"→ {doc.reference}" if doc.reference else ""

        # Feature #231: Match reason
        match_reason = _get_match_reason(query, doc, score)

        # Confidence / result type / signal level
        confidence = _classify_confidence(doc, query, match_reason, score)
        result_type = _classify_result_type(doc, confidence)
        signal_level = _get_signal_level(doc, confidence)
        conf_icon = {"high": "🟢", "medium": "🟡", "low": "⚫"}.get(confidence, "⚪")

        # Build badge line
        badges = f"{core_tag} {verified_tag} {domain_tag}".strip()
        time_str = _relative_time(doc.mtime)

        print(f"  {badges:<25} {doc.title} {status_tag}")
        print(f"  {'':>25} {_score_bar(score):>15}  {time_str}  {conf_icon} {confidence}/{result_type}")
        if match_reason:
            print(f"  {'':>25} (matched: {match_reason})")
        # Feature: --explain score breakdown (#303)
        if explain and query:
            bm25 = _compute_bm25_scores(query, [doc])[0]
            meta_parts = _metadata_bonus_breakdown(query, doc)
            meta_total = sum(v for _, v in meta_parts)
            baseline = doc.score_baseline
            boost_parts = _compute_boost_breakdown(doc)
            boost_total = sum(v for _, v in boost_parts)
            tag_str = ", ".join(doc.tags[:5]) if doc.tags else "—"

            print(f"  {'':>25} ↳ BM25: {bm25:.3f}")
            if meta_parts:
                meta_detail = ", ".join(f"{k}(+{v:.2f})" for k, v in meta_parts)
                print(f"  {'':>25}   Meta: {meta_total:.3f} = {meta_detail}")
            else:
                print(f"  {'':>25}   Meta: 0.000")
            print(f"  {'':>25}   Base: {baseline:.3f}")
            if boost_parts:
                boost_detail = ", ".join(f"{k}({v:+.2f})" for k, v in boost_parts)
                print(f"  {'':>25}   Boost: {boost_total:+.2f} = {boost_detail}")
            else:
                print(f"  {'':>25}   Boost: +0.00")
            print(f"  {'':>25}   Tags: {tag_str}")
        # Feature: related lessons (cross-lesson reference graph)
        if all_docs is not None:
            related = _get_related_lessons(doc, all_docs, max_related=3)
            if related:
                rel_line = ", ".join(f"📄 {f}" for _, f in related)
                print(f"  {'':>25} 🔗 Related: {rel_line}")
        if titles_only:
            continue
        rel_dir = "lessons" if doc.is_lesson else "reference"
        print(f"  {'':>25} 📄 {rel_dir}/{doc.filename}")
        preview = _get_preview(doc.content, max_chars=120)
        if preview:
            print(f"  {'':>25} {_highlight(preview, query)}")
        if ref_tag:
            print(f"  {'':>25} ref: {ref_tag}")
        print()
    return True


def _get_preview(content: str, max_chars: int = 100) -> str:
    if not content:
        return ""
    lines = content.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break
    for line in lines[start:]:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("- **"):
            if len(line) > max_chars:
                return line[:max_chars] + "..."
            return line
    return ""


def _show_timing(elapsed: float, num_docs: int):
    if elapsed > 0.1:
        print(f"  ⏱ 检索 {num_docs} 篇文档耗时 {elapsed:.2f}s")


# 导出：用缓存版本替换原始加载/排序函数
_load_docs = _load_docs_cached
_rank_docs = _search_cached
# 保留原名供 L1 缓存内部调用（不导出）
_rank_docs_impl_export = _rank_docs_impl

__all__ = [
    "CachedDoc",
    "LESSONS",
    "REFERENCES",
    "_load_docs",
    "_rank_docs",
    "_format_output",
    "_show_timing",
    "_tokenize",
    "_compute_bm25_scores",
    "_normalize",
    "_is_verified",
    "_is_core",
    "_is_recent",
    "_compute_boost",
    "_relative_time",
    "_get_match_reason",
    "_highlight_plain",
    "_score_breakdown",
    "_get_related_lessons",
]


def _is_verified(doc: CachedDoc) -> bool:
    """Check if lesson has Verify/Verification section."""
    if not doc.content:
        return False
    return bool(re.search(r"##\s*(Verify|Verification)", doc.content, re.IGNORECASE))


def _is_core(doc: CachedDoc) -> bool:
    """Check if lesson is in core/ directory."""
    parts = [part.lower() for part in doc.filepath.parts]
    return any(parts[i] == "lessons" and parts[i + 1] == "core" for i in range(len(parts) - 1))


def _is_recent(doc: CachedDoc) -> bool:
    """Feature #228: True if lesson was updated within BOOST_RECENT_DAYS days."""
    if not doc.mtime:
        return False
    import datetime

    age_days = (datetime.datetime.now().timestamp() - doc.mtime) / 86400
    return age_days <= BOOST_RECENT_DAYS


def _relative_time(mtime: float) -> str:
    """Show relative update time."""
    if not mtime:
        return ""
    import datetime

    now = datetime.datetime.now().timestamp()
    diff = now - mtime
    if diff < 60:
        return "just now"
    elif diff < 3600:
        return f"{int(diff/60)}m ago"
    elif diff < 86400:
        return f"{int(diff/3600)}h ago"
    elif diff < 2592000:
        return f"{int(diff/86400)}d ago"
    else:
        return f"{int(diff/2592000)}mo ago"
