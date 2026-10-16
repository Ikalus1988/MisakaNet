#!/usr/bin/env python3
"""The funnel's event set is closed, and nothing that reaches it came from the request.

Why this is a static test rather than a `doctor.py` check
---------------------------------------------------------
It has no deployment to talk to. `doctor.py`'s contract is "does this deployment answer" (config,
core, remote, deployed-version, deploy-freshness), and every flag added there has to be registered in
`FLAG_CHECKS`, `LOCAL_ONLY` and `tests/test_doctor_reach.py` as well. A drift rule that is checkable
from the source belongs where it runs on *every* PR — which is what `tests/test_d1_counters_schema.py`
(worker SQL ↔ schema) and `tests/test_unsolved_map.py` (worker source ↔ privacy claim) do.

The four things this pins
-------------------------
1. **The event set is closed.** Every `bumpCounter(env, "funnel", …)` in the worker must name a
   literal from `FUNNEL_EVENTS`, and every member of that list must have a write site. A new event
   name is a decision about what the funnel *means*, so it has to be made here as well as in the
   worker — otherwise the reader and the writer drift and the series silently loses a column.
2. **No identity at a write site.** The arguments of every funnel write are scanned for the four
   names the worker already uses to identify a caller (`clientIp`, `args.client_id`, `clientHint`,
   `authToken`, `X-MisakaNet-Client`, `request.headers`). The design reason is in the worker next to
   `FUNNEL_EVENTS`: `first_search` and a per-visitor `drop_off` need exactly those values, which is
   why they are retired and derived instead of implemented.
3. **No bucket that needs an identifier, anywhere.** `first_search` and `drop_off` must not appear as
   a bucket of any scope. `drop_off` has no per-visitor form and is computed at read time from two
   day-level integers; a bucket with that name is how somebody would try to store the connection the
   design refuses to make.
4. **The document names the same five events.** `docs/analytics/first-call-funnel.md` is the only
   place the funnel is described to a reader, and it described four metrics pointing at an
   implementation (`hub/master/master_api.py`, Grafana) that no longer exists. A doc and a code path
   that disagree about what is measured is the same defect class as a hand-written lesson count.

What it deliberately cannot see
--------------------------------
A caller-supplied value laundered through a local variable (`const b = args.client_id; bumpCounter(env,
"funnel", b, …)`) is caught only because the bucket then is not a literal — the value itself is beyond
a source scan. That is the honest limit of this check, and it is why the write sites carry the
reasoning in prose as well.

Every check below has a red fixture, because a gate nobody has watched fail is a gate that may not be
testing anything (`tests/test_referral_server_side.py` and `docs/agents/repo-operations.md` state the
rule).
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKER = REPO / "workers" / "register-proxy-sw.js"
DOC = REPO / "docs" / "analytics" / "first-call-funnel.md"

# The closed set. Adding a member is a product decision; it must be changed here, in
# `FUNNEL_EVENTS`, and in the document, in one commit.
APPROVED = ("visit", "register", "authorize", "pair", "search")

# Names the worker uses to identify a caller. A funnel write that mentions one of these is a funnel
# write that can be traced to somebody, which is the one property the whole design exists to avoid.
FORBIDDEN_IN_WRITE = (
    "clientIp",
    "args.client_id",
    "clientHint",
    "authToken",
    "X-MisakaNet-Client",
    "request.headers",
)

# Bucket names that would have to carry an identifier (or a cross-request join) to mean anything.
IDENTITY_BUCKETS = ("first_search", "drop_off")

_FUNNEL_CALL = re.compile(
    r'bumpCounter\(\s*env\s*,\s*"funnel"\s*,\s*(?:"(?P<literal>[a-z_]+)"|(?P<expr>[A-Za-z_$][\w$]*))'
)
_ANY_BUCKET = re.compile(r'bumpCounter\(\s*env\s*,\s*"([a-z_]+)"\s*,\s*"([a-z_]+)"')
_DECLARED = re.compile(r"const FUNNEL_EVENTS = Object\.freeze\(\[(.*?)\]\)", re.DOTALL)


def _call_arguments(source: str, open_paren: int) -> str:
    """The arguments of the call whose `(` sits at `open_paren`, by parenthesis balance.

    The arguments rather than "the line this is on": the register write is formatted across three
    lines, and a line-based rule would either miss its arguments or swallow the statement after it.
    """
    depth = 0
    for i in range(open_paren, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[open_paren + 1:i]
    return source[open_paren:]


def funnel_write_sites(source: str) -> list[dict]:
    """Every `bumpCounter(env, "funnel", …)` call, with its bucket and its arguments.

    `bucket` is `None` when the third argument is an expression rather than a string literal.
    """
    sites = []
    for match in _FUNNEL_CALL.finditer(source):
        open_paren = source.index("(", match.start())
        sites.append({
            "bucket": match.group("literal"),
            "expression": match.group("expr"),
            "arguments": _call_arguments(source, open_paren),
        })
    return sites


def check_worker_source(source: str) -> list[str]:
    """Problems with the worker's funnel writes; empty means clean."""
    problems: list[str] = []
    sites = funnel_write_sites(source)
    buckets = [site["bucket"] for site in sites]

    if len(sites) != len(APPROVED):
        problems.append(
            f"expected one write site per event ({list(APPROVED)}), found {len(sites)}: "
            f"{[site['bucket'] or site['expression'] for site in sites]}")

    for site in sites:
        if site["bucket"] is None:
            problems.append(
                "a funnel bucket must be a literal from the event set, not the expression "
                f"`{site['expression']}` — an expression is how a caller-supplied value becomes a key")
            continue
        if site["bucket"] not in APPROVED:
            problems.append(f"`{site['bucket']}` is written to the funnel but is not an approved event")
        for token in FORBIDDEN_IN_WRITE:
            if token in site["arguments"]:
                problems.append(
                    f"the `{site['bucket']}` write mentions `{token}`, which identifies the caller")

    missing = [event for event in APPROVED if event not in buckets]
    if missing:
        problems.append(f"declared in the event set but never written: {missing}")

    declared = _DECLARED.search(source)
    if not declared:
        problems.append("`FUNNEL_EVENTS` is not declared, so the event set has no single source")
    else:
        names = re.findall(r'"([a-z_]+)"', declared.group(1))
        if names != list(APPROVED):
            problems.append(f"`FUNNEL_EVENTS` is {names}, not {list(APPROVED)}")

    for scope, bucket in _ANY_BUCKET.findall(source):
        if bucket in IDENTITY_BUCKETS:
            problems.append(
                f"`{bucket}` is written as a bucket of scope `{scope}`; it needs an identifier "
                "(or a cross-request join) to mean anything, so it must stay derived at read time")

    return problems


def check_funnel_doc(text: str) -> list[str]:
    """Problems with the funnel document; empty means clean."""
    problems: list[str] = []
    for stale in ("hub/master/master_api.py", "Grafana", "docs/data/feed.json"):
        if stale in text:
            problems.append(f"the document still points at the migrated-away implementation: {stale}")

    # `funnel.visit` / `funnel.register` / `funnel.search` / `funnel.drop_off` / `funnel.authorize`
    # / `funnel.pair` — the document's names for the code's events, plus where the numbers come from.
    required = tuple(f"funnel.{event}" for event in APPROVED) + (
        "/api/funnel", "workers/register-proxy-sw.js",
    )
    for name in required:
        if name not in text:
            problems.append(f"the document never names {name}, so a reader cannot find the code")

    for line in text.splitlines():
        if "first_search" in line and "retired" not in line.lower():
            problems.append(f"`first_search` is still presented as a live metric: {line.strip()}")
        if "funnel.drop_off" in line and "derived" not in line.lower():
            problems.append(
                f"`funnel.drop_off` must be documented as derived at read time: {line.strip()}")

    return problems


# ── the real files ────────────────────────────────────────────────────────────────────────────────

def test_the_worker_writes_only_approved_funnel_events():
    problems = check_worker_source(WORKER.read_text(encoding="utf-8"))
    assert problems == [], "\n  - " + "\n  - ".join(problems)


def test_every_event_has_a_write_site_and_the_reader_enumerates_the_same_set():
    source = WORKER.read_text(encoding="utf-8")
    assert len(funnel_write_sites(source)) == len(APPROVED)
    # The reader must not carry its own copy of the list: one constant, or the two halves drift.
    reader = source[source.index("async function readFunnelDay("):]
    assert "FUNNEL_EVENTS.map" in reader, "readFunnelDay must enumerate FUNNEL_EVENTS"


def test_the_funnel_and_its_document_name_the_same_events():
    doc = DOC.read_text(encoding="utf-8")
    problems = check_funnel_doc(doc)
    assert problems == [], "\n  - " + "\n  - ".join(problems)
    for event in APPROVED:
        assert f'"{event}"' in WORKER.read_text(encoding="utf-8"), f"{event} is not in the worker"
        assert f"funnel.{event}" in doc, f"{event} is not in the document"


# ── red fixtures: the same checks must reject the shapes they exist for ───────────────────────────

def test_red_fixture_a_renamed_event_fails_the_worker_check():
    source = WORKER.read_text(encoding="utf-8")
    broken = source.replace('"visit"', '"first_search"')
    assert broken != source
    assert check_worker_source(broken), "the gate must go red when an event is renamed in place"


def test_red_fixture_a_derived_metric_turned_into_a_bucket_fails_the_worker_check():
    source = WORKER.read_text(encoding="utf-8")
    broken = re.sub(r'"funnel", "pair"', '"funnel", "drop_off"', source, count=1)
    assert broken != source, "the fixture must actually change the source"
    assert check_worker_source(broken), "`drop_off` must never be storable as a bucket"


def test_red_fixture_a_caller_value_in_a_write_fails_the_worker_check():
    source = WORKER.read_text(encoding="utf-8")
    broken = re.sub(r'(bumpCounter\(\s*env\s*,\s*"funnel"\s*,\s*"visit"\s*,\s*)day', r"\1clientIp",
                    source, count=1)
    assert broken != source, "the fixture must actually change the source"
    assert check_worker_source(broken), "a caller's address at a write site must be caught"


def test_red_fixture_a_non_literal_bucket_fails_the_worker_check():
    source = WORKER.read_text(encoding="utf-8")
    broken = re.sub(r'"funnel", "search"', '"funnel", args.query', source, count=1)
    assert broken != source, "the fixture must actually change the source"
    assert check_worker_source(broken), "a bucket computed from the request must be caught"


def test_red_fixture_a_stale_implementation_pointer_fails_the_doc_check():
    doc = DOC.read_text(encoding="utf-8")
    broken = doc.replace("### Implementation",
                         "### Implementation\n1. Track via hub/master/master_api.py registration endpoint")
    assert broken != doc
    assert check_funnel_doc(broken), "the document must not point at the implementation that moved"


def test_red_fixture_an_unretired_first_search_fails_the_doc_check():
    doc = DOC.read_text(encoding="utf-8")
    # A fresh line presenting it as a live metric — the shape the real document had before this
    # change. Editing an *existing* line would be a weaker fixture: the retirement note and the new
    # name share a line, so a careless edit can leave the check nothing to see.
    broken = doc.replace(
        "### Implementation",
        "- `funnel.first_search` — First MCP search executed\n\n### Implementation",
    )
    assert broken != doc
    assert check_funnel_doc(broken), "`first_search` must not read as a live metric anywhere"
