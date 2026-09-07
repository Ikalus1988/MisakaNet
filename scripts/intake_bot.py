#!/usr/bin/env python3
"""misaka-intake-bot MVP — 报错 → 预查建议 → 可靠 intake 决策（零依赖，stdlib only）

构想（docs/agents/crawler-intake-bot.md）的最小实现，供爬虫/外部仓库与 zsxh 实测。
设计取舍：suggest 可宽、intake 必严；默认只报告（dry-run），显式 --auto-intake 才提交。

用法:
    python3 scripts/intake_bot.py --error "ModuleNotFoundError: No module named 'x'" [--auto-intake] [--json]
    python3 scripts/intake_bot.py --log ci.log            # 从日志尾部提取错误
    python3 scripts/intake_bot.py --demo                  # 内置样例演示 命中/采集/忽略 三态
    echo "Error: boom" | python3 scripts/intake_bot.py    # stdin

决策三态:
    hit     预查命中已有课程 → 打印建议（链接+修复摘录），不 intake（建议可宽）
    intake  指纹新颖 + 证据达标 → 打印将提交内容（--auto-intake 才真实调用 submit_intake）
    ignore  重复 / 无证据 / 纯噪音 → 一行原因，静默

噪音闸（MVP 版，对应设计五闸中的 2/3/4）:
    闸2 指纹去重（~/.cache/misaka-intake-bot/sigs.json，sha1 归一化错误）
    闸3 预查命中门（GET https://misakanet.org/api/lessons 免注册，标题/正文 token 重叠）
    闸4 质量门槛（错误 ≥10 字符、非占位/回声模式；--force 可绕过仅用于自测）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

REMOTE_LESSONS = "https://misakanet.org/api/lessons"          # ?search=<q>&limit=N 服务端检索
INTAKE_URL = "https://misakanet.org/mcp"
UA = "MisakaNet-IntakeBot-MVP/0.1"
_CACHE_ROOT = os.environ.get("MISAKA_CACHE_DIR") or os.environ.get("XDG_CACHE_HOME")
CACHE_DIR = Path(_CACHE_ROOT or (Path.home() / ".cache")) / "misaka-intake-bot"
SIG_FILE = CACHE_DIR / "sigs.json"
CORPUS_FILE = CACHE_DIR / "corpus.json"
DEFAULT_HIT_SIM = 0.30  # 命中确认阈值：title 重叠 ×2 / body 重叠，取 max；--sim 可调
PRECHECK_LIMIT = 5      # 服务端返回 top-N 供本地确认

PLACEHOLDER_RE = re.compile(
    r"todo|fixme|coming soon|placeholder|echo\s+.*verified|(grep|wc)\s+.*\|\s*wc",
    re.I,
)
ERROR_LINE_RE = re.compile(
    r"(?P<err>[A-Za-z_][\w.]*(?:Error|Exception|Failure|Fault|Fatal)[^\n]{0,160})"
    r"|(?:HTTP[^\n]{0,40}(?:4\d\d|5\d\d))"
    r"|(?:FAILED[^\n]{0,120})"
    r"|(?:Traceback[^\n]*|[A-Za-z_][\w.]*Error:[^\n]{0,160})",
    re.I,
)


# ── 闸 3 预查（免注册，服务端检索 + 本地命中确认）──────────
_STOP = {"error", "errors", "exception", "exceptions", "failed", "fail", "fails",
         "failure", "fatal", "issue", "issues", "problem", "problems", "boom",
         "generic", "occurred", "something", "went", "wrong", "the", "and",
         "with", "after", "when", "while", "from", "this"}


def _tokens(text: str) -> set[str]:
    toks = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}|[\u4e00-\u9fff]{2,}", (text or "").lower()))
    return toks - _STOP


def _sim(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


_CORPUS_TTL = 300  # seconds


def _load_corpus(timeout: int = 60) -> list[dict]:
    """拉全量语料（limit=5000，~360 lessons）本地打分。缓存 300s 吸收冷启动延迟。失败返回 []（降级）。"""
    if CORPUS_FILE.exists() and time.time() - CORPUS_FILE.stat().st_mtime < _CORPUS_TTL:
        try:
            return json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    try:
        req = urllib.request.Request(f"{REMOTE_LESSONS}?limit=5000",
                                     headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, list) and data:
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                CORPUS_FILE.write_text(json.dumps(data), encoding="utf-8")
            except OSError:
                pass
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[warn] 预查不可用（{e}），跳过命中门（novel → intake 候选，服务端兜底）",
              file=sys.stderr)
        return []


def precheck(error: str, sim_threshold: float) -> dict | None:
    """全量语料本地打分（title 重叠 ×2 / body 重叠，与 search_knowledge --remote
    同一数据源）。命中返回最佳课程 dict；无命中/网络失败返回 None。"""
    q = _tokens(error)
    if not q:
        return None
    best, best_score = None, 0.0
    for doc in _load_corpus():
        title = _tokens(doc.get("title") or "")
        body = _tokens((doc.get("description") or "")[:500])
        score = max(_sim(q, title) * 2.0, _sim(q, body))
        if score > best_score:
            best, best_score = doc, score
    if best and best_score >= sim_threshold:
        best["_sim"] = best_score
        return best
    return None


# ── 闸 2 指纹去重 ─────────────────────────────────────────
def fingerprint(error: str) -> str:
    norm = re.sub(r"0x[0-9a-f]+|\b\d{2,}\b|\b\w+@\w+", "", error.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def load_sigs() -> dict:
    try:
        return json.loads(SIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_sigs(sigs: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        SIG_FILE.write_text(json.dumps(sigs, indent=0), encoding="utf-8")
    except OSError:
        pass


# ── 闸 4 质量门槛 ─────────────────────────────────────────
def quality_gate(error: str, what_tried: str) -> tuple[bool, str]:
    err = (error or "").strip()
    if len(err) < 10:
        return False, "错误签名过短（<10 字符），缺证据"
    if PLACEHOLDER_RE.search(err + " " + what_tried):
        return False, "疑似占位/回声内容"
    return True, "ok"


# ── 签名提取（输入 → 错误签名）─────────────────────────────
def extract_error(text: str) -> str:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    for line in reversed(lines[-60:]):  # 尾部优先
        if ERROR_LINE_RE.search(line):
            return re.sub(r"\s+", " ", line)[:220]
    return re.sub(r"\s+", " ", " ".join(lines[-3:]))[:220]


def submit_intake(payload: dict) -> str:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "misakanet_submit_intake", "arguments": payload},
    })
    req = urllib.request.Request(
        INTAKE_URL, data=body.encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Origin": "https://github.com", "User-Agent": UA,
                 "MCP-Protocol-Version": "2025-06-18"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")[:400]


def decide(error: str, *, source: str, what_tried: str, auto_intake: bool,
           sim_threshold: float, force: bool, offline: bool = False) -> dict:
    sig = fingerprint(error)
    sigs = load_sigs()
    hit = None if offline else precheck(error, sim_threshold)
    if hit:
        return {"decision": "hit", "fingerprint": sig,
                "lesson": {"id": hit.get("id"), "title": hit.get("title"),
                           "url": f"https://misakanet.org/lessons/{hit.get('id') or ''}/",
                           "sim": round(hit.get("_sim", 0), 2)}}

    ok, reason = quality_gate(error, what_tried)
    seen = sigs.get(sig, 0)
    if seen and not force:
        return {"decision": "ignore", "fingerprint": sig, "reason": f"重复签名（第 {seen + 1} 次出现）"}
    if not ok and not force:
        return {"decision": "ignore", "fingerprint": sig, "reason": reason}

    payload = {"kind": "missing_lesson", "problem": error[:280], "error": error[:280],
               "what_tried": what_tried[:400], "source": source,
               "matched_lesson_id": "", "fix": "", "verification": ""}
    if auto_intake:
        receipt = submit_intake(payload)
        sigs[sig] = sigs.get(sig, 0) + 1
        save_sigs(sigs)
        return {"decision": "intake", "fingerprint": sig, "receipt": receipt[:200]}
    return {"decision": "intake", "fingerprint": sig, "dry_run": True, "payload": payload}


# ── CLI ────────────────────────────────────────────────────
def demo() -> int:
    # 命中样例用真实课程的可辨识错误文本（保证演示稳定命中）
    hit_err = ("git credential helper 401: credential lookup failed for "
               "https://github.com with helper path mismatch")
    novel_err = ("FetcherError: site returned 451 Unavailable For Legal "
                 "Reasons with flag=consent-gate")
    short_err = "it broke"
    samples = [
        ("命中样例（预查 → 建议，不 intake）", hit_err),
        ("新颖样例（intake 候选，dry-run）", novel_err),
        ("噪音样例（无证据 → 忽略）", short_err),
    ]
    for label, err in samples:
        print(f"\n=== {label}")
        res = decide(err, source="intake-bot-demo", what_tried="",
                     auto_intake=False, sim_threshold=DEFAULT_HIT_SIM, force=False)
        print(json.dumps(res, ensure_ascii=False)[:420])
    # 去重演示：同一新颖错误连续两次 → 第一次 intake 候选，第二次（已见指纹）忽略
    print("\n=== 去重样例（同一错误两次：首次候选 → 二次忽略）")
    r1 = decide(novel_err, source="intake-bot-demo", what_tried="",
                auto_intake=False, sim_threshold=DEFAULT_HIT_SIM, force=False)
    print("  第 1 次:", json.dumps(r1, ensure_ascii=False)[:200])
    save_sigs({r1["fingerprint"]: 1})
    r2 = decide(novel_err, source="intake-bot-demo", what_tried="",
                auto_intake=False, sim_threshold=DEFAULT_HIT_SIM, force=False)
    print("  第 2 次:", json.dumps(r2, ensure_ascii=False)[:200])
    print("\n[demo] 全部为本地决策；intake 候选为 dry-run，未真实提交。")
    print("提示：--sim 可调命中灵敏度；--auto-intake 才真实提交（重复签名自动去重）。")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MisakaNet intake bot MVP (suggest/collect, noise-safe)")
    ap.add_argument("--error", help="错误文本（优先）")
    ap.add_argument("--log", help="从日志文件尾部提取错误")
    ap.add_argument("--source", default="intake-bot", help="intake 来源标识（默认 intake-bot）")
    ap.add_argument("--what-tried", default="", help="已尝试内容（提高转正率）")
    ap.add_argument("--auto-intake", action="store_true", help="真实调用 submit_intake（默认 dry-run）")
    ap.add_argument("--sim", type=float, default=DEFAULT_HIT_SIM, help=f"命中阈值（默认 {DEFAULT_HIT_SIM}）")
    ap.add_argument("--offline", action="store_true", help="跳过远端预查")
    ap.add_argument("--force", action="store_true", help="绕过去重/质量闸（仅自测）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)

    if a.demo:
        return demo()

    if a.error:
        error = a.error.strip()
    elif a.log:
        try:
            error = extract_error(Path(a.log).read_text(encoding="utf-8", errors="ignore"))
        except OSError as e:
            print(json.dumps({"decision": "ignore", "reason": f"log 不可读: {e}"})); return 2
    elif not sys.stdin.isatty():
        error = extract_error(sys.stdin.read())
    else:
        ap.print_help(); return 2

    res = decide(error, source=a.source, what_tried=a.what_tried, auto_intake=a.auto_intake,
                 sim_threshold=a.sim, force=a.force, offline=a.offline)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        if res["decision"] == "hit":
            l = res["lesson"]
            print(f"💡 命中课程（sim={l['sim']}）：{l['title']}\n   {l['url']}")
            print("   已存在课程 → 不 intake；按该课程修复后再试仍失败请补 what_tried 重跑。")
        elif res["decision"] == "intake":
            if res.get("dry_run"):
                print(f"🧪 新颖失败，intake 候选（dry-run，未提交）。fingerprint={res['fingerprint']}")
                print(f"   将提交: {json.dumps(res['payload'], ensure_ascii=False)}")
                print("   加 --auto-intake 真实提交（每条签名每日自动去重）。")
            else:
                print(f"📥 已提交 intake。fingerprint={res['fingerprint']} receipt={res.get('receipt','')[:120]}")
        else:
            print(f"🚫 忽略：{res.get('reason')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
