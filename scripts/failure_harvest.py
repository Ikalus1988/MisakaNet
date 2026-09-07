#!/usr/bin/env python3
"""failure_harvest — P0: 失败养料 → 指纹簇 → lesson 骨架草稿（批量、防过窄）。

Review 通过后最小实现（docs/reviews/2026-09-07-intake-lesson-network-vs-ecosystem.md）：
- 借鉴不重造：指纹/聚类语义对齐 Sentry grouping；复用本仓 intake_bot 的
  fingerprint/_detect_stack/_is_noise/_tokens；产出落 lessons/drafts/（与
  fatal-guard 草稿同一生命周期：自动生成 → PR → 维护者审 → 升格 contrib）。
- 防"过窄"：同失败族多变体 → 一篇草稿。聚类键 = 具体异常类名（specific kind）
  或 generic+归一化技术栈；401/fatal/HTTP 码为弱信号，只进 failure_patterns，
  不因措辞差异拆簇（git credential 的 "401" 与 "fatal:" 属同一族）。
- 防"过宽"：specific kind 才按类名聚类；generic 必配技术栈，避免不同栈同并。
- 栈噪声处理：检测前剥 URL（防 https→web 误报）；剔除 "r " 单字符误报
  （"error " 尾字母 r+空格 会命中 intake_bot 的 R 词表，采收场景弃用 R 栈）。
- 草稿带 failure_patterns（类名+弱信号+栈词）→ 为 #1527 签名索引铺路。

用法:
  python3 scripts/failure_harvest.py --demo
  python3 scripts/failure_harvest.py --events events.json [--out lessons/drafts] [--json]
  cat events.json | python3 scripts/failure_harvest.py --json
事件格式: [{"error": "...", "source": "...", "what_tried": "...", "occurred_at": "..."}]
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.intake_bot import _detect_stack, _is_noise, fingerprint as ib_fingerprint  # noqa: E402

DRAFT_DIR = REPO / "lessons" / "drafts"
MIN_OCCURRENCES = 2          # 高频门槛：同簇出现 ≥2 才默认生成草稿
# 类名（可带模块路径）优先；HTTP 状态码 / 裸 4xx/5xx / fatal 为弱信号
_CLASS_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Failure|Fault)")
_HTTP_CODE_RE = re.compile(r"\b(?:HTTP\s*)?(?<!\w)(?:4\d\d|5\d\d)(?!\w)", re.I)
_FATAL_RE = re.compile(r"\bfatal\b", re.I)
_URL_RE = re.compile(r"https?://\S+", re.I)
# intake_bot._STACK_HINTS["r"] = {"r ", ...}：任意 "r"+空格（如 "error "、"for "）都命中，
# 采收聚类里误报率远高于真实 R 语境 → 直接剔除（不动共享词表，避免影响 intake 命中门）。
_STACK_DROPS = {"r"}
STACK_DOMAIN = {
    "python": "python", "node": "node", "git": "git", "web": "web", "network": "network",
    "shell": "shell", "docker": "docker", "k8s": "kubernetes", "aws": "aws",
    "cloudflare": "cloudflare", "db": "database", "fanuc": "fanuc", "feishu": "feishu",
}


def classify(error: str) -> tuple[str, bool, list[str]]:
    """返回 (kind_label, specific, signals)。

    - kind_label：specific=True 时为最内层异常类短名（剥模块路径，如 ReadTimeoutError）；
      specific=False 时为弱信号词（http-401 / fatal）或 generic-failure。
    - specific：以 Error/Exception/Failure/Fault 结尾的类名才可作聚类键；
      401/fatal 语义上可能是同族不同措辞（如 git credential），不可作键。
    - signals：捕获到的全部弱信号（HTTP 码 / fatal），供 failure_patterns。
    """
    err = error or ""
    classes = list(_CLASS_RE.finditer(err))
    if classes:
        raw = classes[-1].group(0)          # 取最后一个（最内层）异常
        return raw.rsplit(".", 1)[-1], True, []
    code = _HTTP_CODE_RE.search(err)
    if code:
        m = code.group(0)
        digits = re.sub(r"\D", "", m)
        return f"http-{digits}", False, [m.strip()]
    if _FATAL_RE.search(err):
        return "fatal", False, ["fatal"]
    return "generic-failure", False, []


def error_kind(error: str) -> str:
    """向后兼容：仅返回 kind_label。"""
    return classify(error)[0]


def norm_stack(text: str) -> tuple[str, ...]:
    """归一化技术栈：剥 URL → 检测 → 剔除弱/误报栈。返回排序 tuple。

    - https://github.com 会命中 web（词表含 http/https）→ 先剥 URL。
    - "r " 词表命中任意 r+空格 → 剔除 r（见 _STACK_DROPS）。
    """
    cleaned = _URL_RE.sub("", text or "")
    hits = _detect_stack(cleaned)
    hits -= _STACK_DROPS
    return tuple(sorted(hits))


def norm_variant(error: str) -> str:
    return re.sub(r"\s+", " ", (error or "").strip())[:200]


def cluster_key(stack: tuple, kind: str, specific: bool) -> str:
    """聚类键：specific kind → 仅 kind（同族措辞/栈差异不拆簇）；
    generic → generic + 归一栈（栈承担区分，防不同栈并入同簇）。"""
    if specific:
        return f"K:{kind}"
    return f"G:generic|{','.join(stack)}"


def safe_filename(cid: str) -> str:
    """cid → 跨平台安全文件名（去掉 : | 等文件系统不友好字符）。"""
    safe = re.sub(r"[^A-Za-z0-9]+", "-", cid).strip("-")
    return safe or "cluster"


def build_draft(cluster: dict) -> str:
    """生成 lesson 骨架草稿（合并多措辞变体 → 泛化；签名 → failure_patterns）。"""
    now = datetime.now(timezone.utc)
    stack = cluster["stack"]
    kind = cluster["kind"]
    signals = cluster.get("signals", [])
    top = cluster["top_error"]
    slug_kind = re.sub(r"[^A-Za-z0-9]+", "-", kind)[:40].lower()
    slug = f"harvest-{now.strftime('%Y%m%d')}-{cluster['cid']}-{slug_kind}"
    domain = STACK_DOMAIN.get(stack[0] if stack else "", "general")
    tags = ["draft", "auto-generated", "failure-harvest"]
    tags += list(stack)[:3]
    tags += [kind[:30]] if len(kind) <= 30 else []
    patterns = [kind] + signals + list(stack)[:3]
    fm = {
        "title": f"Harvest: {kind} ({', '.join(stack) or 'general'})",
        "domain": domain,
        "tags": tags,
        "status": "draft",
        "source": "failure-harvest",
        "harvest_ref": cluster["cid"],
        "failure_patterns": patterns,
        "created": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_level": "E0",  # draft 未验证；升格前须补真实证据
    }
    lines = ["---", json.dumps(fm, ensure_ascii=False, indent=2), "---", "", "## Problem", "",
             f"同一失败族 `{kind}` 在 {cluster['occurrences']} 次事件中出现"
             f"（{len(cluster['variants'])} 种措辞变体）。代表性报错：", "",
             "```text", top[:300], "```", ""]
    if len(cluster["variants"]) > 1:
        lines += ["变体（防过窄：本课应覆盖族内所有形态）：", ""]
        for v in cluster["variants"][:5]:
            lines += [f"- `{v[:150]}`", ""]
    if cluster.get("sources"):
        lines += ["来源计数：", ""]
        for src, n in sorted(cluster["sources"].items(), key=lambda x: -x[1])[:8]:
            lines += [f"- {src}: {n}", ""]
    tried = cluster.get("what_tried", [])
    if tried:
        lines += ["## What was tried（合并去重）", ""]
        for t in tried[:5]:
            lines += [f"- {t[:200]}", ""]
    lines += ["## 待补全（草稿生命周期）", "",
              "- [ ] Root cause 归因", "- [ ] 可验证 Solution", "- [ ] 人工/实证 Verification 后升格 lessons/contrib/（通过 lesson_gate）", ""]
    return "\n".join(lines)


def harvest(events: list[dict], out_dir: Path, min_occ: int) -> dict:
    """events → 簇 → 草稿。返回摘要。"""
    cleaned = 0
    clusters: dict[str, dict] = {}
    for ev in events:
        err = (ev.get("error") or "").strip()
        if not err or _is_noise(err):
            cleaned += 1
            continue
        fp = ib_fingerprint(err)
        kind, specific, signals = classify(err)
        stack = norm_stack(err)
        cid = cluster_key(stack, kind, specific)
        c = clusters.setdefault(cid, {"cid": cid, "stack": stack, "kind": kind, "specific": specific,
                                      "signals": [], "fingerprints": set(), "variants": [],
                                      "sources": {}, "what_tried": []})
        c["signals"] = sorted(set(c["signals"]) | set(signals))
        c["fingerprints"].add(fp)
        c["occurrences"] = c.get("occurrences", 0) + 1
        v = norm_variant(err)
        if v not in c["variants"]:
            c["variants"].append(v)
        src = ev.get("source") or "unknown"
        c["sources"][src] = c["sources"].get(src, 0) + 1
        wt = (ev.get("what_tried") or "").strip()
        if wt and wt not in c["what_tried"]:
            c["what_tried"].append(wt)

    written, skipped = [], []
    for c in clusters.values():
        c["variants"] = c["variants"][:10]
        c["top_error"] = c["variants"][0] if c["variants"] else ""
        # 只按频次门槛写；what_tried 只是草稿内容，不豁免 occ=1（防噪音草稿）。
        if c["occurrences"] >= min_occ:
            try:
                out_dir.mkdir(parents=True, exist_ok=True)
                p = out_dir / f"{safe_filename(c['cid'])}.md"
                p.write_text(build_draft(c), encoding="utf-8")
                written.append({"cid": c["cid"], "kind": c["kind"],
                                "stack": list(c["stack"]), "occurrences": c["occurrences"],
                                "file": str(p)})
            except OSError as e:
                skipped.append({"cid": c["cid"], "reason": f"write failed: {e}"})
        else:
            skipped.append({"cid": c["cid"], "kind": c["kind"],
                            "reason": f"low signal (occ={c['occurrences']} < {min_occ})"})
    return {"events": len(events), "cleaned_noise": cleaned,
            "clusters": len(clusters), "drafts": written, "skipped": skipped}


def demo() -> int:
    events = []
    # 同族多变体（防过窄：应聚成一簇生成一篇草稿）
    pip_variants = [
        "pip install ReadTimeoutError behind corporate proxy while reading from pypi",
        "ERROR: Could not install packages due to an OSError ReadTimeoutError proxy pypi pip",
        "pip._vendor.urllib3.exceptions.ReadTimeoutError: HTTPSConnectionPool proxy timeout pip",
    ]
    git_variants = [
        "git credential helper 401 credential lookup failed github helper path mismatch",
        "fatal: could not read Username for 'https://github.com': credential helper misconfigured git",
    ]
    cf_variants = [
        "ReferenceError: env.MISAKANET_KV is undefined cloudflare worker kv binding",
        "ReferenceError: KV namespace binding missing in cloudflare workers env",
    ]
    for e in pip_variants:
        events.append({"error": e, "source": "pilot-a"})
    for e in git_variants:
        events.append({"error": e, "source": "pilot-b", "what_tried": "checked credential.helper path"})
    for e in cf_variants:
        events.append({"error": e, "source": "pilot-a"})
    # 噪音 + 弱信号（应被跳过）
    events.append({"error": "https://example.com/foo", "source": "pilot-a"})
    events.append({"error": "it broke", "source": "pilot-b"})
    events.append({"error": "error[E0308] borrow checker rust cargo", "source": "pilot-c"})
    summary = harvest(events, DRAFT_DIR, MIN_OCCURRENCES)
    print(json.dumps(summary, ensure_ascii=False, indent=1)[:2000])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", help="events JSON 文件")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=str(DRAFT_DIR))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-occ", type=int, default=MIN_OCCURRENCES)
    a = ap.parse_args()
    if a.demo:
        return demo()
    if a.events:
        events = json.loads(Path(a.events).read_text(encoding="utf-8"))
    elif not sys.stdin.isatty():
        events = json.load(sys.stdin)
    else:
        print("need --events / --demo / stdin"); return 2
    summary = harvest(events, Path(a.out), a.min_occ)
    if a.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
