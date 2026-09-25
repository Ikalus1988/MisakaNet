#!/usr/bin/env python3
"""What `docs/mcp.md` says exists must be what the code registers — on the surface it names.

Issue #1901 reported that the page advertised "5 resources that do not exist" and a
`misakanet_submit_usage` tool that does not exist. Checked against the sources on 2026-09-25, **that is
not what is wrong**: `misakanet/server/resources.py` registers all five `misaka://` URIs and
`misakanet/server/tools.py` defines `misakanet_submit_usage`. The page documents the **local stdio**
server, and on that surface every name in it is real.

What *was* wrong is the reason the report exists at all: the page never said **which surface** it
describes. There are three, they have different sets, and the one most readers actually call —
`https://misakanet.org/mcp` — exposes **tools only**. A reader who takes the resources table and calls
`resources/list` on the hosted endpoint gets an error, which is the wrong mental model the reporter was
reaching for even though the specific claim was not accurate.

So this file pins the map, against the code, offline:

* every `misaka://` URI in the page is registered in `misakanet/server/resources.py`;
* every prompt name in the page exists in `misakanet/server/prompts.py`;
* every tool named in the page exists in `misakanet/server/tools.py` or the hosted worker's set;
* the local tool table is **complete** for the surface the page documents (a tool added to the code and
  not to the page fails here, which is the "doc drifts quietly" failure);
* and the page states the thing that was missing: the hosted endpoint has no resources and no prompts.

It parses rather than greps for the same reason the sibling gates do: the page *talks about* the names
it lists, so a substring search is satisfied by prose.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "mcp.md"
TOOLS = REPO / "misakanet" / "server" / "tools.py"
RESOURCES = REPO / "misakanet" / "server" / "resources.py"
PROMPTS = REPO / "misakanet" / "server" / "prompts.py"
WORKER = REPO / "workers" / "register-proxy-sw.js"

URI = re.compile(r"misaka://[a-z0-9/_-]+")


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


def table_rows(doc: str, heading: str) -> list[str]:
    """The table body under a `##` heading, header separator excluded."""
    start = doc.index(heading)
    end = doc.find("\n## ", start + 1)
    body = doc[start:end if end != -1 else len(doc)]
    rows = [line for line in body.splitlines() if line.startswith("|")]
    return [row for row in rows if not set(row) <= set("|-: ")]


def local_tool_names() -> set[str]:
    return set(re.findall(r'"name":\s*"(misakanet_[a-z_]+)"', TOOLS.read_text(encoding="utf-8")))


def registered_uris() -> set[str]:
    return set(re.findall(r'"uri":\s*"(' + URI.pattern + ')"', RESOURCES.read_text(encoding="utf-8")))


def prompt_names() -> set[str]:
    return set(re.findall(r'"name":\s*"([a-z_]+)"', PROMPTS.read_text(encoding="utf-8")))


def hosted_tool_names() -> set[str]:
    return set(re.findall(r'name:\s*"(misakanet_[a-z_]+)"', WORKER.read_text(encoding="utf-8")))


# ── the map, checked against the code ────────────────────────────────────────────────────────────

def test_every_documented_resource_is_registered(doc: str):
    documented = set(URI.findall(doc))
    assert documented, "the page no longer lists any misaka:// URI; fix this gate with the page"
    unknown = sorted(documented - registered_uris())
    assert not unknown, (
        f"docs/mcp.md advertises {unknown}, which misakanet/server/resources.py does not register. Either "
        f"register it or remove it from the page — a documented resource that does not exist teaches a "
        f"reader a mental model that fails on the first call"
    )


def test_every_registered_resource_is_documented(doc: str):
    """The other direction: a resource nobody can discover is not a feature."""
    missing = sorted(registered_uris() - set(URI.findall(doc)))
    assert not missing, f"misakanet/server/resources.py registers {missing}, undocumented in docs/mcp.md"


def test_every_documented_prompt_exists(doc: str):
    rows = table_rows(doc, "## Prompts")
    names = {re.match(r"\|\s*`([a-z_]+)`", row).group(1) for row in rows if re.match(r"\|\s*`([a-z_]+)`", row)}
    assert names, "the prompts table lost its rows; fix this gate with the page"
    unknown = sorted(names - prompt_names())
    assert not unknown, f"docs/mcp.md lists prompts {unknown} that misakanet/server/prompts.py does not define"


def test_every_documented_tool_exists_somewhere(doc: str):
    documented = set(re.findall(r"`(misakanet_[a-z_]+)`", doc))
    known = local_tool_names() | hosted_tool_names()
    unknown = sorted(documented - known)
    assert not unknown, (
        f"docs/mcp.md names {unknown}, which neither the local server's tools.py nor the hosted worker "
        f"implements"
    )


def test_the_local_surface_is_documented_completely(doc: str):
    """The page documents the local stdio server, so it has to list that server's tools.

    This is the direction that catches drift: adding a tool to `tools.py` without a line here fails,
    instead of shipping a page that is quietly a version behind the code.
    """
    documented = set(re.findall(r"`(misakanet_[a-z_]+)`", doc))
    missing = sorted(local_tool_names() - documented)
    assert not missing, (
        f"misakanet/server/tools.py defines {missing} and docs/mcp.md never names them. Add them to the "
        f"surface table (or remove them from the code)"
    )


def test_the_page_says_the_hosted_endpoint_has_no_resources_or_prompts(doc: str):
    """The fact whose absence produced #1901: the hosted endpoint is tools-only.

    Everything else about the page can be right and a reader still ends up calling `resources/list`
    against `misakanet.org/mcp`, because nothing told them the surfaces differ.
    """
    lowered = doc.lower()
    assert "hosted" in lowered, "the page no longer distinguishes the hosted endpoint"
    assert re.search(r"tools only", lowered), "the page no longer says the hosted endpoint is tools-only"
    assert re.search(r"no resources", lowered) or re.search(r"\*\*none\*\*", lowered), (
        "the page no longer says the hosted endpoint exposes no resources"
    )


def test_the_three_sets_are_actually_different():
    """Guard the guard: if the surfaces happened to be identical, this file would be pinning nothing."""
    local, hosted = local_tool_names(), hosted_tool_names()
    assert local and hosted, "one of the tool sets came back empty"
    assert local != hosted, "the local and hosted tool sets are now identical — re-check this gate"
    assert "misakanet_me_events" in hosted and "misakanet_me_events" not in local
    assert "misakanet_submit_usage" in local and "misakanet_submit_usage" not in hosted


def test_the_gate_can_go_red(doc: str):
    """A page that documents a resource nothing registers fails."""
    mutated = doc.replace("`misaka://docs/faq`", "`misaka://docs/nonexistent`")
    assert mutated != doc
    unknown = set(URI.findall(mutated)) - registered_uris()
    assert unknown == {"misaka://docs/nonexistent"}
