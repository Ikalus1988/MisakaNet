#!/usr/bin/env python3
"""Verify MisakaNet's Glama MCP listing shows the right tools and the right version.

Three outcomes, and they are not allowed to blur into one another (the same
discipline as `registry-drift-watch.yml`, whose comment says so in full):

* **exit 0** — the probe answered and the listing matches;
* **exit 1** — the probe answered and found a real mismatch;
* **exit 2** — the probe **could not answer**.

Exit 2 used to be unreachable in the case that matters. The Glama JSON API now
answers `401 unauthorized` ("This endpoint requires an API key" — measured
2026-10-22), and the old code swallowed that with `except Exception: pass` and
silently fell back to scraping the web page. The scrape matched
`misakanet_([a-z]\\w*)` **anywhere** in the HTML, so it counted tool names out
of the repository README (`misakanet_cli` out of `scripts/misakanet_cli.py`,
`misakanet_usage_status` out of a README bullet) and out of a tool
*description* (`misakanet_get_my_events`, which the `misakanet_me_events`
description mentions as its old name). The scrape reported **13** "advertised"
tools; the listing actually advertises **11**. Worse, a 401 and a real
mismatch both ended in "not healthy", so "we could not ask" was
indistinguishable from "we asked and it is wrong".

What the page really says, measured 2026-10-22 against
`https://glama.ai/mcp/servers/Ikalus1988/MisakaNet` (no account, no API key):

* **11** tools, taken from the tool cards' own ids
  (`<details id="misakanet_…">`), not from prose;
* the version Glama publishes for this repository — **2.48.0** — read from the
  listing record's `latestRelease`;
* the release the listing's **tool schema** was last observed at — **2.43.0**,
  observed **2026-10-15T16:44:56Z** — from the rendered "Tool Schema
  Changelog";
* the last time Glama **scored** the listing — **2026-10-16T21:15:25Z** —
  from the rendered TDQS line.

Those 11 tools are the **Python stdio server's** tool set
(`misakanet/server/tools.py`), not the hosted worker's 8: the repository's
`Dockerfile` starts `python3 scripts/mcp_server.py`, and the strings
"local stdio process only", "remote submission is disabled",
"MISAKANET_USAGE_DISABLE_REMOTE" and "local placeholder report only" appear on
the Glama page (3, 2, 2, 2 times) and **zero** times in
`workers/register-proxy-sw.js`. So the listing is a faithful introspection of
the surface Glama builds from this repository; it is *not* the hosted
endpoint, which Glama advertises separately as the connector
`org.misakanet/misaka-net` with exactly the worker's 8 tools. That is the
"publishing contract" question, and it is **not** this script's to decide — see
`docs/integrations/glama-listing.md`.

Usage:
  python3 scripts/verify-glama-listing.py [--json]

Environment:
  GLAMA_API_KEY — optional. Glama's JSON API requires a key; with one, the API
  is used as the authoritative source. Without one the API answers 401 and the
  public listing page is read instead.

Exit codes:
  0 — the probe answered and the listing matches
  1 — the probe answered and the listing does not match
  2 — the probe could not answer (nothing said "the listing is wrong")

Issue #1063, #3644
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

GLAMA_API = "https://glama.ai/api/mcp/v1/servers/Ikalus1988/MisakaNet"
GLAMA_PAGE = "https://glama.ai/mcp/servers/Ikalus1988/MisakaNet"
WORKER = Path(__file__).resolve().parent.parent / "workers" / "register-proxy-sw.js"
STDOOL_TOOLS = Path(__file__).resolve().parent.parent / "misakanet" / "server" / "tools.py"
GLAMA_MANIFEST = Path(__file__).resolve().parent.parent / "glama.json"

EXPECTED_CORE_TOOLS = [
    "misakanet_search",
    "misakanet_get_lesson",
    "misakanet_submit_intake",
]

#: The listing page renders one `<details>` per advertised tool, and the element's id *is* the
#: tool name. That is a structural anchor: the README prose and the tool descriptions are not
#: in it, which is exactly what the old `misakanet_([a-z]\w*)` scrape could not tell apart.
TOOL_CARD = re.compile(r'<details[^>]*\bid="(misakanet_[a-z0-9_]+)"')

#: The "Tool Schema Changelog" entries, e.g. `<code …>v<!-- -->2.43.0</code></span><time …
#: dateTime="2026-10-15T16:44:56.961170Z"`. React splits the text nodes with `<!-- -->`.
CHANGELOG_ENTRY = re.compile(
    r'<code[^>]*>v<!-- -->(\d+\.\d+\.\d+)</code></span><time[^>]*dateTime="([^"]+)"'
)

#: The TDQS line: `Scored<!-- --> <time dateTime="2026-10-16T21:15:25.208460Z" …`.
SCORED_AT = re.compile(r'Scored<!-- --> <time dateTime="([^"]+)"')

#: A version, as `X.Y.Z`. Used to compare the version Glama publishes with the one this
#: repository declares — a string comparison would put "2.9.0" above "2.48.0".
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def get_local_tools() -> list[str]:
    """Extract tool names from register-proxy-sw.js MCP_TOOLS definition."""
    text = WORKER.read_text(encoding="utf-8")
    return re.findall(r'name:\s*"misakanet_(\w+)"', text)


def get_stdio_tools() -> list[str]:
    """The tool names of the Python stdio server — the surface the Dockerfile starts.

    `Dockerfile` runs `python3 scripts/mcp_server.py`, and `server.json` publishes the
    `python3 -m misakanet.server` package; both are the stdio server, whose tool list lives in
    `misakanet/server/tools.py`. Glama builds this repository from that Dockerfile and
    introspects whatever it starts, so this is the tool set a listing produced from this
    repository is *expected* to carry.
    """
    text = STDOOL_TOOLS.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'"name":\s*"(misakanet_[a-z0-9_]+)"', text)))


def get_declared_version() -> str:
    """The version this repository declares for the listing — `glama.json`'s `version`.

    The repository is the source of truth for the version; the listing is a copy of it.
    """
    return str(json.loads(GLAMA_MANIFEST.read_text(encoding="utf-8"))["version"])


def parse_version(raw: str) -> tuple[int, int, int]:
    """`"2.48.0"` -> `(2, 48, 0)`. Raises `ValueError` on anything else."""
    match = SEMVER.match(raw.strip())
    if match is None:
        raise ValueError(f"not a version: {raw!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


# ── reading the listing ────────────────────────────────────────────────────────────────────────


def listing_from_page(html: str) -> dict:
    """Read the listing out of its public page. Pure: it takes HTML, it fetches nothing.

    Returns `{"tools": [...], "version": str|None, "inspected_version": str|None,
    "inspected_at": str|None, "scored_at": str|None, "error": str|None}`. `error` is set when
    the page could not be read as a listing at all; the probe turns that into "could not
    answer", never into a mismatch.
    """
    tools = sorted(set(TOOL_CARD.findall(html)))
    if not tools:
        return {"tools": [], "version": None, "inspected_version": None, "inspected_at": None,
                "scored_at": None,
                "error": "no tool cards found in the listing page"}

    changelog = CHANGELOG_ENTRY.findall(html)
    inspected_version, inspected_at = (None, None)
    if changelog:
        # The newest observation is the highest release version, not the first one rendered.
        inspected_version, inspected_at = max(changelog, key=lambda entry: parse_version(entry[0]))

    scored = SCORED_AT.search(html)
    return {
        "tools": tools,
        "version": published_version(html),
        "inspected_version": inspected_version,
        "inspected_at": inspected_at,
        "scored_at": scored.group(1) if scored else None,
        "error": None,
    }


def published_version(html: str) -> str | None:
    """The version Glama publishes for this repository, or `None` if it is not on the page.

    The listing record carries it as `latestRelease.version`. The page ships that record as a
    flat array (every value indexed once; an object's key is written `_` plus the index of the
    key string), so the lookup is two steps: find the element the key `latestRelease` maps to,
    then the element the key `version` maps to.

    Measured 2026-10-22: the listing page publishes `2.48.0`, the version this repository
    declares. The page does **not** render it — the only copy is in that array — which is why
    this cannot be a plain regex over the visible HTML.
    """
    flat = _flat_array(html)
    if flat is None:
        return None
    release = _flat_value(flat, "latestRelease")
    if not isinstance(release, dict):
        return None
    version = _flat_member(flat, release, "version")
    if not isinstance(version, str):
        return None
    return version


def _flat_array(html: str) -> list | None:
    """The listing page's flat record array, or `None` when the page does not carry one."""
    for chunk in _payload_chunks(html):
        try:
            flat = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(flat, list) and flat:
            return flat
    return None


def _payload_chunks(html: str) -> list[str]:
    """The JSON documents the page streams into the client, one per `enqueue` call.

    The page ships its record as `window.__reactRouterContext.streamController.enqueue("…")`,
    where the argument is a JavaScript string literal holding a JSON document.
    """
    chunks = []
    for match in re.finditer(r"streamController\.enqueue\(", html):
        start = match.end()
        if start >= len(html) or html[start] != '"':
            continue
        cursor = start + 1
        literal = []
        while cursor < len(html):
            char = html[cursor]
            if char == "\\":
                literal.append(html[cursor:cursor + 2])
                cursor += 2
                continue
            if char == '"':
                break
            literal.append(char)
            cursor += 1
        else:
            continue
        try:
            chunks.append(json.loads('"' + "".join(literal) + '"'))
        except json.JSONDecodeError:
            continue
    return chunks


def _flat_value(flat: list, key: str) -> object | None:
    """The value `key` maps to in the page's flat record array, or `None`."""
    for element in flat:
        if not isinstance(element, dict):
            continue
        for encoded, reference in element.items():
            if not (encoded.startswith("_") and encoded[1:].isdigit()):
                continue
            index = int(encoded[1:])
            if index >= len(flat) or flat[index] != key:
                continue
            if not isinstance(reference, int) or not 0 <= reference < len(flat):
                return None
            return flat[reference]
    return None


def _flat_member(flat: list, container: dict, key: str) -> object | None:
    """The value `key` maps to inside one element of the page's flat record array.

    Scoped to the container, so a `version` key that belongs to some other record in the same
    array cannot be mistaken for the one being looked up.
    """
    for encoded, reference in container.items():
        if not (encoded.startswith("_") and encoded[1:].isdigit()):
            continue
        index = int(encoded[1:])
        if index >= len(flat) or flat[index] != key:
            continue
        if not isinstance(reference, int) or not 0 <= reference < len(flat):
            return None
        return flat[reference]
    return None


def listing_from_api(payload: str) -> dict:
    """Read the listing out of Glama's JSON API body. Pure: it takes the body, it fetches nothing.

    Returns the same shape as `listing_from_page`.
    """
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        return {"tools": [], "version": None, "error": f"the API answer was not JSON: {error}"}
    if not isinstance(data, dict):
        return {"tools": [], "version": None, "error": "the API answer was not a JSON object"}

    tools = []
    for entry in data.get("tools") or []:
        if isinstance(entry, str):
            tools.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
            tools.append(entry["name"])
    if not tools:
        return {"tools": [], "version": None,
                "error": "the API answer carried no tools"}

    version = data.get("version")
    if not isinstance(version, str):
        release = data.get("latestRelease")
        if isinstance(release, dict) and isinstance(release.get("version"), str):
            version = release["version"]
    return {
        "tools": sorted(set(tools)),
        "version": version if isinstance(version, str) else None,
        "inspected_version": None,
        "inspected_at": None,
        "scored_at": None,
        "error": None,
    }


def fetch(url: str, accept: str) -> tuple[int | None, str, str | None]:
    """GET `url`. Returns `(status, body, error)`; `error` is set when the request failed."""
    headers = {"Accept": accept}
    key = os.environ.get("GLAMA_API_KEY")
    if key and url == GLAMA_API:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body, f"HTTP {error.code}"
    except Exception as error:  # noqa: BLE001 — the reason is reported, never swallowed
        return None, "", str(error)


def get_glama_listing() -> dict:
    """Ask Glama what the listing says. Returns the first **complete** answer.

    A source is complete when it produced a tool list *and* a version: the probe compares both,
    so an answer with only one of them cannot answer the question and is not an answer.
    """
    attempts = []

    status, body, error = fetch(GLAMA_API, "application/json")
    if error is None and status == 200:
        answer = listing_from_api(body)
        if answer["error"] is None and answer["version"] is not None:
            answer["source"] = "api"
            return answer
        attempts.append(f"the API answered but {answer['error'] or 'carried no version'}")
    elif status in (401, 403):
        attempts.append(f"the API answered HTTP {status}: it requires an API key")
    else:
        attempts.append(f"the API did not answer ({error or f'HTTP {status}'})")

    status, body, error = fetch(GLAMA_PAGE, "text/html")
    if error is None and status == 200:
        answer = listing_from_page(body)
        if answer["error"] is None and answer["version"] is not None:
            answer["source"] = "page"
            return answer
        attempts.append(f"the page answered but {answer['error'] or 'carried no version'}")
    else:
        attempts.append(f"the page did not answer ({error or f'HTTP {status}'})")

    return {"tools": [], "version": None, "inspected_version": None, "inspected_at": None,
            "scored_at": None, "source": None,
            "error": "; ".join(attempts) or "no source answered"}


# ── deciding ──────────────────────────────────────────────────────────────────────────────────


def compare(local_tools: list[str], declared_version: str, listing: dict) -> dict:
    """Compare what we publish with what the listing says. Pure.

    Returns `{"outcome": "match"|"mismatch"|"cannot-answer", ...}`. The three outcomes are
    the whole point: a probe that could not answer must never answer "the listing is wrong".
    """
    advertised = list(listing.get("tools") or [])
    advertised_version = listing.get("version")

    if not advertised or not advertised_version:
        return {
            "outcome": "cannot-answer",
            "reason": listing.get("error") or "the listing carried no tools or no version",
            "missing_core_tools": [],
            "stale_on_glama": [],
            "missing_from_glama": [],
            "version_ok": False,
        }

    missing_core = [tool for tool in EXPECTED_CORE_TOOLS if tool not in advertised]
    local_set = set(local_tools)
    advertised_set = set(advertised)
    stale_tools = sorted(advertised_set - local_set)
    new_tools = sorted(local_set - advertised_set)

    try:
        published = parse_version(advertised_version)
        declared = parse_version(declared_version)
    except ValueError as error:
        return {
            "outcome": "cannot-answer",
            "reason": f"a version could not be read: {error}",
            "missing_core_tools": missing_core,
            "stale_on_glama": stale_tools,
            "missing_from_glama": new_tools,
            "version_ok": False,
        }

    # The listing may carry a version *newer* than ours — that is fine, it means it saw a
    # release we have not published yet. Older is drift: the listing is behind the repository.
    version_ok = published >= declared

    drifted = bool(missing_core or stale_tools or new_tools) or not version_ok
    return {
        "outcome": "mismatch" if drifted else "match",
        "reason": None,
        "missing_core_tools": missing_core,
        "stale_on_glama": stale_tools,
        "missing_from_glama": new_tools,
        "version_ok": version_ok,
    }


def main(argv: list[str] | None = None, listing: dict | None = None) -> int:
    """Run the probe. Returns the exit code; `listing` may be injected to keep a test offline.

    The listing is the one thing this script cannot read from the repository, so it is the one
    thing a test may hand over instead of fetching. Everything else — the worker's tool list,
    the stdio server's tool list, the declared version — is read from the checkout.
    """
    argv = sys.argv if argv is None else argv
    as_json = "--json" in argv

    local_tools = [f"misakanet_{suffix}" for suffix in get_local_tools()]
    declared_version = get_declared_version()
    if listing is None:
        listing = get_glama_listing()
    verdict = compare(local_tools, declared_version, listing)

    stdio_tools = get_stdio_tools()
    # The names the listing advertises but the hosted worker does not serve are, in this
    # repository, the stdio server's tools: the listing is an introspection of what the
    # Dockerfile starts. Saying so is the difference between "the listing is broken" and "the
    # listing describes the other surface", and it is the whole reason the numbers are here.
    stale = verdict["stale_on_glama"]
    stale_from_stdio = [name for name in stale if name in stdio_tools]
    stale_unknown = [name for name in stale if name not in stdio_tools]
    result = {
        "outcome": verdict["outcome"],
        "local_tool_count": len(local_tools),
        "local_tools": local_tools,
        "stdio_tool_count": len(stdio_tools),
        "stdio_tools": stdio_tools,
        "glama_tool_count": len(listing.get("tools") or []),
        "glama_tools": listing.get("tools") or [],
        "missing_core_tools": verdict["missing_core_tools"],
        "stale_on_glama": stale,
        "stale_on_glama_from_stdio": stale_from_stdio,
        "stale_on_glama_unknown": stale_unknown,
        "missing_from_glama": verdict["missing_from_glama"],
        "local_version": declared_version,
        "glama_version": listing.get("version"),
        "version_ok": verdict["version_ok"],
        "glama_inspected_version": listing.get("inspected_version"),
        "glama_inspected_at": listing.get("inspected_at"),
        "glama_scored_at": listing.get("scored_at"),
        "glama_error": listing.get("error"),
        "glama_source": listing.get("source"),
        "healthy": verdict["outcome"] == "match",
    }

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Local MCP tools: {len(local_tools)} ({', '.join(local_tools)})")
        print(f"Stdio MCP tools: {len(stdio_tools)}")
        print(f"Glama tools:     {result['glama_tool_count']}")
        for name in result["glama_tools"]:
            print(f"  - {name}")
        print(f"Glama source:    {result['glama_source'] or 'none'}")
        print(f"Version declared: {declared_version}   published by Glama: {result['glama_version']}")
        if result["glama_inspected_version"]:
            print(f"Last tool schema observed: v{result['glama_inspected_version']} "
                  f"at {result['glama_inspected_at']}")
        if result["glama_scored_at"]:
            print(f"Last scored:              {result['glama_scored_at']}")
        if result["glama_error"]:
            print(f"Glama error: {result['glama_error']}")
        if verdict["missing_core_tools"]:
            print(f"Missing core tools: {verdict['missing_core_tools']}")
        if verdict["stale_on_glama"]:
            print(f"Stale on Glama (removed locally): {verdict['stale_on_glama']}")
            if result["stale_on_glama_from_stdio"]:
                print(f"  ↳ all of them are tools of this repository's stdio server "
                      f"({result['stale_on_glama_from_stdio']}), which the Dockerfile starts — "
                      f"the listing describes that surface, not the hosted worker")
            if result["stale_on_glama_unknown"]:
                print(f"  ↳ these are in neither surface: {result['stale_on_glama_unknown']}")
        if verdict["missing_from_glama"]:
            print(f"Missing from Glama (added locally): {verdict['missing_from_glama']}")
        if not verdict["version_ok"] and result["glama_version"]:
            print(f"Version drift: Glama publishes {result['glama_version']}, "
                  f"this repository declares {declared_version}")
        if verdict["outcome"] == "match":
            print("✅ Glama listing matches what this repository publishes")
        elif verdict["outcome"] == "mismatch":
            print("❌ Glama listing does not match what this repository publishes")
        else:
            print("⚠️  The probe could not answer — Glama was not asked, so nothing is claimed")

    if verdict["outcome"] == "match":
        return 0
    if verdict["outcome"] == "mismatch":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
