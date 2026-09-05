#!/usr/bin/env python3
"""
Workers AI Lesson Benchmark (tiered / full-scan mode)
======================================================
Evaluate how Cloudflare Workers AI models handle real MisakaNet failure
scenarios, with RAG-ablation compare (with vs without lesson context).

Tiered strategy (Free-plan friendly, <10k neurons/day):
  - full model:  runs ALL lessons (light model, low neuron cost)
  - strong model: runs a representative subset (heavy model, high quality)

Features:
  - --all: full lesson scan (default: small sample)
  - concurrency + rate control (~250 req/min, Free limit 300/min)
  - resume cache: skips already-evaluated (model, scenario, condition)
  - lesson_hit_rate metric shows distinctiveness of repo lessons

Usage:
    python3 scripts/benchmark_workers_ai.py --all --compare \
        --full-model @cf/qwen/qwen2.5-coder-32b-instruct \
        --strong-model @cf/meta/llama-3.3-70b-instruct-fp8-fast \
        --strong-subset 40 --concurrency 5 \
        --output docs/benchmarks/latest.json

Auth: CLOUDFLARE_API_TOKEN env (CI) or mcporter OAuth (local).
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ACCOUNT = "6b92325b505f2b76aec49e9fe4195d31"
MC = str(Path(__file__).resolve().parents[1] / ".tools" / "bin" / "mcporter")
CFG = str(Path(__file__).resolve().parents[1] / ".tools" / "mcporter.json")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))  # audit T2.5: import misakanet.lesson_index

DEFAULT_FULL_MODEL = "@cf/meta/llama-3.2-3b-instruct"
# Strong model must stay within the Workers Free daily neuron allocation
# (10,000 neurons/day, $0.011/1000 over). 70B costs ~205k neurons per M
# output tokens — 86 runs blew the free pool and billed $0.11 on 2026-08-30.
# llama-3.1-8b-fp8-fast (~30k neurons/M output) keeps benchmarks free.
DEFAULT_STRONG_MODEL = "@cf/meta/llama-3.1-8b-instruct-fp8-fast"
RATE_PER_MIN = 250          # below Free 300/min
CONCURRENCY = 5
_CACHE_LOCK = __import__("threading").Lock()   # protects incremental JSON writes


def call_ai(model: str, prompt: str, timeout: int = 90) -> dict:
    """Call the model. Order: AI Gateway (AI_GATEWAY_ID) -> direct Workers AI
    (CLOUDFLARE_API_TOKEN) -> mcporter execute (local OAuth)."""
    gid = os.environ.get("AI_GATEWAY_ID")
    if gid:
        gtok = os.environ.get("AI_GATEWAY_TOKEN") or ""
        url = (f"https://gateway.ai.cloudflare.com/v1/{ACCOUNT}/{gid}"
               f"/workers-ai/run/{model}")
        req = urllib.request.Request(
            url,
            data=json.dumps({"messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"Authorization": f"Bearer {gtok}",
                     "Content-Type": "application/json",
                     "User-Agent": "misakanet-benchmark"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read())
            r_ = d.get("result") or d
            c = (r_.get("choices") and r_.get("choices")[0].get("message", {}).get("content")) or r_.get("response")
            return {"success": True, "status": r.status, "content": c, "errors": d.get("errors"), "gateway": gid}
        except urllib.error.HTTPError as e:
            body = e.read()[:250]
            return {"success": False, "status": e.code, "error": str(body)}
        except Exception as e:
            return {"success": False, "error": str(e)[:300]}
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if token:
        req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/{model}",
            data=json.dumps({"messages": [{"role": "user", "content": prompt}]}).encode(),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json",
                     "User-Agent": "misakanet-benchmark"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read())
            r_ = d.get("result") or {}
            c = (r_.get("choices") and r_.get("choices")[0].get("message", {}).get("content")) or r_.get("response")
            return {"success": d.get("success"), "status": d.get("status") or 200,
                    "content": c, "errors": d.get("errors")}
        except urllib.error.HTTPError as e:
            body = e.read()[:200]
            return {"success": False, "status": e.code, "error": str(body)}
        except Exception as e:
            return {"success": False, "error": str(e)[:300]}
    code = (
        "async () => { const res = await cloudflare.request({ method: 'POST', "
        f"path: '/accounts/{ACCOUNT}/ai/run/{model}', "
        f"body: {{ messages: [{{ role: 'user', content: {json.dumps(prompt)} }}] }} }}); "
        "const r = res.result || {}; "
        "const c = (r.choices && r.choices[0] && r.choices[0].message) "
        "? r.choices[0].message.content : (r.response || null); "
        "return { success: res.success, status: res.status, content: c, "
        "errors: res.errors }; }"
    )
    r = subprocess.run(
        [MC, "call", "cloudflare.execute", "code=" + code, "--config", CFG],
        capture_output=True, text=True, timeout=timeout,
    )
    try:
        return json.loads(r.stdout.strip())
    except json.JSONDecodeError:
        return {"success": False, "error": r.stdout[-300:]}


def score_response(content: str, reference_commands: list | None = None) -> dict:
    if not content:
        return {"length": 0, "commands": 0, "has_command_block": False,
                "actionable": False, "has_code_inline": False, "lesson_hits": 0, "lesson_hit_rate": 0.0}
    code_blocks = re.findall(r"```(?:bash|sh|shell|zsh)?\s*\n(.*?)```", content, re.S)
    commands = []
    for b in code_blocks:
        commands += [l.strip() for l in b.splitlines() if l.strip() and not l.strip().startswith("#")]
    inline_code = re.findall(r"`([^`]{3,})`", content)
    action_words = re.findall(r"\b(run|execute|install|configure|set|fix|use|try)\b", content, re.I)
    hits = 0
    if reference_commands:
        norm = content.lower()
        for rc in reference_commands:
            key = rc.lower()
            if key in norm or any(k in norm for k in key.split() if len(k) > 4):
                hits += 1
    rate = (hits / len(reference_commands)) if reference_commands else 0.0
    return {
        "length": len(content),
        "commands": len(commands),
        "command_list": commands[:5],
        "has_command_block": bool(code_blocks),
        "actionable": len(action_words) >= 2,
        "inline_code_count": len(inline_code),
        "lesson_hits": hits,
        "lesson_hit_rate": round(rate, 3),
    }


def _extract_commands(md: Path) -> list[str]:
    """Extract real executable commands from a lesson's Fix/Solution section.

    Only fenced blocks with an executable language tag (bash/sh/shell/zsh) are
    treated as commands. Plain fenced blocks without a language tag are often
    ASCII flow diagrams (e.g. 'PR opened -> Shadow Branch -> ...') — those are
    NOT commands and must be skipped, otherwise the reference answer fed to the
    model is misleading (observed: 8B hit 100% -> 50% on auto-merge lesson).
    """
    text = md.read_text(encoding="utf-8", errors="ignore")
    # Fix/Solution section spans from its heading to the NEXT top-level (## X)
    # heading — ### subsections belong to the fix body and must be included.
    fix_sec = re.search(r"## (?:Solution|Fix|修复|解法)\s*\n(.*?)(?=\n##\s|[ \t]*\Z)", text, re.S)
    if not fix_sec:
        return []
    cmds: list[str] = []
    # Inline backticks are commands only when they are single-line shell-ish
    # tokens. Skip multi-line spans and flow/pseudo-code: arrows (->, →),
    # prose filler words, and step-like numbering indicate prose, not a command.
    for m in re.finditer(r"`([^`]{6,})`", fix_sec.group(1)):
        tok = m.group(1).strip()
        if "\n" in tok or "→" in tok or "->" in tok:
            continue
        # Skip prose markers: CJK chars, em/en-dashes, filler words.
        if re.search(r"[\u4e00-\u9fff—–…]", tok):
            continue
        if _looks_like_command(tok):
            cmds.append(tok)
    # Fenced blocks: executable shells (bash/sh/shell/zsh) extract every line;
    # yaml/yml extracts only lines under a `run:` key (GitHub Actions style).
    for m in re.finditer(r"```(bash|sh|shell|zsh|yaml|yml)\s*\n(.*?)```", fix_sec.group(1), re.S):
        lang, block = m.group(1).lower(), m.group(2)
        if lang in ("yaml", "yml"):
            in_run, run_indent = False, None
            for line in block.splitlines():
                if re.match(r"^\s*run\s*:\s*\|?\s*$", line):
                    in_run, run_indent = True, len(line) - len(line.lstrip())
                    continue
                if in_run:
                    indent = len(line) - len(line.lstrip())
                    s = line.strip()
                    if not s:
                        continue
                    if indent <= run_indent:  # back to a sibling yaml key
                        if re.match(r"^[a-zA-Z_]+:", s) and s.split(":",1)[0] not in ("run",):
                            in_run = False
                            continue
                    if s and not s.startswith("#") and not re.match(r"^[a-z_]+:", s) and _looks_like_command(s):
                        cmds.append(s)
        else:
            for line in block.splitlines():
                s = line.strip()
                if s and not s.startswith("#") and _looks_like_command(s):
                    cmds.append(s)
    return list(dict.fromkeys(cmds))[:8]


def _looks_like_command(line: str) -> bool:
    """Heuristic: does this line read like an executable shell command?

    Filters prose/flow text out of extracted candidates. A line is a command
    if it starts with a known command word or contains shell syntax (assignment,
    $var, pipe, redirect, sub-shell, flag options) — prose filler won't.
    """
    s = line.strip()
    if not s or len(s) > 200:
        return False
    if re.search(r"[\u4e00-\u9fff]", s):        # CJK prose
        return False
    if re.match(r"^[A-Za-z][A-Za-z0-9_./-]*(\s|$)", s):   # starts like a command name
        # reject sentence-like prose
        if re.search(r"\b(?:is|are|was|were|the|a|an|and|or|of|for|to|when|if|this|that|these|those|it|will|should|can|may|must|not|only|after|before|use|uses|using|based)\b", s, re.I) and not re.search(r"[=|<>&|;`$]", s):
            return False
        return True
    # command continuation / shell syntax lines
    return bool(re.search(r"^(?:[A-Za-z_][\w]*=|\$\(|[\w./-]+(?: |$).*[-][a-zA-Z])", s)) and not re.search(r"\b(?:is|are|the|a|an|of|for|to)\b", s, re.I)


def _lesson_has_commands(md: Path) -> bool:
    return bool(_extract_commands(md))


def load_all_scenarios() -> list[str]:
    """Load ALL canonical lessons as scenarios (deduped, audit T2.5);
    command-bearing first, then the rest."""
    from misakanet.lesson_index import canonical_lessons

    with_cmds, without_cmds = [], []
    for md in canonical_lessons(REPO / "lessons"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        title = ""
        fm = re.search(r"^---\n(.*?)\n---", text, re.S)
        if fm:
            t = re.search(r"title:\s*(.+)", fm.group(1))
            if t:
                title = t.group(1).strip().strip("'\"")
        problem_match = re.search(r"## (?:Problem|问题)\s*\n(.*?)(?:\n##|\Z)", text, re.S)
        problem = problem_match.group(1).strip() if problem_match else ""
        scene = (title or problem)
        if scene and len(scene) > 20:
            entry = f"{scene} ({md.stem})"
            (with_cmds if _lesson_has_commands(md) else without_cmds).append(entry)
    return with_cmds + without_cmds


def load_lesson_context(scene: str, max_chars: int = 1500) -> tuple:
    stem = scene.rsplit("(", 1)[-1].rstrip(")") if scene.endswith(")") else ""
    if stem:
        # Scenarios come from canonical_lessons, so lookups only need to walk
        # that same canonical set (audit T2.5).
        from misakanet.lesson_index import canonical_lessons

        for p in canonical_lessons(REPO / "lessons"):
            if p.stem != stem:
                continue
            text = p.read_text(encoding="utf-8", errors="ignore")
            body = re.sub(r"^---\n.*?\n---", "", text, flags=re.S)
            clean = re.sub(r"[#*`>]", "", body)
            cmds = _extract_commands(p)
            return clean.strip()[:max_chars], cmds
    return "", []


def load_cache(path: Path) -> dict:
    if path and path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"runs": []}


_QUOTA_HIT = {"flag": False}   # set when daily neurons quota exhausted

# Neuron consumption per model (per M input/output tokens), from
# developers.cloudflare.com/workers-ai/platform/pricing. Used to enforce a
# free-tier budget so benchmarks never bill (2026-08-30: 70B runs billed
# $0.11 past the 10k/day free allocation).
MODEL_NEURONS_PER_MTOK = {
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": (26668, 204805),
    "@cf/meta/llama-3.1-8b-instruct-fp8-fast": (4625, 30475),
    "@cf/meta/llama-3.2-3b-instruct": (2457, 18252),
    "@cf/qwen/qwen2.5-coder-32b-instruct": (60000, 90909),
    "@cf/qwen/qwen3-30b-a3b-fp8": (60000, 90909),
}
_BUDGET = {"remaining": 10000.0}   # free-tier neurons left this run


def estimate_neurons(model: str, prompt: str, content: str) -> float:
    """Rough neuron cost of one call (input tokens ~ len/4, output ~ len/4)."""
    inp, out = MODEL_NEURONS_PER_MTOK.get(model, (2457, 18252))
    return (len(prompt) / 4 / 1e6 * inp) + (len(content) / 4 / 1e6 * out)


def run_one(args, model, scene, condition, prompt, ref_cmds, out_path):
    if _QUOTA_HIT["flag"]:
        return {"status": 429, "quota": True}
    est = estimate_neurons(model, prompt, "")
    if est > _BUDGET["remaining"]:
        _QUOTA_HIT["flag"] = True
        print(f"  ⛔ neuron budget exhausted (remaining {_BUDGET['remaining']:.0f} < "
              f"est {est:.0f} for {model}) — stopping to stay free-tier", flush=True)
        return {"status": 429, "quota": True}
    resp = call_ai(model, prompt)
    content = resp.get("content") or ""
    _BUDGET["remaining"] -= estimate_neurons(model, prompt, content)
    metrics = score_response(content, ref_cmds)
    run = {"model": model, "scenario": scene, "condition": condition,
           "status": resp.get("status"), "content": content, "metrics": metrics,
           "error": resp.get("errors") or resp.get("error")}
    err_text = json.dumps(run.get("error") or "").lower()
    if resp.get("status") == 429 or "daily free allocation" in err_text or "neurons" in err_text:
        _QUOTA_HIT["flag"] = True
        print("  ⛔ daily neurons quota exhausted — stopping further calls (resume later)", flush=True)
    with _CACHE_LOCK:
        data = load_cache(out_path)
        data.setdefault("models", [])
        data.setdefault("scenarios", [])
        data["runs"].append(run)
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    name = model.rsplit("/", 1)[-1]
    print(f"  ✓ {name} × {scene[:40]} [{condition}] "
          f"len={metrics['length']} hit={int(metrics['lesson_hit_rate']*100)}%", flush=True)
    return run


def main() -> int:
    ap = argparse.ArgumentParser(description="Workers AI tiered lesson benchmark")
    ap.add_argument("--all", action="store_true", help="full lesson scan (default: sample)")
    ap.add_argument("--scenarios", type=int, default=4, help="sample size when not --all")
    ap.add_argument("--compare", action="store_true", help="with vs without lesson context")
    ap.add_argument("--full-model", default=DEFAULT_FULL_MODEL, help="light model, runs all")
    ap.add_argument("--strong-model", default=DEFAULT_STRONG_MODEL, help="heavy model, runs subset")
    ap.add_argument("--strong-subset", type=int, default=40, help="lessons for strong model")
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--output", default="docs/benchmarks/latest.json")
    ap.add_argument("--neuron-budget", type=float, default=10000.0,
                    help="free-tier neuron budget; stop before billing (default 10000)")
    args = ap.parse_args()
    _BUDGET["remaining"] = args.neuron_budget

    scenarios = load_all_scenarios() if args.all else (load_all_scenarios()[:args.scenarios])
    print(f"Scenarios: {len(scenarios)} total ({'FULL' if args.all else 'sample'})")
    print(f"full model: {args.full_model} (all {len(scenarios)})")
    strong_n = min(args.strong_subset, len(scenarios))
    print(f"strong model: {args.strong_model} (top {strong_n})")

    out_path = Path(args.output)
    data = load_cache(out_path)
    cache_keys = {(r["model"], r["scenario"][:80], r.get("condition", "-"))
                  for r in data.get("runs", [])}
    print(f"cache: {len(cache_keys)} runs already done, resuming")

    tasks = []
    for i, scene in enumerate(scenarios):
        ctx, ref_cmds = load_lesson_context(scene)
        models = [(args.full_model, False)]
        if i < strong_n:
            models.append((args.strong_model, True))
        for model, _ in models:
            if args.compare:
                tasks.append((model, scene, "with_lesson",
                              f"I hit this error and need a fix:\n{scene}\n\n"
                              f"Here is a verified lesson about this failure:\n{ctx}\n\n"
                              f"Give a concrete, actionable fix with exact commands.",
                              ref_cmds))
                tasks.append((model, scene, "plain",
                              f"I hit this error and need a fix:\n{scene}\n\n"
                              f"Give a concrete, actionable fix with exact commands.",
                              ref_cmds))
            else:
                tasks.append((model, scene, "plain",
                              f"I hit this error and need a fix:\n{scene}\n\n"
                              f"Give a concrete, actionable fix with exact commands.",
                              ref_cmds))

    todo = [t for t in tasks if (t[0], t[1][:80], t[2]) not in cache_keys]
    print(f"Total tasks: {len(tasks)} | to run: {len(todo)} (skipping {len(tasks)-len(todo)} cached)")
    start = time.time()
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = set()
        for task in todo:
            if _QUOTA_HIT["flag"]:
                break
            futures.add(ex.submit(run_one, args, *task, out_path))
            if len(futures) >= args.concurrency:
                finished, futures = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                for f in finished:
                    try:
                        f.result()
                    except Exception as e:
                        print("task err:", e)
                    done += 1
        for f in concurrent.futures.as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print("task err:", e)
            done += 1

    print(f"\nDone {done} runs in {time.time()-start:.0f}s. Report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

