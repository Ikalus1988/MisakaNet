#!/usr/bin/env python3
"""intake_bot decision benchmark runner. Loads tests/benchmarks/intake_benchmark.json,
injects corpus offline (no network). Metrics: hit_precision, hit_recall, noise_ignore,
fp_count. Usage: --check (exit 1 below defaults) / --json / --sim <th>."""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.intake_bot import _detect_stack, decide  # noqa: E402

BENCH = REPO / "tests" / "benchmarks" / "intake_benchmark.json"
DEFAULTS = {"hit_precision": 0.85, "hit_recall": 0.90, "noise_ignore": 0.90, "max_fp": 0}


def run(sim_threshold):
    data = json.loads(BENCH.read_text(encoding="utf-8"))
    corpus = data["corpus"]
    domain_of = {c["id"]: (c.get("domain") or "") for c in corpus}
    stack_cache = {}

    def stack_of(doc_id):
        if doc_id not in stack_cache:
            for c in corpus:
                if c["id"] == doc_id:
                    hay = " ".join([c.get("title") or "", c.get("domain") or "",
                                    " ".join(c.get("tags") or [])])
                    stack_cache[doc_id] = _detect_stack(hay)
                    break
            else:
                stack_cache[doc_id] = set()
        return stack_cache[doc_id]

    stats = {"correct_hit": 0, "wrong_hit": 0, "expected_hit": 0,
             "expected_no_hit": 0, "ignored_ok": 0, "ignore_class": 0}
    failures = []
    for s in data["samples"]:
        kind = s["kind"]
        r = decide(s["error"], source="benchmark", what_tried="", auto_intake=False,
                   sim_threshold=sim_threshold, force=False, corpus=corpus)
        d = r["decision"]
        if kind == "hit":
            stats["expected_hit"] += 1
            lid = (r.get("lesson") or {}).get("id")
            exp = s.get("expect", [""])[0]
            ok = d == "hit" and (lid in s.get("expect", []) or
                                 (lid in domain_of and domain_of[lid] and domain_of[lid] == domain_of.get(exp, "")) or
                                 bool(stack_of(lid) & stack_of(exp)))
            if ok:
                stats["correct_hit"] += 1
            else:
                failures.append((s["id"], "hit-miss", d, s["error"][:80]))
        elif kind == "no-hit":
            stats["expected_no_hit"] += 1
            if d == "hit":
                stats["wrong_hit"] += 1
                failures.append((s["id"], "fp", d, s["error"][:80]))
        elif kind == "ignore":
            stats["ignore_class"] += 1
            if d == "ignore":
                stats["ignored_ok"] += 1
            else:
                failures.append((s["id"], "not-ignored", d, s["error"][:80]))
    tp = stats["correct_hit"]
    stats["hit_precision"] = tp / (tp + stats["wrong_hit"]) if (tp + stats["wrong_hit"]) else 0.0
    stats["hit_recall"] = tp / stats["expected_hit"] if stats["expected_hit"] else 0.0
    stats["noise_ignore"] = stats["ignored_ok"] / stats["ignore_class"] if stats["ignore_class"] else 0.0
    stats["fp_count"] = stats["wrong_hit"]
    return stats, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if below thresholds")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sim", type=float, default=0.45)
    a = ap.parse_args()
    stats, failures = run(a.sim)
    if a.json:
        print(json.dumps({"metrics": stats, "failures": failures[:20], "n_failures": len(failures)},
                         ensure_ascii=False))
        return 0
    print("intake_bot decision benchmark")
    print(f"  hit_precision = {stats['hit_precision']:.2f}  (correct={stats['correct_hit']}, fp={stats['wrong_hit']})")
    print(f"  hit_recall    = {stats['hit_recall']:.2f}  (expected={stats['expected_hit']})")
    print(f"  noise_ignore  = {stats['noise_ignore']:.2f}  ({stats['ignored_ok']}/{stats['ignore_class']})")
    if failures:
        print(f"  failures ({len(failures)}):")
        for f in failures[:10]:
            print("   ", f[0], f[1], f[2], "|", f[3])
    if a.check:
        bad = []
        for k, v in DEFAULTS.items():
            if k == "max_fp":
                if stats["fp_count"] > v:
                    bad.append(f"{k}={stats['fp_count']}>{v}")
            elif stats[k] < v:
                bad.append(f"{k}={stats[k]:.2f}<{v}")
        if bad:
            print("BENCHMARK FAIL:", "; ".join(bad))
            return 1
        print("BENCHMARK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
