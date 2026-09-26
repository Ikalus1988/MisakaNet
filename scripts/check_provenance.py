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
import ipaddress
import json
import os
import pathlib
import re
import socket
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


def _host_of(url: str) -> str:
    """The hostname (or bracketed IPv6 literal) of a URL, lower-cased, without the port."""
    if not url or not isinstance(url, str):
        return ""
    rest = re.sub(r"^https?://", "", url, flags=re.I)
    rest = rest.split("/")[0].split("?")[0]
    if rest.startswith("["):                       # [fe80::1]:8080
        close_bracket = rest.find("]")
        if close_bracket != -1:
            return rest[1:close_bracket].lower()
        return rest[1:].lower()
    return rest.split(":")[0].lower()


def is_non_public_host(host: str) -> bool:
    """True when the host is not a public internet address.

    This is an SSRF guard, not a stylistic choice: a pull request can put any URL in a lesson's
    frontmatter, and CI would fetch it. The first version only exempted RFC1918 literals, so
    `http://169.254.169.254/latest/meta-data/` (cloud metadata), CGNAT (`100.64.0.0/10`),
    `0.0.0.0`, and every IPv6 literal were all "checked" — i.e. requested from inside the runner.
    Found by an open-code-review scan (2026-09-16).
    """
    if not host or not isinstance(host, str):
        return True
    host = host.strip("[]").lower()
    if not host or host in EXEMPT_HOSTS or host.endswith((".local", ".internal", ".lan")):
        return True
    if host in ("0.0.0.0", "::", "::1"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False          # a name: resolution is checked separately, see resolves_non_public()
    return not address.is_global


def resolves_non_public(host: str) -> bool:
    """True when a hostname resolves to a non-public address (DNS-based SSRF).

    A name that resolves to 169.254.169.254 is the same threat as writing the literal, so the
    gate refuses to follow it. Unresolvable names are *not* non-public — they are handled as
    `unknown`, because a lesson may legitimately cite a site that is down.
    """
    if not host or not isinstance(host, str):
        return False
    host = host.strip("[]").strip()
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        address = info[4][0].split("%")[0]
        try:
            ip = ipaddress.ip_address(address)
            # 198.18.0.0/15 is used by developer transparent / fake-IP proxies (Clash, Surge)
            # for DNS interception; it is not a private SSRF destination.
            if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("198.18.0.0/15"):
                continue
            if not ip.is_global:
                return True
        except ValueError:
            continue
    return False

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
    if not text or not isinstance(text, str) or not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end != -1 else ""


def _json_citations(fm: str) -> list[str] | None:
    """Citations from a JSON-style frontmatter block, or None when it is not JSON.

    Sixty-four lessons use JSON frontmatter. The line-oriented parser reads the pretty-printed
    form, but a single-line block (`{"source": "https://…"}`) has no line to key off — so a
    contributor could hide a source from the gate by minifying it. Returns None (not []) when the
    block simply is not JSON, so the caller keeps the YAML path for malformed-but-close blocks.
    """
    if not fm or not isinstance(fm, str):
        return None
    text = fm.strip()
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except Exception:
        return None
    found: list[str] = []

    def walk(node, key=""):
        if isinstance(node, dict):
            for k, value in node.items():
                walk(value, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key)
        elif isinstance(node, str) and key in CITATION_KEYS:
            for url in re.findall(r"https?://[^\s\"'\]\),]+", node):
                url = url.rstrip(".,;>")
                if url not in found:
                    found.append(url)

    walk(data)
    return found


def citations(fm: str) -> list[str]:
    """Every URL cited in the frontmatter, in order, de-duplicated.

    Handles the three shapes this corpus actually uses: `source: "https://..."`, block lists
    (`evidence_refs:` followed by `  - "https://..."`), and **JSON-style frontmatter**
    (`"source": "https://..."`, which 64 lessons use). The last one matters: a quoted key was
    invisible to the first version of this regex, so a fabricated source could have been hidden
    inside a JSON block and the gate would have reported nothing at all. Found by the red-team
    probe, not by review.
    """
    if not fm or not isinstance(fm, str):
        return []
    json_urls = _json_citations(fm)
    if json_urls is not None:
        return json_urls
    found: list[str] = []
    parent = ""                     # the key a list item or block scalar belongs to
    for line in fm.splitlines():
        stripped = line.strip()
        if not stripped:
            parent = ""
            continue
        match = re.match(r'\s*"?([A-Za-z_]+)"?\s*:\s*(.*)$', line)
        if match and match.group(1).lower() in ("http", "https", "ftp", "file") \
                and match.group(2).startswith("/"):
            # A bare URL on its own line (`https://…`, e.g. a block scalar) is not `key: value`;
            # the key pattern would otherwise read the scheme as the key and drop the citation.
            match = None
        if match:
            key, value = match.group(1), match.group(2)
            parent = key
            if key == LEVEL_KEY or (key not in CITATION_KEYS and value not in ("", "|", ">")):
                continue
        elif stripped.startswith("-"):
            # A list item is only a citation when the list belongs to a citation key: a URL in
            # `tags:` or `authors:` is metadata, not a source (open-code-review finding 14).
            if parent not in CITATION_KEYS:
                continue
            value = stripped.lstrip("-").strip()
        elif parent in CITATION_KEYS and line[:1] in (" ", "\t"):
            value = stripped      # block scalar (`source: |` then an indented URL) — finding 15
        else:
            continue
        for url in re.findall(r"https?://[^\s\"'\]\),]+", value):
            url = url.rstrip(".,;>")
            if url not in found:
                found.append(url)
    return found


def evidence_level(fm: str) -> str:
    if not fm or not isinstance(fm, str):
        return ""
    text = fm.strip()
    if text.startswith("{"):
        try:
            value = json.loads(text).get(LEVEL_KEY)
            if isinstance(value, str):
                return value.upper()
        except Exception:
            pass                     # fall through to the line-oriented read
    match = re.search(rf'^\s*"?{LEVEL_KEY}"?\s*:\s*["\']?([A-Za-z0-9]+)', fm, re.M)
    return match.group(1).upper() if match else ""


def classify(url: str) -> str:
    """`exempt` | `placeholder` — decided without any network call."""
    if not url or not isinstance(url, str):
        return "exempt"
    if is_non_public_host(_host_of(url)):
        return "exempt"
    if any(p.search(url) for p in PLACEHOLDER_PATTERNS):
        return "placeholder"
    return "check"


def github_api_url(url: str) -> str | None:
    """Map a github.com URL onto the REST resource that proves it exists."""
    if not url or not isinstance(url, str):
        return None
    match = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)(?:/(?:issues|pull)/(\d+))?", url, re.I)
    if not match:
        return None
    owner, repo, number = match.groups()
    repo = repo.removesuffix(".git")
    path = f"/repos/{owner}/{repo}"
    if number:
        path += f"/issues/{number}"
    return "https://api.github.com" + path


def auth_headers(url: str, token: str) -> dict:
    """Attach the CI token to the GitHub API only — never to a URL a lesson cites.

    The first version passed the token to every fetch, so any URL in any lesson frontmatter
    (i.e. anything a contributor can write) received the workflow's `GITHUB_TOKEN`. Found by an
    open-code-review scan (2026-09-16).
    """
    if not url or not isinstance(url, str) or not token:
        return {}
    if _host_of(url) == "api.github.com":
        return {"Authorization": f"Bearer {token}"}
    return {}


class _PublicRedirectsOnly(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but never into a non-public address.

    `urlopen` follows 3xx by default, so `https://public.example/redir` could 302 the CI runner
    at `http://169.254.169.254/...` and the previous behaviour would have gone there, bearer
    token included. Same scan.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        host = _host_of(newurl)
        if is_non_public_host(host) or resolves_non_public(host):
            raise urllib.error.HTTPError(newurl, code, "refusing redirect to a non-public address",
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PublicRedirectsOnly)


def _http(url: str, token: str = "") -> tuple[int | str, str]:
    headers = {"User-Agent": "misakanet-provenance-gate", **auth_headers(url, token)}
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers=headers)
        try:
            with _OPENER.open(request, timeout=TIMEOUT) as response:
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
    if not url or not isinstance(url, str):
        return "exempt", "empty or invalid url"
    verdict = classify(url)
    if verdict in ("exempt", "placeholder"):
        return verdict, ""
    if fetcher is None:
        return "unknown", "offline"
    host = _host_of(url)
    if resolves_non_public(host):
        return "exempt", "resolves to a non-public address"
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
    if not isinstance(data, dict):
        return {"known_dead": [], "exempt_urls": []}
    data.setdefault("known_dead", [])
    data.setdefault("exempt_urls", [])
    return data


def rel_to_repo(path: pathlib.Path) -> str:
    """Repo-relative when possible; a file from outside the repo (tests, ad-hoc checks) as-is."""
    if path is None:
        return ""
    if not isinstance(path, pathlib.Path):
        try:
            path = pathlib.Path(path)
        except Exception:
            return str(path)
    try:
        return str(path.resolve().relative_to(REPO))
    except (ValueError, Exception):
        return str(path)


def scan(paths: list[pathlib.Path], fetcher=None) -> list[dict]:
    rows: list[dict] = []
    if not paths:
        return rows
    for path in paths:
        if path is None:
            continue
        if not isinstance(path, pathlib.Path):
            try:
                path = pathlib.Path(path)
            except Exception:
                continue
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
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
    baseline = baseline or {}
    strict_new = strict_new or set()
    exempt = set(baseline.get("exempt_urls") or [])
    known_dead = {entry["url"] for entry in baseline.get("known_dead") or [] if isinstance(entry, dict) and "url" in entry}
    failures: list[str] = []
    advisories: list[str] = []
    per_lesson: dict[str, dict] = {}
    if not rows:
        return failures, advisories
    for row in rows:
        if not isinstance(row, dict) or "lesson" not in row or "status" not in row:
            continue
        bucket = per_lesson.setdefault(row["lesson"], {"resolvable": 0, "dead": [], "placeholder": []})
        url = row.get("url", "")
        if row["status"] == "ok":
            bucket["resolvable"] += 1
        elif row["status"] == "dead" and url not in known_dead and url not in exempt:
            bucket["dead"].append(url)
            failures.append(f"{row['lesson']}: source does not resolve — {url} ({row.get('detail', '')})")
        elif row["status"] == "placeholder":
            bucket["placeholder"].append(url)
            failures.append(f"{row['lesson']}: source is a placeholder, not a citation — {url}")
    for lesson, bucket in sorted(per_lesson.items()):
        if lesson not in strict_new:
            continue
        level = next((r.get("evidence_level", "") for r in rows if isinstance(r, dict) and r.get("lesson") == lesson), "")
        if level in HIGH_LEVELS and bucket["resolvable"] == 0 and not bucket["dead"]:
            advisories.append(
                f"{lesson}: claims evidence_level {level} but cites no resolvable source "
                "- cite where it was reproduced, or lower the level / say it is unreproduced")
    return failures, advisories


def lesson_files(explicit: list[str]) -> list[pathlib.Path]:
    if explicit:
        resolved: list[pathlib.Path] = []
        for p in explicit:
            if not p:
                continue
            target = pathlib.Path(p) if pathlib.Path(p).is_absolute() else REPO / p
            if target.is_dir():
                resolved.extend(sorted(target.rglob("*.md")))
            else:
                resolved.append(target)
        return resolved
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
