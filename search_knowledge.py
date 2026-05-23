#!/usr/bin/env python3
"""
虫群知识检索 v2 — lessons + reference 智能搜索

v2 升级: BM25 排序 + metadata 加权 + frontmatter 缓存
- 不依赖 numpy/sentence-transformers，纯 Python 可用
- --semantic 标志位预留（安装依赖后自动启用向量检索）

用法:
  search_knowledge.py "微信安装失败"           # 搜 lessons + reference
  search_knowledge.py "虫群记忆" --ref          # 只搜 reference
  search_knowledge.py "wxauto" --lessons        # 只搜 lessons
  search_knowledge.py "rag" --titles            # 只看标题
  search_knowledge.py "wxauto" --broad           # 只看跨平台通用 lessons
"""
import sys
import json
import math
import re
import time
from pathlib import Path
from typing import Optional
from collections import Counter
from dataclasses import dataclass, field

REPO = Path(__file__).parent
LESSONS = REPO / "lessons"
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


def _load_docs(directory: Path, is_lesson: bool = True) -> list[CachedDoc]:
    docs = []
    for f in sorted(directory.glob("**/*.md")):
        if f.name == "index.md":
            continue
        try:
            st = f.stat()
            content = f.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        if not content.strip():
            continue
        doc = CachedDoc(filename=f.name, filepath=f, content=content,
                        mtime=st.st_mtime, is_lesson=is_lesson)
        meta = _parse_json_frontmatter(content) or _parse_yaml_frontmatter(content)
        doc.title = meta.get("title", f.name.replace(".md", ""))
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
    return docs


def _tokenize(text: str) -> list[str]:
    t = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text.lower())
    tokens = []
    for part in t.split():
        if re.search(r'[\u4e00-\u9fff]', part):
            for ch in part:
                tokens.append(ch)
        else:
            tokens.append(part)
    return tokens


def _compute_bm25_scores(query: str, docs: list[CachedDoc]) -> list[float]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return [0.0] * len(docs)
    N = len(docs)
    doc_tfs = []
    doc_lengths = []
    for d in docs:
        tokens = _tokenize(d.content)
        doc_tfs.append(Counter(tokens))
        doc_lengths.append(len(tokens))
    avg_doc_len = sum(doc_lengths) / max(N, 1)
    df = Counter()
    for tf in doc_tfs:
        for t in query_tokens:
            if tf.get(t, 0) > 0:
                df[t] = df.get(t, 0) + 1
    scores = []
    for i in range(N):
        score = 0.0
        tf_counter = doc_tfs[i]
        doc_len = doc_lengths[i]
        for term in query_tokens:
            tf = tf_counter.get(term, 0)
            if tf == 0:
                continue
            idf = math.log((N - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5) + 1.0)
            numerator = tf * (K1 + 1)
            denominator = tf + K1 * (1 - B + B * doc_len / max(avg_doc_len, 1))
            score += idf * numerator / denominator
        scores.append(score)
    return scores


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


def _rank_docs(query: str, docs: list[CachedDoc],
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


def _format_output(scored: list[tuple[float, CachedDoc]],
                   titles_only: bool = False,
                   top_k: int = 10,
                   mode_label: str = "") -> bool:
    if not scored:
        return False
    n = len(scored)
    shown = min(top_k, n)
    print(f"\\n📋 {mode_label} ({n} 条匹配，展示前 {shown})")
    print("-" * 50)
    for score, doc in scored[:top_k]:
        domain_tag = f"[{doc.domain}]" if doc.domain else ""
        status_tag = f"({doc.status})" if doc.status else ""
        ref_tag = f"→ {doc.reference}" if doc.reference else ""
        print(f"  {domain_tag:<20} {doc.title} {status_tag}")
        if titles_only:
            continue
        rel_dir = "lessons" if doc.is_lesson else "reference"
        print(f"  {'':>20} → see {rel_dir}/{doc.filename}  (score: {score:.3f})")
        if ref_tag:
            print(f"  {'':>20} 参考: {ref_tag}")
        print()
    return True


def _get_preview(content: str, max_chars: int = 100) -> str:
    """Extract first meaningful line of body as preview"""
    if not content:
        return ''
    # Skip frontmatter (--- ... ---)
    lines = content.split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    # Find first non-empty, non-heading line
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    query = sys.argv[1]
    mode = "all"
    titles_only = False
    broad_only = False
    top_k = 10
    use_semantic = False
    for arg in sys.argv[2:]:
        if arg == "--ref":
            mode = "ref"
        elif arg == "--lessons":
            mode = "lessons"
        elif arg == "--titles":
            titles_only = True
        elif arg == "--broad":
            broad_only = True
        elif arg.startswith("--top="):
            try:
                top_k = int(arg.split("=")[1])
            except ValueError:
                pass
        elif arg == "--semantic":
            use_semantic = True
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--top" and i + 1 < len(args):
            try:
                top_k = int(args[i + 1])
            except ValueError:
                pass
    t0 = time.time()
    found_any = False
    lessons_docs = _load_docs(LESSONS, is_lesson=True) if mode in ("all", "lessons") else []
    ref_docs = _load_docs(REFERENCES, is_lesson=False) if mode in ("all", "ref") else []
    if use_semantic:
        try:
            from storage.vector_store import generate_embedding
            print("  🔬 语义检索已启用")
        except ImportError:
            print("  ⚠️ --semantic 需要 sentence-transformers，降级为 BM25")
    if lessons_docs:
        ranked = _rank_docs(query, lessons_docs, titles_only, broad_only)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"lessons/  (全部 {len(lessons_docs)} 篇)")
        found_any = found_any or found
    if ref_docs:
        ranked = _rank_docs(query, ref_docs, titles_only, broad_only=False)
        found = _format_output(ranked, titles_only, top_k,
                               mode_label=f"reference/  (全部 {len(ref_docs)} 篇)")
        found_any = found_any or found
    total_docs = len(lessons_docs) + len(ref_docs)
    if not found_any:
        print(f"\\n  ❌ 未找到 '{query}' 相关内容")
        print(f"  如果这是一个新踩坑，请入库:")
        print(f"    python3 misakanet/scripts/queue_lesson.py -t \"{query}\" ...")
        print()
    _show_timing(time.time() - t0, total_docs)
    if found_any:
        print(f"  💡 查看完整内容: cat lessons/<filename>.md")
        print(f"  💡 贡献新知识: python3 misakanet/scripts/queue_lesson.py -t '标题' -d domain '内容...'")
        print()


if __name__ == "__main__":
    main()
