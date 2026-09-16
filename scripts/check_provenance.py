#!/usr/bin/env python3
"""Check that the sources a lesson cites actually exist.

Why this exists: `scripts/lesson_gate.py` checks structure, DCO checks signatures and
`scripts/injection_scan.py` checks for prompt-injection shapes — none of them can tell
whether a `source:` URL is real. On 2026-09-16 four lesson PRs (#1713–#1716) passed
24/24 checks while every one of them cited
`https://github.com/modelcontextprotocol/mcp-memory-service/issues/1652`, a repository
that returns 404. In a corpus whose value proposition is *verifiable* failure memory,
an invented source is worse than an absent one: it looks checkable and is not.

Two rule tiers, because legacy debt must not block every future PR:

  tier 1 (always fails)   a placeholder URL, or a URL that is confirmed dead (404/410)
                          and is not recorded in the baseline
  tier 2 (--strict-new)   a lesson that claims `evidence_level: E2`/`E3` while citing no
                          resolvable source at all. Only applied to *newly added* files,
                          the same strict/advisory split the lesson gate uses for
                          structural rules (see .github/workflows/lesson-gate.yml).

Statuses are deliberately conservative: a network failure, a timeout, a rate limit or an
unusual HTTP code is `unknown` and never fails the build — the gate only fails on
evidence, never on the absence of it.

Usage
-----
    python3 scripts/check_provenance.py                 # every lesson
    python3 scripts/check_provenance.py --check         # exit 1 on tier-1 violations
    python3 scripts/check_provenance.py --strict-new lessons/contrib/new-one.md
    python3 scripts/check_provenance.py --list          # per-URL table
    python3 scripts/check_provenance.py --offline       # no network (dev/tests)
    python3 scripts/check_provenance.py --update-baseline   # record current findings

Stdlib only, on purpose: the Python side of this repository has no external runtime
dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

REPO = pathlib.Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"
BASELINE = REPO / "data" / "provenance-baseline.json"
TIMEOUT = 12

# URLs that are illustrative by construction: a lesson about a corporate proxy must be
# able to say `http://172.19.128.1:7890`, and a lesson about a webhook cannot be asked to
# host a real endpoint. These are exempt from resolution, not from being honest.
EXEMPT_HOSTS = {"localhost", "example.com", "example.org", "example.net", "test.invalid"}
EXEMPT_PATTERNS = (
    re.compile(r"^https?://(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)"),
    re.compile(r"^https?://[^/]*\.(local|internal|lan)(:\d+)?(/|$)"),
    re.compile(r"^https?://[^/]*(localhost|127\.0\.0\.1)"),
)

# A URL-shaped thing that cannot be resolved by anyone: `<owner>`, `TODO`, `...`, `/xxx/`,
# or the shouted upper-case placeholders people leave in templates. Keep this list narrow —
# a pattern that matches ordinary URLs turns real links into false failures. `REPO` matched
# case-insensitively, for instance, flagged `https://github.com/gone/repo/issues/3`.
PLACEHOLDER_PATTERNS = (
    re.compile(r"[<>]"),
    re.compile(r"\{[a-z_]+\}", re.I),
    re.compile(r"\b(TODO|FIXME|PLACEHOLDER|YOUR[-_]?ORG|YOUR[-_]?NAME|USERNAME)\b", re.I),
    re.compile(r"\b(OWNER|REPO|ORG)\b"),        # case-sensitive: placeholders are shouted
    re.compile(r"/x{3,}"),
    re.compile(r"\.\.\."),
)

# Frontmatter keys whose values are citations. `evidence_refs` may hold local references
# (`issue:#1553`, `bench:...`) which are not URLs and are simply skipped.
CITATION_KEYS = ("source", "evidence_refs", "provenance", "url", "link")
LEVEL_KEY = "evidence_level"
HIGH_LEVELS = {"E2", "E3"}


def frontmatter(text: str) -> str:
    """The frontmatter block, or '' when the file has none."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def citations(fm: str) -> list[str]:
    """Every URL cited in the frontmatter, in order, de-duplicated.

    Handles both `source: "https://..."` and block-list forms (`evidence_refs:` followed by
    `  - "https://..."`), because the corpus uses both.
    """
    found: list[str] = []
    for line in fm.splitlines():
        stripped = line.strip()
        match = re.match(r"\s*([A-Za-z_]+)\s*:\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2)
            if key == LEVEL_KEY or (key not in CITATION_KEYS and value):
                continue          # an unrelated key with a value; list items carry no key
        elif stripped.startswith("-"):
            value = stripped.lstrip("-").strip()      # a list item under a citation key
        else:
            continue
        for url in re.findall(r"https?://[^\s\"'\]\)>,]+", value):
            url = url.rstrip(".,;")
            if url not in found:
                found.append(url)
    return found


def evidence_level(fm: str) -> str:
    match = re.search(rf"^{LEVEL_KEY}\s*:\s*[\"']?([A-Za-z0-9]+)", fm, re.M)
    return match.group(1).upper() if match else ""


def classify(url: str) -> str:
    """`exempt` | `placeholder` — decided without any network call."""
    if any(p.search(url) for p in EXEMPT_PATTERNS):
        return "exempt"
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0].lower()
    if host in EXEMPT_HOSTS:
        return "exempt"
    if any(p.search(url) for p in PLACEHOLDER_PATTERNS):
        return "placeholder"
    return "check"


def github_api_url(url: str) -> str | None:
    """Map a github.com URL onto the REST resource that proves it exists."""
    match = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)(?:/(?:issues|pull)/(\d+))?", url, re.I)
    if not match:
        return None
    owner, repo, number = match.groups()
    repo = repo.removesuffix(".git")
    path = f"/repos/{owner}/{repo}"
    if number:
        path += f"/issues/{number}"
    return "https://api.github.com" + path


def _http(url: str, token: str = "") -> tuple[int | str, str]:
    headers = {"User-Agent": "misakanet-provenance-gate"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return response.status, ""
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue          # some servers refuse HEAD but answer GET
            return exc.code, ""
        except Exception as exc:   # DNS, TLS, timeout, connection reset
            if method == "HEAD":
                continue
            return "error", type(exc).__name__
    return "error", "unreachable"


def resolve(url: str, fetcher=None) -> tuple[str, str]:
    """Return (status, detail) where status is ok | dead | unknown | exempt | placeholder."""
    verdict = classify(url)
    if verdict in ("exempt", "placeholder"):
        return verdict, ""
    if fetcher is None:
        return "unknown", "offline"
    api = github_api_url(url)
    code, detail = fetcher(api or url, os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "")
    if code in (200, 301, 302, 304):
        return "ok", ""
    if code in (404, 410):
        return "dead", f"HTTP {code}"
    return "unknown", detail or f"HTTP {code}"


def load_baseline() -> dict:
    if not BASELINE.is_file():
        return {"known_dead": [], "exempt_urls": []}
    try:
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:
        return {"known_dead": [], "exempt_urls": []}
    data.setdefault("known_dead", [])
    data.setdefault("exempt_urls", [])
    return data


def rel_to_repo(path: pathlib.Path) -> str:
    """Repo-relative when possible; a file from outside the repo (tests, ad-hoc checks) as-is."""
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def scan(paths: list[pathlib.Path], fetcher=None) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = frontmatter(text)
        if not fm:
            continue
        level = evidence_level(fm)
        rel = rel_to_repo(path)
        cited = citations(fm)
        resolvable = 0
        for url in cited:
            status, detail = resolve(url, fetcher)
            if status == "ok":
                resolvable += 1
            rows.append({"lesson": rel, "url": url, "status": status, "detail": detail,
                         "evidence_level": level})
        if not cited:
            rows.append({"lesson": rel, "url": "", "status": "none", "detail": "",
                         "evidence_level": level})
    return rows


def evaluate(rows: list[dict], baseline: dict, strict_new: set[str]) -> tuple[list[str], list[str]]:
    """Return (failures, advisories)."""
    exempt = set(baseline.get("exempt_urls") or [])
    known_dead = {entry["url"] for entry in baseline.get("known_dead") or [] if "url" in entry}
    failures: list[str] = []
    advisories: list[str] = []
    per_lesson: dict[str, dict] = {}
    for row in rows:
        bucket = per_lesson.setdefault(row["lesson"], {"resolvable": 0, "dead": [], "placeholder": []})
        if row["status"] == "ok":
            bucket["resolvable"] += 1
        elif row["status"] == "dead" and row["url"] not in known_dead and row["url"] not in exempt:
            bucket["dead"].append(row["url"])
            failures.append(f"{row['lesson']}: source does not resolve — {row['url']} ({row['detail']})")
        elif row["status"] == "placeholder":
            bucket["placeholder"].append(row["url"])
            failures.append(f"{row['lesson']}: source is a placeholder, not a citation — {row['url']}")
    for lesson, bucket in sorted(per_lesson.items()):
        if lesson not in strict_new:
            continue
        level = next((r["evidence_level"] for r in rows if r["lesson"] == lesson), "")
        if level in HIGH_LEVELS and bucket["resolvable"] == 0 and not bucket["dead"]:
            advisories.append(
                f"{lesson}: claims evidence_level {level} but cites no resolvable source "
                "- cite where it was reproduced, or lower the level / say it is unreproduced")
    return failures, advisories


def lesson_files(explicit: list[str]) -> list[pathlib.Path]:
    if explicit:
        return [pathlib.Path(p) if pathlib.Path(p).is_absolute() else REPO / p for p in explicit]
    return sorted(LESSONS.rglob("*.md"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="lesson files (default: every lesson)")
    parser.add_argument("--check", action="store_true", help="exit 1 on violations")
    parser.add_argument("--strict-new", nargs="*", default=[], metavar="FILE",
                        help="files added by this change: also enforce tier 2")
    parser.add_argument("--list", action="store_true", help="print every citation and its status")
    parser.add_argument("--offline", action="store_true", help="do not touch the network")
    parser.add_argument("--update-baseline", action="store_true",
                        help="record the current dead URLs in data/provenance-baseline.json")
    args = parser.parse_args(argv)

    fetcher = None if args.offline else _http
    # `--strict-new` takes file paths, and argparse's nargs="*" means it swallows positional
    # arguments too. CI calls it on its own (`--strict-new $ADDED`), so when no positional files
    # were given, the strict-new list *is* the target set — otherwise the CLI silently checks
    # the whole corpus, which is both slow and wrong for a PR-scoped run.
    targets = args.files or args.strict_new
    rows = scan(lesson_files(targets), fetcher)
    baseline = load_baseline()
    strict_new = {rel_to_repo(pathlib.Path(p)) for p in args.strict_new}

    if args.update_baseline:
        dead = sorted({r["url"] for r in rows if r["status"] == "dead"})
        payload = {
            "schema": "misakanet-provenance-baseline/1",
            "note": ("Known-unresolvable sources that must not fail every PR. Keep this list "
                     "short and justified: an entry here means 'we know, and we chose not to "
                     "fix it yet'. Placeholder URLs are never baselined."),
            "known_dead": [{"url": u, "why": "recorded by --update-baseline; say why here"}
                           for u in dead],
            "exempt_urls": baseline.get("exempt_urls") or [],
        }
        BASELINE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"baseline updated: {len(dead)} dead URL(s) recorded -> {BASELINE.relative_to(REPO)}")
        return 0

    if args.list:
        width = max((len(r["url"]) for r in rows), default=0)
        for row in rows:
            level = f" [{row['evidence_level']}]" if row["evidence_level"] else ""
            print(f"  {row['status']:11s} {row['url']:<{width}}  {row['lesson']}{level}"
                  + (f"  ({row['detail']})" if row["detail"] else ""))

    failures, advisories = evaluate(rows, baseline, strict_new)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"\n检查 {len({r['lesson'] for r in rows})} 篇课程，引用 {len([r for r in rows if r['url']])} 条外链："
          + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for note in advisories:
        print(f"  ⚠️  {note}")
    for failure in failures:
        print(f"  ❌ {failure}")

    if not args.check and not args.strict_new:
        return 0
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
