#!/usr/bin/env python3
"""Generate tests/benchmarks/intake_benchmark.json — deterministic offline
benchmark for intake_bot decision quality. See docs/benchmarks/intake-bot-v1.0.md.
Regenerate: python3 scripts/gen_intake_benchmark.py"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"
OUT = REPO / "tests" / "benchmarks" / "intake_benchmark.json"
FRONT = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse(path):
    t = path.read_text(encoding="utf-8", errors="ignore")
    m = FRONT.match(t)
    fm = {}
    if m:
        raw = m.group(1)
        try:
            fm = json.loads(raw)
        except Exception:
            for kv in re.findall(r"^([\w-]+):\s*(.+)$", raw, re.M):
                fm[kv[0]] = kv[1].strip().strip("'\"")
    body = t[m.end():] if m else t
    pm = re.search(r"##\s*(?:Problem|问题)\s*\n(.*?)(?:\n##|\Z)", body, re.S | re.I)
    prob = re.sub(r"\s+", " ", (pm.group(1) if pm else body)[:200]).strip()
    return fm, prob


def pick_corpus(parsed):
    by_domain = {}
    for fm, prob in parsed:
        dom = str(fm.get("domain") or "general").strip().lower()
        by_domain.setdefault(dom, []).append((fm, prob))
    picked = []
    for dom in sorted(by_domain, key=lambda d: -len(by_domain[d])):
        for fm, prob in by_domain[dom][:4]:
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [x.strip() for x in tags.split(",") if x.strip()]
            picked.append({"id": str(fm.get("id") or ""), "title": str(fm.get("title") or ""),
                           "domain": str(fm.get("domain") or ""), "tags": tags,
                           "description": prob})
        if len(picked) >= 36:
            break
    return picked[:36]


def main():
    parsed = []
    for sub in ("core", "contrib", "en"):
        d = LESSONS / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name in ("README.md", "TEMPLATE.md", "LESSON_QUALITY_SCORING.md"):
                continue
            fm, prob = parse(f)
            fm["id"] = f.stem
            parsed.append((fm, prob))
    corpus = pick_corpus(parsed)
    if len(corpus) < 24:
        print(f"only {len(corpus)} lessons picked"); return 2
    REAL_PREFER = ["corporate-proxy-curl-timeout", "git-credential-helper-gh-path-mismatch",
                   "pip-install-proxy-timeout", "python-smtplib-ssl-certificate-verify-failed-fix"]
    existing = {c["id"] for c in corpus}
    for fm, prob in parsed:
        if fm.get("id") in REAL_PREFER and fm["id"] not in existing:
            tags = fm.get("tags") or []
            if isinstance(tags, str):
                tags = [x.strip() for x in tags.split(",") if x.strip()]
            corpus.append({"id": fm["id"], "title": str(fm.get("title") or ""),
                           "domain": str(fm.get("domain") or ""), "tags": tags, "description": prob})
            existing.add(fm["id"])

    hit = []
    for doc in corpus:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", doc["title"])
        core = " ".join(words[:10]) if len(words) > 2 else doc["id"].replace("-", " ")
        err = f"{doc['domain'] or 'error'}: {core} failed — {doc['description'][:120]}"
        hit.append({"id": f"hit-{doc['id'][:44]}", "kind": "hit", "expect": [doc["id"]],
                    "error": err, "source_lesson": doc["id"]})

    real_forms = {
        "corporate-proxy-curl-timeout": "curl: (35) SSL connect error behind corporate proxy — read timeout when fetching over the proxy",
        "git-credential-helper-gh-path-mismatch": "git credential helper 401 credential lookup failed github helper path mismatch",
        "pip-install-proxy-timeout": "pip install ReadTimeoutError behind corporate proxy while reading from pypi",
        "python-smtplib-ssl-certificate-verify-failed-fix": "ssl.SSLCertVerificationError certificate verify failed while sending mail via smtplib",
    }
    for lid, err in real_forms.items():
        if lid in existing:
            hit.append({"id": f"real-{lid[:40]}", "kind": "hit", "expect": [lid],
                        "error": err, "source_lesson": lid})

    nohit_list = [
        "error[E0308]: mismatched types in borrow checker rust cargo build",
        "FAILURE: Build failed with an exception. gradle task :app:assemble",
        "Swift fatal error: unexpectedly found nil while unwrapping an Optional",
        "linker command failed with exit code 1 undefined symbols clang c++",
        "Error from server: namespaces not found kubernetes kubectl get ns",
        "error: cannot find module 'foo' lua require luarocks",
        "ERROR: LoadError: could not load package Foo julia pkg add",
        "MongoServerError: Authentication failed mongodb credentials",
        "Terraform init failed backend state lock tfstate",
        "Error: something went wrong with the database connection pool",
        "npm ERR! code ELIFECYCLE in unrelated js project webpack bundle",
    ]
    nohit = [{"id": f"nohit-{i:02d}", "kind": "no-hit", "error": e}
             for i, e in enumerate(nohit_list)]
    ig_list = ["https://example.com/foo", '{"error":"boom","code":500}', "it broke",
               "0x7f8a2b3c4d5e", "!!! ???", "asdf", "[Errno 2]", "429"]
    ignore = [{"id": f"ignore-{i:02d}", "kind": "ignore", "error": e}
              for i, e in enumerate(ig_list)]

    out = {"_meta": {
        "purpose": "intake_bot decision benchmark (offline, deterministic)",
        "generator": "scripts/gen_intake_benchmark.py",
        "note": "hit samples are lesson-derived — benchmarks decision logic, not retrieval (#1527)"},
        "corpus": corpus, "samples": hit + nohit + ignore}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = {}
    for s in out["samples"]:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(f"wrote {OUT}  corpus={len(corpus)}  samples={kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
