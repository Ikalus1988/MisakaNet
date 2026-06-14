"""MisakaNet 搜索引擎 — BM25 + 元数据加权 + 分层缓存。
BM25 核心算法委托给 misakanet-core 包。
"""
import sys
import json
import re
import time
import sqlite3
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from misakanet_core import BM25 as CoreBM25, ScoredDocument, tokenize as core_tokenize

REPO = Path(__file__).resolve().parent.parent.parent
LESSONS = REPO / "lessons"
LESSONS_CORE = LESSONS / "core"
LESSONS_CONTRIB = LESSONS / "contrib"
REFERENCES = REPO / "reference"
INDEX = LESSONS / "index.md"

K1 = 1.5
B = 0.75
WEIGHT_DOMAIN_MATCH = 0.3
WEIGHT_STATUS = {"published": 0.2, "active": 0.1, "draft": 0.0}
WEIGHT_TITLE_EXACT = 0.5
WEIGHT_TITLE_PARTIAL = 0.2
WEIGHT_HAS_REF = 0.08
MAX_METADATA = 1.0

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
                reference TEXT, scope TEXT, source TEXT, tags TEXT
            )""")
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
    mtime: float = 0.0
    is_lesson: bool = True

    @property
    def is_draft(self) -> bool:
        return self.status == "draft"

    @property
    def score_baseline(self) -> float:
        return 0.0 if self.is_draft else 0.1


def _parse_json_frontmatter(text: str) -> Optional[dict]:
    m = re.match(r'^---\s*\n?(\{.*?\})\n?---', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _parse_yaml_frontmatter(text: str) -> dict:
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split('\n'):
        line = line.strip()
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith('[') and val.endswith(']'):
            try:
                meta[key] = json.loads(val.replace("'", '"'))
            except json.JSONDecodeError:
                meta[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',')]
        else:
            meta[key] = val
    return meta


def _load_docs_cached(directory: Path, is_lesson: bool = True) -> list[CachedDoc]:
    """L2缓存加载 — 只重新解析有变动的文件。
    如果 is_lesson=True，同时扫描 core/ 和 contrib/ 子目录。"""
    docs = []
    conn = _l2()
    known = {row[0]: (row[1], row[2]) for row in conn.execute(
        "SELECT path, mtime, size FROM file_cache").fetchall()}
    changed = 0
    # For lessons, scan both core/ and contrib/; for references, scan single directory
    search_dirs = [directory]
    if is_lesson:
        search_dirs = [LESSONS_CORE, LESSONS_CONTRIB]
    for dir_path in search_dirs:
        if not dir_path.exists():
            continue
        for f in sorted(dir_path.glob("**/*.md")):
            if f.name == "index.md" or f.name.startswith('.'):
                continue
            try:
                st = f.stat()
            except OSError:
                continue
            rel = str(f.relative_to(REPO))
            cached = known.get(rel)
            if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
                row = conn.execute(
                    "SELECT title,domain,status,reference,scope,source,tags FROM file_cache WHERE path=?",
                    (rel,)).fetchone()
                if row:
                    tags = json.loads(row[6]) if row[6] else []
                    doc = CachedDoc(filename=f.name, filepath=f, content="", mtime=st.st_mtime,
                                    is_lesson=is_lesson, title=row[0] or f.stem, domain=row[1] or "",
                                    status=row[2] or "", reference=row[3] or "",
                                    scope=row[4] or "", source=row[5] or "", tags=tags)
                    doc.content = f.read_text(encoding="utf-8", errors="replace")
                    docs.append(doc)
                    continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            if not content.strip():
                continue
            doc = CachedDoc(filename=f.name, filepath=f, content=content,
                            mtime=st.st_mtime, is_lesson=is_lesson)
            meta = _parse_json_frontmatter(content) or _parse_yaml_frontmatter(content)
            doc.title = meta.get("title", f.stem)
            doc.domain = meta.get("domain", "")
            if isinstance(doc.domain, list):
                doc.domain = doc.domain[0] if doc.domain else ""
            doc.status = meta.get("status", "")
            doc.reference = meta.get("reference", "")
            doc.scope = meta.get("scope", "")
            doc.source = meta.get("source", "")
            raw_tags = meta.get("tags", "")
            doc.tags = raw_tags if isinstance(raw_tags, list) else []
            docs.append(doc)
            conn.execute("INSERT OR REPLACE INTO file_cache (path,mtime,size,title,domain,status,reference,scope,source,tags) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (rel, st.st_mtime, st.st_size, doc.title, doc.domain, doc.status,
                          doc.reference, doc.scope, doc.source, json.dumps(doc.tags, ensure_ascii=False)))
            changed += 1
    conn.commit()
    if changed:
        print(f"  📦 L2缓存: {changed} 篇变动")
    return docs


def _doc_cache_id(doc: CachedDoc) -> str:
    return str(doc.filepath.relative_to(REPO))



def _search_cached(query: str, docs: list[CachedDoc],
                   titles_only: bool = False,
                   broad_only: bool = False) -> list[tuple[float, CachedDoc]]:
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


def _tokenize(text: str) -> list[str]:
    """Tokenize using misakanet-core engine."""
    return core_tokenize(text)


def _compute_bm25_scores(query: str, docs: list[CachedDoc]) -> list[float]:
    """BM25 scoring delegated to misakanet-core."""
    query_tokens = core_tokenize(query)
    if not query_tokens:
        return [0.0] * len(docs)

    # Build ScoredDocument list for core engine
    scored_docs = [
        ScoredDocument(d.filename, core_tokenize(d.content))
        for d in docs
    ]

    engine = CoreBM25(scored_docs)
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


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return values
    mn, mx = min(values), max(values)
    if mx - mn < 1e-10:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def _rank_docs_impl(query: str, docs: list[CachedDoc],
                    titles_only: bool = False,
                    broad_only: bool = False) -> list[tuple[float, CachedDoc]]:
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
    scored = [(0.65 * bm25_norm[i] + 0.20 * _metadata_bonus(query, d) + 0.15 * d.score_baseline, d)
              for i, d in enumerate(docs)]
    scored.sort(key=lambda x: -x[0])
    return scored


def _highlight(text: str, query: str) -> str:
    tokens = _tokenize(query)
    if not tokens:
        return text
    for t in sorted(set(tokens), key=len, reverse=True):
        if len(t) < 1:
            continue
        text = re.sub(re.escape(t), lambda m: f"\033[33m{m.group()}\033[0m", text, flags=re.IGNORECASE)
    return text


def _score_bar(score: float, width: int = 10) -> str:
    pct = max(0.0, min(score, 1.0))
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled) + f" {pct:.0%}"




def _get_match_reason(query: str, doc: CachedDoc, score: float) -> str:
    """Feature #231: Show why this result was matched."""
    q = query.lower()
    t = doc.title.lower()
    reasons = []
    
    # Check title match
    if q in t or any(word in t for word in q.split()):
        reasons.append("title")
    
    # Check domain match
    if doc.domain and doc.domain.lower() in q:
        reasons.append("domain")
    
    # Check content match (BM25 score > 0.3 indicates content match)
    if score > 0.3 and "title" not in reasons:
        reasons.append("content")
    
    # Check if broad match
    if doc.scope == "broad":
        reasons.append("broad")
    
    return ", ".join(reasons) if reasons else ""

def _format_output(scored: list[tuple[float, CachedDoc]],
                   titles_only: bool = False,
                   top_k: int = 10,
                   mode_label: str = "",
                   query: str = "") -> bool:
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
        
        # Build badge line
        badges = f"{core_tag} {verified_tag} {domain_tag}".strip()
        time_str = _relative_time(doc.mtime)
        
        print(f"  {badges:<25} {doc.title} {status_tag}")
        print(f"  {'':>25} {_score_bar(score):>15}  {time_str}")
        if match_reason:
            print(f"  {'':>25} (matched: {match_reason})")
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
        return ''
    lines = content.split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    for line in lines[start:]:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('- **'):
            if len(line) > max_chars:
                return line[:max_chars] + '...'
            return line
    return ''


def _show_timing(elapsed: float, num_docs: int):
    if elapsed > 0.1:
        print(f"  ⏱ 检索 {num_docs} 篇文档耗时 {elapsed:.2f}s")


# 导出：用缓存版本替换原始加载/排序函数
_load_docs = _load_docs_cached
_rank_docs = _search_cached
# 保留原名供 L1 缓存内部调用（不导出）
_rank_docs_impl_export = _rank_docs_impl

__all__ = [
    "CachedDoc", "LESSONS", "REFERENCES",
    "_load_docs", "_rank_docs", "_format_output", "_show_timing",
    "_tokenize", "_compute_bm25_scores", "_normalize",
    "_is_verified", "_is_core", "_relative_time", "_get_match_reason",
]


def _is_verified(doc: CachedDoc) -> bool:
    """Check if lesson has Verify/Verification section."""
    if not doc.content:
        return False
    return bool(re.search(r'##\s*(Verify|Verification)', doc.content, re.IGNORECASE))


def _is_core(doc: CachedDoc) -> bool:
    """Check if lesson is in core/ directory."""
    return 'lessons/core/' in str(doc.filepath)


def _relative_time(mtime: float) -> str:
    """Show relative update time."""
    if not mtime:
        return ''
    import datetime
    now = datetime.datetime.now().timestamp()
    diff = now - mtime
    if diff < 60:
        return 'just now'
    elif diff < 3600:
        return f'{int(diff/60)}m ago'
    elif diff < 86400:
        return f'{int(diff/3600)}h ago'
    elif diff < 2592000:
        return f'{int(diff/86400)}d ago'
    else:
        return f'{int(diff/2592000)}mo ago'
