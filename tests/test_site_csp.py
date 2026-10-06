#!/usr/bin/env python3
"""The 97.9% of this site that cannot execute script must say so in a header.

#2683 audited the homepage and found no Content-Security-Policy. Its verdict on
adding one was deliberately cautious: `docs/index.html` carries 47 inline `on*`
handlers and an 82.9 KB inline `<script>`, and a strict policy over that markup
is not a one-line change. Blindly forcing one would break the homepage with no
test able to say so. That reasoning holds for the homepage and for the ten other
pages that run script.

It does not hold for the rest of the site. Measured on this branch, **521 of the
532 HTML pages under `docs/` contain no inline `on*` handler, no executable
inline `<script>`, and not a single `url(...)` in their inline CSS** — every
external reference on them points back at misakanet.org, or is a plain
`github.com` hyperlink. Those pages can carry `default-src 'none'` and lose
nothing, and this file is what keeps that true:

- a page that grows an inline handler *under a CSP rule* turns the gate red,
  because a policy with no `script-src` allowance would silently kill it;
- a page that grows script *outside* every CSP rule also turns the gate red,
  because that is the case this header cannot help with and must be noticed;
- deleting or loosening a rule turns the ratchet test red.

Why per-path rules and not one `/*` rule: Cloudflare's `_headers` **merges**
every matching rule and comma-joins a repeated header name, which is exactly why
the `Cache-Control` block in this file is three disjoint rules with a comment
about it. A CSP under `/*` cannot be loosened for the eleven script pages
without producing `Content-Security-Policy: a, b`. So the policy is written only
on paths that need it, and the two direction checks above are what keep the
omission honest.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
HEADERS = DOCS / "_headers"

CSP_NAME = "content-security-policy"

# An inline event handler needs a real attribute name in front of it: `content=`
# inside `<meta name="description" content="…">` otherwise matches `on[a-z]+=`,
# and a missing word boundary here reported 521 handlers where there are zero.
HANDLER = re.compile(r"""(?<![\w-])on[a-z]+\s*=\s*["'(]""", re.IGNORECASE)
SCRIPT_TAG = re.compile(r"<script\b(?P<attrs>[^>]*)>", re.IGNORECASE | re.DOTALL)
# `application/ld+json` is data, not code: CSP's script-src does not govern it.
NON_EXECUTABLE_TYPE = re.compile(r"""type\s*=\s*["']application/ld\+json""", re.IGNORECASE)

# The eleven pages that do run script. Listed so a failure names them instead of
# leaving the reader to rediscover the list; the tests derive membership from the
# markup itself and use this only for the error text.
KNOWN_SCRIPT_PAGES = {
    "connect.html",
    "index.html",
    "insights/lesson-coverage.html",
    "insights/pr-genius.html",
    "insights/reputation-leaderboard.html",
    "insights/unsolved-map.html",
    "journey/index.html",
    "search/danmaku-widget.html",
    "search/index.html",
    "start.html",
    # A partial, not served as a page — but it is the source `sync_site_partials`
    # copies into pages, so it has to keep passing the same checks.
    "_partials/nav.html",
}

# Coverage floor, as a fraction of all HTML pages under `docs/`. Measured 521/532
# = 0.979 on this branch. The number is a ratchet, not a target: if a future
# change moves static pages under a script path, this goes red and someone has to
# decide whether the page or the policy moves.
COVERAGE_FLOOR = 0.95


def _parse_headers() -> list[tuple[str, list[tuple[str, str]]]]:
    """`docs/_headers` into [(path pattern, [(name, value)])]."""
    rules: list[tuple[str, list[tuple[str, str]]]] = []
    pattern: str | None = None
    entries: list[tuple[str, str]] = []
    for raw in HEADERS.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            if pattern is not None:
                rules.append((pattern, entries))
            pattern = line.strip()
            entries = []
            continue
        name, _, value = line.strip().partition(":")
        entries.append((name.strip(), value.strip()))
    if pattern is not None:
        rules.append((pattern, entries))
    return rules


def _csp_rules() -> list[tuple[str, str]]:
    """[(path pattern, policy)] for every rule that sets a CSP."""
    return [
        (pattern, value)
        for pattern, entries in _parse_headers()
        for name, value in entries
        if name.lower() == CSP_NAME
    ]


def _matches(pattern: str, path: str) -> bool:
    """Cloudflare `_headers` splat matching, conservative about trailing slashes.

    A directory page is reachable both as `/lessons/x/` and `/lessons/x/index.html`;
    testing against both is what stops a page from escaping a rule by being served
    under its file name.

    The backslash normalisation is deliberate belt-and-braces. `_pages()` already
    hands back POSIX paths via `as_posix()`, but that is one call site away from
    regressing, and the failure is silent rather than loud: every page simply stops
    matching every rule, so coverage reads 0 and the direction checks have nothing
    to complain about. Normalising here means a Windows-shaped path is *handled*
    instead of quietly matching nothing. `test_windows_style_paths_still_match_a_rule`
    is what keeps that honest, and it runs on Linux.
    """
    path = path.replace("\\", "/")
    for candidate in {path, path.rstrip("/") + "/", path.rstrip("/") + "/index.html"}:
        if pattern.endswith("/*"):
            if candidate.startswith(pattern[:-1]):
                return True
        elif pattern.endswith("*"):
            if candidate.startswith(pattern[:-1]):
                return True
        elif candidate == pattern or candidate == pattern + "/":
            return True
    return False


def test_windows_style_paths_still_match_a_rule() -> None:
    """Regression: this gate reported 0/532 coverage on Windows and 521/532 on Linux.

    Reproducible on any platform by handing the matcher what `Path.relative_to()`
    produces on Windows, which is the exact input that used to slip through.
    """
    assert _matches("/lessons/*", "/lessons/benchmark-honesty-simulated-vs-real/index.html")
    assert _matches("/lessons/*", "\\lessons\\benchmark-honesty-simulated-vs-real\\index.html")
    assert _matches("/lessons/*", "/lessons/foo/")
    assert _matches("/privacy/*", "\\privacy\\index.html")
    assert _matches("/journey/http-mcp/*", "\\journey\\http-mcp\\index.html")
    assert not _matches("/lessons/*", "/index.html")
    assert not _matches("/journey/http-mcp/*", "/journey/index.html")
    assert not _matches("/lessons/*", "/privacy/index.html")


@lru_cache(maxsize=1)
def _pages() -> list[tuple[str, str]]:
    """[(repo-relative path in POSIX form, source)] for every HTML page under `docs/`.

    Cached because reading 532 files once per assertion turned this file into the
    slowest thing in the suite; the working tree does not change mid-run.

    `as_posix()` is load-bearing, not cosmetic. `Path.relative_to()` renders `\\` on
    Windows, so `"/" + path` produced `/lessons\\foo\\index.html`, which matches no
    `_headers` rule: coverage read 0/532 and the whole gate went quiet on Windows
    while passing on Linux. The Windows jobs in this PR's own CI run are what caught
    it — a green local suite on ext4 did not.
    """
    return [
        (p.relative_to(DOCS).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted(DOCS.rglob("*.html"))
    ]


def _runs_script(source: str) -> bool:
    """True when this markup can execute script without a `src=` fetch.

    That is exactly the set a `default-src 'none'` policy would break, so it is
    the predicate both direction tests turn on.
    """
    if HANDLER.search(source):
        return True
    for match in SCRIPT_TAG.finditer(source):
        attrs = match.group("attrs")
        if re.search(r"\bsrc\s*=", attrs):
            continue
        if NON_EXECUTABLE_TYPE.search(attrs):
            continue
        return True
    return False


def _external_hosts(source: str) -> set[str]:
    """Hosts this markup asks the *browser to fetch a subresource* from.

    Only attributes that load something are listed. `<a href="https://github.com/…">`
    is a hyperlink: navigation is not a fetch, `default-src` does not govern it, and
    counting it produced 496 false offenders on the first run of this file. The
    attributes that *are* governed are `src`, `srcset`, `<link href>` (stylesheet,
    icon, preload) and `<object data>`; `form action` belongs to `form-action` and
    `<base href>` to `base-uri`, both of which the policy sets explicitly.
    """
    urls: list[str] = []
    urls += [m.group("url") for m in re.finditer(
        r"""\b(?:src|data)\s*=\s*["'](?P<url>(?:https?:)?//[^"']+)["']""", source, re.IGNORECASE
    )]
    srcset = re.finditer(r"\bsrcset\s*=\s*[\"']([^\"']+)[\"']", source, re.IGNORECASE)
    urls += [c.strip().split()[0] for m in srcset for c in m.group(1).split(",") if c.strip()]
    urls += [m.group("url") for m in re.finditer(
        r"""<link\b[^>]*?\bhref\s*=\s*["'](?P<url>(?:https?:)?//[^"']+)["']""",
        source, re.IGNORECASE | re.DOTALL,
    )]
    return {
        re.sub(r"^(?:https?:)?//", "", u).split("/")[0]
        for u in urls
        if u.startswith(("http://", "https://", "//"))
    }


def test_the_headers_file_declares_a_content_security_policy() -> None:
    """Without a rule here every other test below is vacuously satisfied."""
    csp = _csp_rules()
    assert csp, f"docs/_headers sets no {CSP_NAME}; #2683 is still open because of this"


def test_every_csp_rule_carries_the_same_policy() -> None:
    """Seven rules with seven copies of the policy drift the moment one is edited.

    `_headers` cannot include a value from elsewhere, so the repetition is forced.
    This test is the only thing that keeps it from becoming seven different
    policies that nobody can review as one.
    """
    policies = {value for _, value in _csp_rules()}
    assert len(policies) == 1, (
        "the CSP rules disagree:\n"
        + "\n".join(f"  {p}\n    {v}" for p, v in sorted(_csp_rules()))
    )


def test_the_policy_does_not_re_enable_what_it_is_meant_to_block() -> None:
    """A policy that permits `unsafe-inline` script is decoration, not a gate.

    `style-src 'unsafe-inline'` is required and allowed: 521 of 521 static pages
    carry an inline `<style>` block. That is a deliberate trade — inline CSS
    cannot execute script — so this check reads the directives rather than
    grepping the whole string for `unsafe-inline`, which would fail on a policy
    that is doing the right thing.
    """
    rules = _csp_rules()
    assert rules, "no CSP rule to inspect"
    for pattern, policy in rules:
        directives = {}
        for part in policy.split(";"):
            name, _, value = part.strip().partition(" ")
            if name:
                directives[name.strip().lower()] = value.strip()

        assert "default-src" in directives, (
            f"{pattern}: no default-src, so nothing is denied by default"
        )
        # Exactly `'none'`, with the quotes. A bare `none` is what CSP Level 1
        # callers wrote, and browsers treat it as a host named "none" — the
        # directive is then simply ignored and the policy looks applied while
        # denying nothing. A gate that passes on a dead directive is worse than
        # no gate, so the quotes are required rather than stripped.
        assert directives["default-src"] == "'none'", (
            f"{pattern}: default-src is {directives['default-src']!r}, not the quoted "
            "'none'. An unquoted `none` is ignored by CSP Level 1 parsers."
        )

        for directive in ("script-src", "script-src-elem"):
            if directive in directives:
                value = directives[directive]
                assert "unsafe-inline" not in value, f"{pattern}: {directive} allows unsafe-inline"
                assert "unsafe-eval" not in value, f"{pattern}: {directive} allows unsafe-eval"
                assert "'*'" not in value and " *" not in value, (
                    f"{pattern}: {directive} allows any host"
                )

        assert "base-uri" in directives, (
            f"{pattern}: no base-uri, so <base> can repoint every relative URL"
        )
        assert "form-action" in directives, f"{pattern}: no form-action"


def test_no_page_under_a_csp_rule_can_execute_script() -> None:
    """The direction that breaks the site.

    A policy with no `script-src` allowance kills every inline handler and every
    executable inline script on the pages it covers. That is the intent — but the
    day someone adds a handler to a lesson page, the page breaks and nothing else
    in the repository would notice.
    """
    rules = _csp_rules()
    offenders: list[str] = []
    for path, source in _pages():
        if not _runs_script(source):
            continue
        site_path = "/" + path
        for pattern, _ in rules:
            if _matches(pattern, site_path):
                offenders.append(f"{site_path} matches rule `{pattern}`")
                break
    assert not offenders, (
        "these pages run script but sit under a CSP rule that forbids it; the page "
        "would break in production with no local signal:\n  " + "\n  ".join(offenders)
    )


def test_every_page_that_runs_script_is_outside_every_csp_rule() -> None:
    """The direction that leaves a hole.

    #2683's point stands for the pages this cannot reach: a script page with no
    CSP has the same single-layer defence #2683 described. The gate cannot fix
    that, but it can stop the list from quietly growing while the header claims
    coverage.
    """
    rules = _csp_rules()
    if not rules:
        return  # the "no rule declared" test is the one that should fail here
    script_pages = {path for path, source in _pages() if _runs_script(source)}
    unlisted = script_pages - KNOWN_SCRIPT_PAGES
    assert not unlisted, (
        "these pages can execute script but are not in KNOWN_SCRIPT_PAGES; add them "
        "so the omission is a decision on the record rather than an oversight:\n  "
        + "\n  ".join(sorted(unlisted))
    )
    missing = KNOWN_SCRIPT_PAGES - script_pages
    assert not missing, (
        "KNOWN_SCRIPT_PAGES lists pages that no longer run script; a CSP rule can "
        "likely cover them now:\n  " + "\n  ".join(sorted(missing))
    )


def test_pages_under_a_csp_rule_reference_nothing_the_policy_forbids() -> None:
    """A page under the policy may not reach for a host the policy does not allow.

    This is the check that would have caught a remote image or a CDN script being
    added to a lesson page: `default-src 'none'` would block it at runtime, and
    the layout would break with an error nobody reads.
    """
    rules = _csp_rules()
    offenders: list[str] = []
    for path, source in _pages():
        site_path = "/" + path
        covering = [p for p, _ in rules if _matches(p, site_path)]
        if not covering:
            continue
        for host in _external_hosts(source):
            if host == "misakanet.org":
                continue  # self; `default-src 'none'` needs an explicit allowance for it
            offenders.append(f"{site_path} ({covering[0]}) references {host}")
    assert not offenders, (
        "these pages are under a CSP rule but reference an external host the policy "
        "does not allow:\n  " + "\n  ".join(sorted(set(offenders)))
    )


def test_coverage_is_a_ratchet_not_a_snapshot() -> None:
    """Deleting the rules must turn this red, not silently unprotect the site."""
    rules = _csp_rules()
    if not rules:
        return  # covered by test_the_headers_file_declares_a_content_security_policy
    total = len(_pages())
    covered = [p for p, _ in _pages() if any(_matches(rule, "/" + p) for rule, _ in rules)]
    ratio = len(covered) / total if total else 0.0
    assert ratio >= COVERAGE_FLOOR, (
        f"CSP covers {len(covered)}/{total} pages ({ratio:.1%}), below the {COVERAGE_FLOOR:.0%} "
        "floor. Raise the policy onto more static paths rather than lowering the floor."
    )


def test_the_measured_shape_of_the_site_matches_what_the_policy_assumes() -> None:
    """Pin the measurement the policy was designed from.

    The strict policy is justified by "the static pages need nothing". If a
    generated page ever starts shipping a script or a remote asset, the
    justification is stale and this fails before the per-page checks do.
    """
    script_pages = {path for path, source in _pages() if _runs_script(source)}
    static = [path for path, _ in _pages() if path not in script_pages]
    assert len(static) == 521, (
        f"expected 521 pages with no script, found {len(static)}; "
        f"new script pages: {sorted(script_pages - KNOWN_SCRIPT_PAGES)}"
    )
    for path in static:
        source = (DOCS / path).read_text(encoding="utf-8")
        for block in re.findall(r"<style[^>]*>(.*?)</style>", source, re.S | re.IGNORECASE):
            assert "url(" not in block, (
                f"{path} fetches something from its inline CSS; `default-src 'none'` "
                "would block it, so the page is no longer self-contained"
            )
