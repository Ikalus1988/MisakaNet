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
    hit     预查命中已有课程 → 打印建议（链接+修复摘录），不 intake；命中仅为 suggest-only，请人工核对
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
UA = "MisakaNet-IntakeBot-v1.0"
_CACHE_ROOT = os.environ.get("MISAKA_CACHE_DIR") or os.environ.get("XDG_CACHE_HOME")
CACHE_DIR = Path(_CACHE_ROOT or (Path.home() / ".cache")) / "misaka-intake-bot"
SIG_FILE = CACHE_DIR / "sigs.json"
CORPUS_FILE = CACHE_DIR / "corpus.json"
DEFAULT_HIT_SIM = 0.45  # v1.0：命中确认阈值（title 重叠 ×2 / body 重叠，取 max）。0.30 曾致 38% 跨语言假阳性（#1529 反馈）
HIGH_BAR_SIM = 0.55    # 无技术栈特征（泛化错误）时要求更高相似度才给 hit
PRECHECK_LIMIT = 5


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
         "with", "after", "when", "while", "from", "this", "not", "found",
         "module", "modules", "cannot", "unable", "could", "undefined", "null",
         "command", "install", "package", "line", "file", "files", "unexpected",
         "expected", "during", "processing"}

# 技术栈/语言特征词（用于命中门：避免"module not found"这类泛化词跨语言误配）
_STACK_HINTS = {
    "python": {"python", "pip", "venv", "uv", "pytest", "import", "module", "numpy", "pandas", "django", "flask", "werkzeug", "tiktoken", "asyncio", "traceback", "syntaxerror", "indentation", "none"},
    "node": {"node", "npm", "npx", "js", "javascript", "typescript", "ts", "react", "webpack", "metro", "babel", "pnpm", "yarn", "angular", "vue", "expo"},
    "rust": {"rust", "cargo", "borrow", "lifetime", "unwrap", "crate", "rustc"},
    "go": {"golang", "go build", "go test", "go: ", "goroutine", "gopath"},
    "java": {"java", "gradle", "maven", "jvm", "kotlin", "android", "spring", "classnotfound"},
    "c": {"c++", "cpp", "gcc", "clang", "cmake", "linker", "compiler", "cxx", "segfault", "makefile"},
    "swift": {"swift", "xcode", "unwrap", "swiftui"},
    "dart": {"dart", "flutter", "null safety"},
    "php": {"php", "composer", "laravel"},
    "lua": {"lua", "luarocks"},
    "julia": {"julia", "pkg"},
    "r": {"r ", "rlang", "rscript"},
    "ruby": {"ruby", "gem", "bundler", "rails"},
    "shell": {"bash", "sh ", "zsh", "shell", "chmod", "permission denied", "env:", "exit code", "make["},
    "docker": {"docker", "container", "image", "dockerfile", "compose", "registry", "kubectl", "pod"},
    "k8s": {"kubernetes", "k8s", "namespace", "helm", "deployment", "pod"},
    "terraform": {"terraform", "tfstate", "plan", "apply"},
    "aws": {"aws", "s3", "ec2", "lambda", "cloudfront", "iam", "secret access key"},
    "cloudflare": {"cloudflare", "workers", "cf-", "kv", "d1"},
    "git": {"git", "github", "merge", "rebase", "pull", "push", "credential helper", "sign-off", "signed-off"},
    "db": {"postgres", "postgresql", "mysql", "mongodb", "redis", "sql", "connection pool"},
    "web": {"http", "https", "url", "curl", "ssl", "tls", "proxy", "403", "404", "429", "500", "502", "504", "rate limit", "timeout", "dns"},
    "network": {"socket", "connection refused", "econnreset", "timeout", "dns", "proxy", "tls", "ssl"},
    "windows": {"windows", "wsl", "winerror", "cmd.exe", "powershell", "pycharm"},
    "fanuc": {"fanuc", "robot", "karel", "tp ", "r-2000", "r-30ia", "alarm", "welding"},
    "feishu": {"feishu", "lark", "webhook", "bot"},
}

_NOISE_RE = re.compile(
    r"^https?://\S+|^[\w./-]+\.(json|yaml|yml|log|txt)$|^\[?[0-9a-f-]{8,}\]?$"
    r"|^[\[{].{0,80}[}\]]$|^[\w@.:/\\-]{0,40}$|^[^a-zA-Z\u4e00-\u9fff]{2,}$",
    re.I,
)


def _detect_stack(text: str) -> set[str]:
    """返回 text 命中的技术栈族。"""
    low = (text or "").lower()
    hits = set()
    for family, words in _STACK_HINTS.items():
        if any(w in low for w in words):
            hits.add(family)
    return hits


def _doc_stack(doc: dict) -> set[str]:
    """课程侧技术栈：title + tags + domain 联合判定。"""
    hay = " ".join([
        doc.get("title") or "",
        doc.get("domain") or "",
        " ".join(doc.get("tags") or []),
    ])
    return _detect_stack(hay)


def _is_noise(error: str) -> bool:
    """纯 URL / 路径 / JSON 片段 / 符号串 / 无实义词 → 噪音（不 intake、不 hit）。"""
    err = (error or "").strip()
    if len(err) < 10:
        return True
    letters = re.sub(r"[^a-zA-Z\u4e00-\u9fff]", "", err)
    if len(letters) < 4:
        return True
    return bool(_NOISE_RE.match(err))


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


def precheck(error: str, sim_threshold: float, corpus: list | None = None) -> dict | None:
    """全量语料本地打分（title 重叠 ×2 / body 重叠）。命中返回最佳课程 dict；无命中返回 None。

    v1.0 结构性防假阳性（#1529 反馈：0.30 阈值跨语言 FP 38%）：
    - 查询含明确技术栈特征 → 最佳课程必须同栈（跨栈即使词面相似也不 hit）
    - 查询无技术栈特征（泛化错误）→ 需过 HIGH_BAR_SIM 才 hit
    `corpus` 供测试注入固定语料；缺省走远端（_load_corpus）。
    """
    q = _tokens(error)
    if not q or _is_noise(error):
        return None
    docs = _load_corpus() if corpus is None else corpus
    q_stack = _detect_stack(error)
    bar = sim_threshold if q_stack else max(sim_threshold, HIGH_BAR_SIM)
    best, best_score = None, 0.0
    for doc in docs:
        title = _tokens(doc.get("title") or "")
        body = _tokens((doc.get("description") or "")[:500])
        score = max(_sim(q, title) * 2.0, _sim(q, body))
        if score <= best_score:
            continue
        # 技术栈一致性：query 有栈特征时必须与课程共享至少一族
        if q_stack and not (q_stack & _doc_stack(doc)):
            continue
        best, best_score = doc, score
    if best and best_score >= bar:
        best["_sim"] = best_score
        best["_suggest_only"] = True  # v1.0：命中仅为建议，供人工核对
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
    if _is_noise(err):
        return False, "纯噪音（URL/JSON/路径/符号串），无失败语义"
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
           sim_threshold: float, force: bool, offline: bool = False,
           corpus: list | None = None) -> dict:
    sig = fingerprint(error)
    sigs = load_sigs()
    hit = None if offline else precheck(error, sim_threshold, corpus=corpus)
    if hit:
        return {"decision": "hit", "fingerprint": sig,
                "suggest_only": True,  # v1.0：命中仅为建议，请人工核对后再采用
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
            print(f"💡 命中课程（sim={l['sim']}，仅供参考）：{l['title']}\n   {l['url']}")
            print("   ⚠️ suggest-only：AI 建议，请人工核对后再采用。已存在课程 → 不 intake；")
            print("   按该课程修复后再试仍失败，请补 what_tried 重跑。")
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
