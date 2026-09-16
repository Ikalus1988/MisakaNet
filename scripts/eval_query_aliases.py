#!/usr/bin/env python3
"""Offline before/after evaluation of the query-alias expansion layer.

    python3 scripts/eval_query_aliases.py                 # engine backend (default)
    python3 scripts/eval_query_aliases.py --backend bm25   # pure BM25, no synonyms
    python3 scripts/eval_query_aliases.py --json
    python3 scripts/eval_query_aliases.py --max-expansions 8   # how the cap moves the numbers

Offline only: no network, no server, no model. Both backends read lessons/ from disk.

Backends
    engine : misakanet.search.engine._rank_docs — the local production-ish path used by
             search_knowledge.py. It already applies engine._SYNONYM_MAP (32 tokens) and
             metadata boosts, and the CLI drops everything below score 0.1. Both the
             BEFORE and the AFTER column go through it, so the delta isolates the alias
             table rather than the engine.
    bm25   : misakanet_core.BM25 over engine._tokenize, no synonym map at all — the
             cleanest measurement of what the alias table itself buys.

A query counts as a hit when ANY acceptable lesson is the top-1 result (hit@1) or is
inside the top-3 (hit@3). Several questions genuinely have more than one right lesson,
so `accept` lists them; `primary` is the one the question is really about.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "scripts"), str(REPO)]  # expand_query + the misakanet package

import expand_query  # noqa: E402  (same directory, stdlib-only module)

from misakanet.search.engine import (  # noqa: E402  (repo package, cwd-independent)
    LESSONS,
    _load_docs,
    _rank_docs,
)

ENGINE_MIN_SCORE = 0.1   # search_knowledge.py MIN_SCORE_THRESHOLD

# (query, primary lesson, other acceptable lessons, why the corpus answers it)
QUERIES: list[tuple[str, str, list[str], str]] = [
    ("如何切换模型", "lessons/contrib/model-switch-script-pattern.md", [],
     "多模型 Switch 脚本模式 — 双 Agent 模型管理"),
    ("pip 安装超时怎么办", "lessons/contrib/pip-install-timeout-ssl.md", [],
     "pip install Network Timeout / SSL ErrorFix"),
    ("pip install 卡住不动", "lessons/contrib/lesson-08-pip-https-proxy-clash.md", [],
     "pip install HTTPS Timeout from WSL — Prepend HTTPS_PROXY"),
    ("公司代理导致 SSL 证书校验失败", "lessons/contrib/pip-install-proxy-timeout.md",
     ["lessons/contrib/corporate-proxy-curl-timeout.md"],
     "ReadTimeoutError Behind Corporate Proxy: Certificate Validation"),
    ("磁盘空间不足怎么清理", "lessons/contrib/disk-space-cleanup.md", [],
     "磁盘空间不足 / chroma_db_v4 CacheCleanup"),
    ("权限不足无法执行", "lessons/contrib/permission-denied-fix.md", [],
     "Permission Denied / WSL NTFS 跨文件系统 PermissionFix"),
    ("定时任务不执行", "lessons/contrib/cron-job-not-running.md", [],
     "Cron 作业不执行 / 不生效排障"),
    ("Python 改了代码不生效", "lessons/contrib/python-pycache-stale.md", [],
     "Python 代码修改不生效 — stale .pyc Cache"),
    ("中文乱码怎么解决", "lessons/contrib/python-gbk-encoding-error.md",
     ["lessons/contrib/wsl-pip-gbk-hub-poller-crash.md",
      "lessons/contrib/aider-windows-unicode-error.md"],
     "Python GBK Encoding Error — Windows/WSL 跨平台"),
    ("装了包还是提示模块找不到", "lessons/contrib/python-venv-tiktoken-module-not-found.md",
     ["lessons/import-path-verification-after-refactor.md"],
     "venv 中 tiktoken 安装后仍报 ModuleNotFoundError"),
    ("飞书机器人收不到消息",
     "lessons/contrib/feishu-gateway-group-policy-silently-drops-messages.md", [],
     "飞书 bot 在群聊里静默吞消息 — 双层 allowlist 陷阱"),
    ("WSL 内存占用过高", "lessons/contrib/wsl2-memory-leak-fix.md", [],
     "WSL2 内存泄漏 / 内存占用过高"),
    ("容器内存不足被杀死", "lessons/contrib/kubernetes-crashloopbackoff-debugging.md", [],
     "Exit code 137 indicates Kubernetes hit the memory limit and killed the container"),
    ("DCO 签名失败怎么办", "lessons/contrib/dco-signoff-force-push-pitfall.md",
     ["lessons/contrib/ci-dco-decouple-pythonpath-fork-pr.md",
      "lessons/contrib/error-dco-signoff-windows.md"],
     "DCO Signoff Lost During Force Push + 另两篇 DCO 课程"),
    ("Node.js 连接被重置", "lessons/contrib/n8n-nodejs-econnreset-connection-reset-fix.md", [],
     "Fix Node.js ECONNRESET Connection Reset Error"),
    ("git TLS 握手失败", "lessons/contrib/git-tls-handshake-failure.md", [],
     "GitHub TLS 握手失败 — gnutls_handshake() Error"),
    ("向量检索召回率低", "lessons/contrib/bm25-vector-hybrid-search-weights.md",
     ["lessons/contrib/rag-retrieval-six-layer-silent-degradation.md"],
     "BM25 + Vector Hybrid Search: configurable blending weights"),
    ("机器人报警代码", "lessons/contrib/fanuc-alarm-code-reference.md", [],
     "FANUC Robot Alarm Code Reference Table"),
    ("YAML 内联注释导致类型错误", "lessons/contrib/yaml-inline-comment-type-coercion.md", [],
     "YAML 内联注释导致类型强制转换失败"),
    ("浏览器自动化被拦截", "lessons/contrib/browser-automation-csp-bypass.md", [],
     "CSP blocks JavaScript injection in browser automation"),
]


def _rel(doc) -> str:
    try:
        return doc.filepath.relative_to(REPO).as_posix()
    except ValueError:
        return doc.filepath.as_posix()


def _rank_engine(query: str, docs: list, k: int) -> tuple[list[str], int]:
    ranked = _rank_docs(query, docs)
    passed = [(s, d) for s, d in ranked if s >= ENGINE_MIN_SCORE]
    return [_rel(d) for _, d in passed[:k]], len(passed)


def build_bm25_index(docs: list):
    from misakanet_core import BM25, ScoredDocument
    scored = [ScoredDocument(_rel(d), expand_query.tokenize(d.content)) for d in docs]
    return BM25(scored)


def _rank_bm25(engine, query: str, k: int) -> tuple[list[str], int]:
    size = len(engine.documents) if hasattr(engine, "documents") else 400
    hits = engine.search(query, top_k=size)
    passed = [h for h in hits if getattr(h, "score", 0) > 0]
    return [h.doc_id for h in passed[:k]], len(passed)


def drop_cjk_residue(query: str) -> str:
    """Strip single CJK chars left over after expansion.

    Probe, not a recommendation: the local engine tokenizes CJK one char at a time and
    the Worker drops it entirely, so the residue looked like pure noise — it is not,
    see --drop-cjk-residue in the design doc's "did not help" section.
    """
    return " ".join(t for t in expand_query.tokenize(query)
                    if not re.fullmatch(r"[\u4e00-\u9fff]", t))


def evaluate(backend: str, table: dict, max_expansions: int, keep_original: bool,
             strip_residue: bool = False) -> list[dict]:
    docs = _load_docs(LESSONS, is_lesson=True)
    bm25 = build_bm25_index(docs) if backend == "bm25" else None

    def rank(query: str, k: int) -> tuple[list[str], int]:
        return _rank_bm25(bm25, query, k) if backend == "bm25" else _rank_engine(query, docs, k)

    rows = []
    for query, primary, extra, why in QUERIES:
        accept = [primary] + list(extra)
        rep = expand_query.expand(query, table, max_expansions=max_expansions,
                                 keep_original=keep_original)
        if strip_residue:
            rep["expanded"] = drop_cjk_residue(rep["expanded"])
            rep["worker_tokens"] = expand_query.worker_tokens(rep["expanded"])
        before1, before_n = rank(query, 1)
        before3, _ = rank(query, 3)
        after1, after_n = rank(rep["expanded"] or query, 1)
        after3, _ = rank(rep["expanded"] or query, 3)
        rows.append({
            "query": query, "primary": primary, "accept": accept, "why": why,
            "expanded": rep["expanded"], "added": [t["term"] for t in rep["added_terms"]],
            "worker_before": expand_query.worker_tokens(query),
            "worker_after": rep["worker_tokens"],
            "before_top1": before1[0] if before1 else None,
            "before_top3": before3,
            "after_top1": after1[0] if after1 else None,
            "after_top3": after3,
            "before_hit1": bool(before1 and before1[0] in accept),
            "before_hit3": any(p in accept for p in before3),
            "after_hit1": bool(after1 and after1[0] in accept),
            "after_hit3": any(p in accept for p in after3),
            "before_candidates": before_n, "after_candidates": after_n,
        })
    return rows


def _mark(row: dict, key: str) -> str:
    return "✓" if row[key] else "✗"


def report(rows: list[dict], backend: str, max_expansions: int, keep_original: bool) -> dict:
    n = len(rows)
    b1 = sum(r["before_hit1"] for r in rows)
    b3 = sum(r["before_hit3"] for r in rows)
    a1 = sum(r["after_hit1"] for r in rows)
    a3 = sum(r["after_hit3"] for r in rows)
    print(f"\n=== query-alias expansion — backend={backend} "
          f"max_expansions={max_expansions} keep_original={keep_original} — n={n} ===")
    print(f"{'query':<26} {'b@1':>4} {'b@3':>4} {'a@1':>4} {'a@3':>4}  expanded")
    print("-" * 118)
    for r in rows:
        q = r["query"][:24] + ("…" if len(r["query"]) > 24 else "")
        print(f"{q:<26} {_mark(r, 'before_hit1'):>4} {_mark(r, 'before_hit3'):>4} "
              f"{_mark(r, 'after_hit1'):>4} {_mark(r, 'after_hit3'):>4}  {r['expanded'][:56]}")
    print("-" * 118)
    print(f"{'HIT RATE':<26} {b1}/{n} {b3}/{n} {a1}/{n} {a3}/{n}")
    print(f"{'  as %':<26} {100*b1/n:5.0f} {100*b3/n:5.0f} {100*a1/n:5.0f} {100*a3/n:5.0f}")
    delta = {"top1": a1 - b1, "top3": a3 - b3}
    print(f"  delta: top-1 {delta['top1']:+d}  top-3 {delta['top3']:+d}")
    worse1 = [r for r in rows if r["before_hit1"] and not r["after_hit1"]]
    worse3 = [r for r in rows if r["before_hit3"] and not r["after_hit3"]]
    better1 = [r for r in rows if r["after_hit1"] and not r["before_hit1"]]
    noise = [r for r in rows if r["before_candidates"] and r["after_candidates"]]
    if noise:
        mb = sum(r["before_candidates"] for r in noise) / len(noise)
        ma = sum(r["after_candidates"] for r in noise) / len(noise)
        print(f"  mean docs above the score floor: before {mb:.0f} → after {ma:.0f}")
    for label, group in (("gained top-1", better1), ("lost top-1", worse1), ("lost top-3", worse3)):
        print(f"  {label:13s}({len(group)}): " + (", ".join(r["query"] for r in group) or "none"))
    print(f"  still missing({sum(not r['after_hit3'] for r in rows)}): "
          + (", ".join(r["query"] for r in rows if not r["after_hit3"]) or "none"))
    # Production tokenizer (workers/register-proxy-sw.js bm25Tokenize): does the query
    # even reach searchLessonsBM25 with a term? This is corpus-independent — a Chinese
    # query tokenizes to [] there, so the whole index is unreachable, not just misranked.
    empty_before = [r for r in rows if not r["worker_before"]]
    empty_after = [r for r in rows if not r["worker_after"]]
    print(f"\n  worker bm25Tokenize: queries with ZERO query terms before {len(empty_before)}/{n}"
          f" → after {len(empty_after)}/{n}")
    for r in empty_before:
        print(f"    {r['query']:<28} [] → {r['worker_after']}")
    return {"n": n, "backend": backend, "max_expansions": max_expansions,
            "keep_original": keep_original, "before_top1": b1, "before_top3": b3,
            "after_top1": a1, "after_top3": a3, "delta_top1": delta["top1"],
            "delta_top3": delta["top3"],
            "worker_empty_before": len(empty_before), "worker_empty_after": len(empty_after),
            "gained_top1": [r["query"] for r in better1],
            "lost_top1": [r["query"] for r in worse1],
            "lost_top3": [r["query"] for r in worse3],
            "still_missing": [r["query"] for r in rows if not r["after_hit3"]],
            "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline before/after eval of query alias expansion")
    ap.add_argument("--backend", choices=("engine", "bm25"), default="engine")
    ap.add_argument("--max-expansions", type=int, default=expand_query.MAX_EXPANSIONS)
    ap.add_argument("--keep-original", action="store_true",
                    help="keep tokens that `replace` kinds would drop")
    ap.add_argument("--table", default=str(expand_query.DEFAULT_TABLE))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sweep", action="store_true",
                    help="also run with --keep-original to show how much `replace` matters")
    ap.add_argument("--drop-cjk-residue", action="store_true",
                    help="probe: strip unmatched CJK chars after expansion")
    args = ap.parse_args(argv)
    table = expand_query.load_table(Path(args.table))
    runs = [report(evaluate(args.backend, table, args.max_expansions, args.keep_original,
                            args.drop_cjk_residue),
                   args.backend, args.max_expansions, args.keep_original)]
    if args.sweep and not args.keep_original:
        runs.append(report(evaluate(args.backend, table, args.max_expansions, True),
                           args.backend, args.max_expansions, True))
    if args.json:
        print(json.dumps(runs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
