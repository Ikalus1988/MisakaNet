#!/usr/bin/env python3
"""Every default endpoint in this repository must name a domain that resolves.

`integrations/langchain/misakanet_tool.py` and `integrations/llamaindex/misakanet_tool.py`
both shipped this:

    DEFAULT_ENDPOINT = "https://misakanet.dev/api/search"
    DEFAULT_MCP_URL  = "https://misakanet.dev/mcp"

`misakanet.dev` does not resolve. Measured 2026-10-06 on this machine:

    $ getent hosts misakanet.dev
    (nothing — NO DNS)
    $ getent hosts misakanet.org
    2606:4700:3032::6815:3761 misakanet.org

Both files feed that constant straight into `urllib.request.urlopen`, and both read it
as a user-overridable default:

    default_factory=lambda: os.environ.get("MISAKANET_SEARCH_URL", DEFAULT_ENDPOINT)

So the tool worked exactly as written and returned `Search failed: <urlopen error
[Errno -2] Name or service not known>` for every query. Two further problems rode along:
the path was wrong as well as the host (`/api/search` is a 404; the public search
endpoint is `/api/lessons`, confirmed 200 JSON at the time of writing), and
`misakanet.dev` appears in 20+ tracked files.

**Why the suite was green.** `tests/test_integrations.py` patches
`urllib.request.urlopen` for the REST search path, so the constant is never resolved,
never dialled, and never checked. Every assertion passed against a URL that cannot
exist. That is the same shape as the dead `tests/dsh/` suite removed in #2920: a mock
at the boundary converts "this cannot work" into "this is tested". Mocking the network
is legitimate; mocking the network *and* asserting nothing about the address is a test
that certifies a fiction.

This gate does not make network calls — the suite has to stay runnable offline and
without credentials. It asserts the weaker property that is still decisive: a default
endpoint must name the repository's canonical host, and must use a path the worker
actually serves. The canonical host is not hardcoded here; it is read from the shipped
client (`lib/client.js`), so a future domain change updates the gate instead of
silently invalidating it.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The shipped client's own constants. `lib/client.js` is what the DSH plugin, the web
# overlay, and the browser build all dial, so it is the best available statement of
# "the domain and path this project is served from".
CLIENT_JS = REPO / "lib/client.js"

# Files that define a default endpoint users are expected to be able to reach.
# `integrations/` is not in the wheel (`pyproject.toml` ships `misakanet*` only), but it
# is imported by `tests/test_integrations.py` and documented in `integrations/*/README.md`,
# so it is repo code with tests, not scratch.
CANDIDATES = [
    REPO / "integrations/langchain/misakanet_tool.py",
    REPO / "integrations/llamaindex/misakanet_tool.py",
    REPO / "misakanet/tools/langchain_tool.py",
]

# A line that becomes a request target when the user does not override it. A docstring
# showing an example is prose; a DEFAULT_* / *_URL assignment is a default.
DEFAULT_LINE = re.compile(r"DEFAULT_\w+|SEARCH_URL|MCP_URL")

URL_IN_TEXT = re.compile(r"https?://([A-Za-z0-9.-]+)(/[A-Za-z0-9./_?=&%-]*)?")

# The path the shipped client searches through. `/api/search` is a 404; this is 200.
PUBLIC_SEARCH_PATH = "/api/lessons"


def _canonical_host() -> str:
    text = CLIENT_JS.read_text(encoding="utf-8")
    hosts = {m.group(1) for m in URL_IN_TEXT.finditer(text)}
    assert hosts, (
        f"{CLIENT_JS.name} contains no absolute http(s) URL, so this gate cannot learn "
        "the canonical host. If the client's endpoints moved behind a config layer, "
        "point this function at whatever now defines them."
    )
    assert len(hosts) == 1, (
        f"{CLIENT_JS.name} names {len(hosts)} hosts ({sorted(hosts)}); this gate assumed "
        "one canonical host. Resolve which is authoritative and narrow the assertion."
    )
    return hosts.pop()


def _default_lines() -> list[tuple[Path, int, str]]:
    """(path, line number, line) for every line that defines a network default."""
    out = []
    for path in CANDIDATES:
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if DEFAULT_LINE.search(line):
                out.append((path, n, line))
    return out


def test_the_canonical_host_is_learned() -> None:
    """Otherwise every check below passes by comparing the dead host to itself."""
    host = _canonical_host()
    assert host != "misakanet.dev", (
        "the canonical host is misakanet.dev, which does not resolve (measured "
        "2026-10-06, `getent hosts misakanet.dev` returns nothing). If the domain "
        "moved, fix lib/client.js first — this gate follows it, it does not override it."
    )


def test_no_default_endpoint_points_at_a_dead_host() -> None:
    """The defect this gate was written for: a default that cannot be dialled.

    Every network default must sit on the canonical host. Reading the host from the
    shipped client rather than from a literal here is deliberate: when the project moves
    domains, this gate follows the move instead of failing on a value that was correct
    the day it was written.
    """
    canonical = _canonical_host()
    lines = _default_lines()
    assert lines, (
        "no default endpoint was checked. The file list, the assignment pattern, or the "
        "URL regex has drifted from the code — this gate is currently vacuous."
    )

    checked = 0
    for path, n, line in lines:
        rel = path.relative_to(REPO)
        for match in URL_IN_TEXT.finditer(line):
            checked += 1
            host, url_path = match.group(1), match.group(2) or ""
            assert host == canonical, (
                f"{rel}:{n} defaults to host `{host}`, but the shipped client "
                f"({CLIENT_JS.relative_to(REPO)}) dials `{canonical}`.\n"
                f"  {line.strip()}\n"
                "A default the user never has to override has to work out of the box; "
                "this one returns a DNS failure for every query. Note that "
                "tests/test_integrations.py patches urlopen, so the suite cannot catch "
                "this — the mock stands in for the network it never reaches."
            )
            # The host can be right and the path still wrong; that is what the 404 on
            # /api/search was. Shape check, not equality, so a version prefix added to
            # the public path later does not turn this into a snapshot.
            if "/api/" in url_path:
                assert url_path.split("?")[0].rstrip("/").endswith(PUBLIC_SEARCH_PATH), (
                    f"{rel}:{n} points at `{url_path}`. Measured 2026-10-06 on "
                    f"{canonical}: `GET /api/search?q=test&limit=1` -> 404 "
                    f"(application/json), `GET /api/lessons?limit=1` -> 200 "
                    f"(application/json). Fixing the host without this would swap a DNS "
                    "error for an HTTP error and leave the tool just as broken."
                )


def test_the_gate_actually_sees_the_integration_defaults() -> None:
    """Anchor the file list to reality.

    If `integrations/` is ever deleted, vendored, or renamed, the two checks above would
    go quiet rather than red. This asserts the specific lines they exist to guard are
    still present and still declare a default.
    """
    seen = set()
    for path, _n, line in _default_lines():
        for match in URL_IN_TEXT.finditer(line):
            seen.add(match.group(0))
    assert seen, (
        "no absolute default URL found in the candidate files. Either the integrations "
        "moved or they stopped declaring network defaults — in both cases this gate "
        "needs re-pointing rather than deleting."
    )
    for required in (PUBLIC_SEARCH_PATH,):
        assert any(required in url for url in seen), (
            f"no default URL uses {required}. The integrations declare "
            f"{sorted(seen)}; if the public search path moved, update "
            "PUBLIC_SEARCH_PATH from lib/client.js rather than loosening the check."
        )
