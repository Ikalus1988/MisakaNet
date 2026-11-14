#!/usr/bin/env python3
"""Tell IndexNow about the pages a push to `docs/` added, changed, renamed or deleted.

Why this exists (2026-11-15)
---------------------------
`https://misakanet.org` is static assets served out of `docs/`, so a generated lesson page is live
seconds after the push that writes it and unknown to a search engine until its next crawl. Google
Search Console was verified on 2026-11-15; Bing has never been verified and sent 26 views in the
previous 14 days. IndexNow is the cheap half of that gap: one POST names the URLs, the receiving
engine shares them with the other participating engines (Bing, Yandex, Naver), and the crawl moves
from "next week" to "queued now". The protocol's own documentation is the source for the request
shape and the 10,000-URL limit: https://www.indexnow.org/documentation.

The URL shapes are measured against the live site (2026-11-15), never guessed — `/index.html`
answers 307 to `/`, `/lessons/<slug>` answers 307 to the slash form, and `/start.html` is the file
whose page is served at `/start`:

* `docs/index.html`                 -> `https://misakanet.org/`
* `docs/lessons/<slug>/index.html` -> `https://misakanet.org/lessons/<slug>/`
* `docs/<name>.html`               -> `https://misakanet.org/<name>`
* `docs/<path>.md`                 -> `https://misakanet.org/<path>` (served verbatim, as the
  sitemap's own `troubleshooting.md`/`skill.md` entries confirm)

`docs/googled7bffcd986dade3f.html` is a Search Console verification token, not a document, and the
`.html` rule above would have turned it into `/googled7bffcd986dade3f` — a URL that 404s. A `.html`
file with no document marker is therefore not a page (see `is_html_document`).

Where the list comes from
-------------------------
The push range (`--before`..`--after`) is preferred: it names exactly the pages this push touched.
The full `docs/sitemap.xml` is the fallback, and is used only when the range cannot answer — a
manual run has no `before`, a force push can carry the all-zero SHA, and a shallow checkout may not
contain `before` at all. The fallback is not the normal path: on a daily corpus push it would submit
950+ URLs that did not change.

Exit codes
----------
`0` — the submission was attempted, whatever the endpoint answered. A failed POST is logged (and
annotated as a warning) but does not fail the run: this workflow must never be the reason a deploy
looks stuck.
`2` — the submission was **never attempted**: no key file, an unreadable or mismatched key, or an
empty URL list. This case is deliberately loud, because the alternative is a pipeline that looks
alive in the Actions list and has not sent anything for months.

`--wait-for-key` is the deploy race, not a protocol requirement. `docs/` ships through Cloudflare
Workers Builds, which is asynchronous (around 45 seconds, `docs/agents/repo-operations.md`), so the
push that introduces this file can be submitted before `https://misakanet.org/<key>.txt` answers.
The option polls the keyLocation first and only warns when it never comes up: a submission whose
key the engine has not fetched yet is the endpoint's 202 case, not a reason to stay silent.

Usage
-----
    python3 scripts/indexnow_submit.py --before <sha> --after <sha>
    python3 scripts/indexnow_submit.py --after <sha>        # no history: the sitemap's full set
    python3 scripts/indexnow_submit.py --dry-run            # print, never POST
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Iterator

REPO = Path(__file__).resolve().parent.parent

SITE = "https://misakanet.org"
HOST = "misakanet.org"
ENDPOINT = "https://api.indexnow.org/indexnow"
SITEMAP = "docs/sitemap.xml"
DOCS = "docs"

# The protocol allows up to 10,000 URLs per POST and asks that each be URL-escaped (RFC 3986).
MAX_URLS_PER_REQUEST = 10_000
TIMEOUT_SECONDS = 30
USER_AGENT = "MisakaNet-IndexNow/1.0"

# The key file is `<32 lowercase hex>.txt`; the same pattern keeps `docs/llms.txt` out of discovery.
KEY_RE = re.compile(r"^[0-9a-f]{32}$")

#: Extensions that are served as a page. Everything else under `docs/` is an asset, site
#: configuration (`_headers`, `_redirects`), machine data (`data/**`, `sitemap.xml`) or a token.
PAGE_SUFFIXES = frozenset({".html", ".md"})

SITEMAP_LOC = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"

Log = Callable[[str], None]


class ConfigError(RuntimeError):
    """A configuration problem that means the submission was never attempted."""


# ── the key ─────────────────────────────────────────────────────────────────────────────────────

def discover_key_file(root: Path = REPO) -> Path:
    """The one `docs/<32-hex>.txt`, found by pattern rather than named a second time."""
    candidates = sorted(p for p in (root / DOCS).glob("*.txt") if KEY_RE.fullmatch(p.stem))
    if len(candidates) != 1:
        names = ", ".join(p.name for p in candidates) or "none"
        raise ConfigError(
            f"expected exactly one IndexNow key file (docs/<32 lowercase hex>.txt), found {names}")
    return candidates[0]


def read_key(path: Path) -> str:
    """The key, after checking that the file is the key.

    The protocol requires the file's *content* to be the key and the search engine to fetch it from
    `keyLocation`; a name that disagrees with the content would publish a 404 at the location the
    payload advertises, so the mismatch is rejected here instead of by a 403 from the endpoint.
    """
    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigError(f"cannot read the IndexNow key file {path}: {exc}") from exc
    if not KEY_RE.fullmatch(content):
        raise ConfigError(f"{path} does not contain a 32-character lowercase hex key")
    if content != path.stem:
        raise ConfigError(
            f"{path.name} and its content disagree — the protocol requires the file to contain the "
            f"key, so the file has to be named after it")
    return content


def key_location_for(key: str) -> str:
    """The public URL the key file is served from — computed, never typed twice."""
    return f"{SITE}/{key}.txt"


# ── docs/ path -> canonical public URL ───────────────────────────────────────────────────────────

def public_url_for_path(path: str) -> str | None:
    """The canonical URL a tracked `docs/` path is served at, or None when it is not a page.

    Pure on purpose (path in, URL out): `tests/test_indexnow.py` drives this function, so the rule
    under test is the rule that runs instead of a transcription of it.
    """
    pure = PurePosixPath(path)
    if not pure.parts or pure.parts[0] != DOCS or len(pure.parts) < 2:
        return None
    relative = PurePosixPath(*pure.parts[1:])
    if any(part.startswith(("_", ".")) for part in relative.parts):
        # `_headers`, `_redirects`, `_routes.json`, `_lessons_count.txt`, `.well-known/…`: the
        # site's configuration and machine entry points, not pages a search result can land on.
        return None
    suffix = relative.suffix.lower()
    if suffix not in PAGE_SUFFIXES:
        return None
    if suffix == ".md":
        return f"{SITE}/{relative.as_posix()}"
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return f"{SITE}/" if parent == "." else f"{SITE}/{parent}/"
    return f"{SITE}/{relative.as_posix()[:-len('.html')]}"


def encode_url(url: str) -> str:
    """Percent-encode the path so a CJK lesson slug is a valid RFC 3986 URI.

    IndexNow asks for escaped URLs, and many `docs/lessons/` slugs contain Chinese characters
    (measured 2026-11-15). `%` is left alone so an already-encoded URL is not encoded twice, and the
    query/fragment are untouched because no page here has either.
    """
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/%"),
         parts.query, parts.fragment))


def is_html_document(path: Path) -> bool:
    """Whether the file is an HTML document rather than a token that merely ends in `.html`.

    An unreadable file answers True: a `D` entry in the diff names a page that was just removed, and
    the protocol explicitly accepts deleted URLs, so "cannot read it" must not silently drop it.
    """
    try:
        head = path.read_bytes()[:2048].decode("utf-8", "replace").lower()
    except OSError:
        return True
    return "<!doctype html" in head or "<html" in head


def canonical_urls_for_paths(root: Path, paths: Iterable[str]) -> list[str]:
    """Canonical, encoded, de-duplicated URLs for the changed `docs/` paths that are pages."""
    urls = []
    for path in paths:
        url = public_url_for_path(path)
        if url is None:
            continue
        if path.lower().endswith(".html") and not is_html_document(root / path):
            continue
        urls.append(encode_url(url))
    return sorted(dict.fromkeys(urls))


# ── where the URLs come from ────────────────────────────────────────────────────────────────────

def changed_paths(before: str | None, after: str | None, root: Path = REPO) -> list[str] | None:
    """Every `docs/` path `before..after` added, copied, modified, renamed or deleted.

    `None` means the range cannot answer — no usable `before`/`after`, or git refuses — and the
    caller must fall back to the sitemap. Deletions are included on purpose: the protocol accepts a
    deleted URL, which is how an engine learns that a page it indexed is gone.

    `-z` and `core.quotepath=false` are both load-bearing: paths under `docs/lessons/` contain
    Chinese characters, and the default rendering would turn them into quoted octal escapes that
    resolve to no file at all.
    """
    if not before or not after or set(before) == {"0"}:
        return None
    command = [
        "git", "-c", "core.quotepath=false", "diff", "--name-only", "--diff-filter=ACMRD",
        "-z", before, after, "--", DOCS,
    ]
    try:
        done = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return [path for path in done.stdout.split("\0") if path.strip()]


def sitemap_urls(root: Path = REPO) -> list[str]:
    """Every URL `docs/sitemap.xml` advertises, encoded and de-duplicated."""
    try:
        tree = ET.parse(root / SITEMAP)
    except (OSError, ET.ParseError) as exc:
        raise ConfigError(f"cannot read the sitemap fallback {SITEMAP}: {exc}") from exc
    urls = [element.text.strip() for element in tree.getroot().iter(SITEMAP_LOC) if element.text]
    # Compare the parsed host, not a string prefix: `startswith` on a URL is the incomplete
    # sanitization pattern security scanners (rightly) flag, and equality is what is meant here.
    ours = [url for url in urls if urllib.parse.urlsplit(url).netloc == HOST]
    return sorted({encode_url(url) for url in ours})


def urls_for_run(before: str | None, after: str | None, *, root: Path = REPO,
                 log: Log = print) -> tuple[list[str], str]:
    """The URLs to submit and which source answered: `"diff"` or `"sitemap"`."""
    paths = changed_paths(before, after, root=root)
    if paths is None:
        log("IndexNow: the push range cannot answer — falling back to docs/sitemap.xml")
        return sitemap_urls(root), "sitemap"
    log(f"IndexNow: {len(paths)} changed path(s) under docs/ in {before[:12]}..{after[:12]}")
    return canonical_urls_for_paths(root, paths), "diff"


# ── the request ────────────────────────────────────────────────────────────────────────────────

def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def build_payloads(urls: Iterable[str], key: str, *, key_location: str,
                   host: str = HOST, max_urls: int = MAX_URLS_PER_REQUEST) -> list[dict]:
    """One POST body per at-most-10,000 URLs, in the exact shape the protocol documents."""
    if max_urls < 1:
        raise ValueError("max_urls must be positive")
    return [
        {"host": host, "key": key, "keyLocation": key_location, "urlList": chunk}
        for chunk in _chunks(list(urls), max_urls)
    ]


def post_payload(payload: dict, *, endpoint: str = ENDPOINT,
                 timeout: int = TIMEOUT_SECONDS) -> tuple[int, str]:
    """POST one payload and return `(status, body)`.

    4xx/5xx are answers, not exceptions: the caller logs them. Only transport failures raise, and
    the caller turns those into a warning rather than a failed run.
    """
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4096).decode("utf-8", "replace")


def key_is_live(key_location: str, key: str, *, timeout: int = 10) -> tuple[bool, str]:
    """Whether `keyLocation` already serves the key, and a detail string for the log.

    Never raises: the caller is in the middle of a best-effort wait and a transport error here is
    the same answer as a 404 — "not yet".
    """
    # The `User-Agent` is load-bearing, not politeness: Cloudflare answers urllib's default
    # `Python-urllib/3.11` with **403**, so without it this probe can never report the key as live
    # and every run burns its full 90-second wait. Measured from a runner (2026-11-15): default UA →
    # 403, `MisakaNet-IndexNow/1.0` → 200, curl → 200.
    request = urllib.request.Request(key_location, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096).decode("utf-8", "replace").strip()
            return body == key, f"HTTP {response.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 — any failure means "not live yet"
        return False, f"{type(exc).__name__}: {exc}"


def wait_for_key(key_location: str, key: str, seconds: int, *, log: Log = print,
                 poll: Callable[[str, str], tuple[bool, str]] = key_is_live,
                 interval: float = 5.0) -> bool:
    """Poll `keyLocation` for up to `seconds`; warn (never raise) when it never serves the key."""
    deadline = time.monotonic() + seconds
    while True:
        live, detail = poll(key_location, key)
        if live:
            log(f"IndexNow: the key file is live at {key_location}")
            return True
        if time.monotonic() >= deadline:
            log(f"::warning::IndexNow: {key_location} is not serving the key ({detail}) — "
                f"submitting anyway, because the endpoint answers 202 while key validation is "
                f"pending")
            return False
        time.sleep(interval)


# ── entry point ────────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit the pages a push to docs/ changed to IndexNow.")
    parser.add_argument("--before", default="",
                        help="the push's previous SHA; empty or unresolvable falls back to "
                             "the sitemap")
    parser.add_argument("--after", default="", help="the push's new SHA")
    parser.add_argument("--key-file", default="",
                        help="docs/<key>.txt; discovered by pattern when omitted")
    parser.add_argument("--wait-for-key", type=int, default=0, metavar="SECONDS",
                        help="poll keyLocation for this long before submitting (deploy is async)")
    parser.add_argument("--dry-run", action="store_true", help="print the payloads without POSTing")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None, *, root: Path = REPO,
        poster: Callable[[dict], tuple[int, str]] = post_payload, log: Log = print) -> int:
    args = parse_args(argv)
    try:
        key_path = Path(args.key_file) if args.key_file else discover_key_file(root)
        if not key_path.is_absolute():
            key_path = root / key_path
        if key_path.parent != root / DOCS:
            raise ConfigError(
                f"the key file must live at the docs root ({DOCS}/) — keyLocation is built "
                f"from its name, and {key_path} would be unfetchable there")
        key = read_key(key_path)
        urls, source = urls_for_run(args.before, args.after, root=root, log=log)
        if not urls:
            log("::error::IndexNow: no URLs to submit — this run did not attempt a submission, so "
                "it must not report success")
            return 2
        payloads = build_payloads(urls, key, key_location=key_location_for(key))
        log(f"IndexNow: {len(urls)} URL(s) from the {source}, {len(payloads)} request(s)")
        if args.dry_run:
            for payload in payloads:
                log(f"IndexNow dry run: {len(payload['urlList'])} URL(s), first "
                    f"{payload['urlList'][0]}")
            return 0
        if args.wait_for_key > 0:
            wait_for_key(key_location_for(key), key, args.wait_for_key, log=log)
        for payload in payloads:
            try:
                status, body = poster(payload)
            except Exception as exc:  # noqa: BLE001 — see the module docstring's exit codes
                log(f"::warning::IndexNow: request failed: {type(exc).__name__}: {exc}")
                continue
            if status in (200, 202):
                log(f"IndexNow: HTTP {status} — {len(payload['urlList'])} URL(s) accepted")
            else:
                log(f"::warning::IndexNow: HTTP {status} for {len(payload['urlList'])} URL(s): "
                    f"{body[:500] or '(empty body)'}")
        return 0
    except ConfigError as exc:
        log(f"::error::IndexNow: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(run())
