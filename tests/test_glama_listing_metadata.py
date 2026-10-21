#!/usr/bin/env python3
"""The Glama listing's facts, pinned offline — and a probe that can say "could not answer".

Issue [#3644](https://github.com/Ikalus1988/MisakaNet/issues/3644) reported that Glama's
connector page showed "Last updated September 17, 2026" while the repository was already at
v2.48.0. Two of the four things that issue asked for need a Glama account and are therefore
not repository work: confirming the listing's ownership/claim state in Glama's backend, and
requesting a rescan. The two that *are* repository work are here:

* **the trigger that worked is written down** — `docs/integrations/glama-listing.md`, linked
  from the Glama row of `docs/integrations/status.md`, so the next reader does not have to
  guess again;
* **the version is verified by the probe** — `scripts/verify-glama-listing.py` now compares the
  version Glama publishes against the version this repository declares, and it distinguishes
  three outcomes instead of two.

Why the version needed a gate at all
------------------------------------
The two manifests that carry the listing's version were never compared with each other:
`glama.json` and `docs/.well-known/glama.json` (the copy the site serves) both said `2.48.0`
and `package.json` said `2.48.0`, and that agreement was a coincidence, not a rule. A release
that bumped one and not the other would have shipped a listing advertising a version the
repository does not have, and nothing in CI could see it. `version_problems()` below is that
missing rule.

Why "could not answer" needed its own outcome
---------------------------------------------
Glama's JSON API answers `401 unauthorized` — "This endpoint requires an API key" — measured
2026-10-22. The probe used to swallow that with `except Exception: pass` and fall back to
scraping the web page, matching `misakanet_([a-z]\\w*)` **anywhere** in the HTML. That scrape
matched tool names out of the repository README (`misakanet_cli` out of `scripts/misakanet_cli.py`)
and out of a tool *description* (`misakanet_get_my_events`, the old name the
`misakanet_me_events` description mentions), so it reported **13** advertised tools where the
listing actually advertises **11**. Worse, "we could not ask" and "we asked and it is wrong"
both ended in "not healthy", so the probe could not tell a service outage from a real defect.

`tests/test_registry_drift_watch_reports.py` already pins the consequence on the workflow
side — exit 2 must stay distinguishable from 0 and 1, because the issue branch keys on exactly
1. This file pins it on the probe side: the decision is made by `compare()`, a pure function,
and every test here injects a listing instead of reaching for the network.

**Every test in this file is offline.** The one thing the probe cannot read from the
repository is the listing itself, so the listing is the one thing a test hands over. A gate
that depends on glama.ai being up is a gate that fails for somebody else's outage, and this
repository has already been burned by one.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from datetime import date
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
DETECTOR = REPO / "scripts" / "verify-glama-listing.py"
PLAYBOOK = REPO / "docs" / "integrations" / "glama-listing.md"
STATUS = REPO / "docs" / "integrations" / "status.md"

LISTING_URL = "https://glama.ai/mcp/servers/Ikalus1988/MisakaNet"

#: The playbook's "when did somebody last look at this" line. A playbook without a date is a
#: playbook whose facts decay silently.
LAST_REVIEWED = re.compile(r"^>\s*Last reviewed:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)

#: The heading that holds the trigger. The playbook is worthless if it does not say which step
#: actually refreshes the listing, and worse than worthless if it says "it depends".
TRIGGER_HEADING = re.compile(r"^##\s+.*\btrigger\b.*$", re.M | re.I)


def _load_probe(path: Path = DETECTOR) -> ModuleType:
    """`scripts/verify-glama-listing.py` as a module.

    The filename is not importable the ordinary way (hyphens), and its `main()` is behind
    `if __name__ == "__main__"`, so loading it has no side effect.
    """
    spec = importlib.util.spec_from_file_location("verify_glama_listing_probe", path)
    assert spec and spec.loader, f"{path} could not be loaded as a module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── the rules, written so they can be driven against a scratch copy ─────────────────────────────


def version_problems(root: Path) -> list[str]:
    """Where the listing's version line disagrees with itself.

    * `glama.json`'s version must equal `package.json`'s — the listing and the package are one
      release, and release-please bumps both.
    * `docs/.well-known/glama.json` (the copy the site serves) must carry the same version as
      the root manifest — a reader who fetches the served card and a reader who reads the
      repository must not be told different versions.

    The two files are deliberately *not* identical (the served card uses Glama's connector
    schema and carries a maintainer e-mail where the manifest carries a GitHub handle), so the
    rule compares the identity and the version, not the bytes.
    """
    manifest = json.loads((root / "glama.json").read_text(encoding="utf-8"))
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    served = json.loads((root / "docs" / ".well-known" / "glama.json").read_text(encoding="utf-8"))

    problems = []
    if manifest["version"] != package["version"]:
        problems.append(
            f"glama.json says {manifest['version']} and package.json says {package['version']} — "
            f"one release, two numbers"
        )
    if served["version"] != manifest["version"]:
        problems.append(
            f"docs/.well-known/glama.json says {served['version']} and glama.json says "
            f"{manifest['version']} — the copy the site serves is behind the manifest"
        )
    if served["name"] != manifest["name"]:
        problems.append(
            f"docs/.well-known/glama.json names {served['name']} and glama.json names "
            f"{manifest['name']} — they are two listings then"
        )
    return problems


def status_problems(root: Path) -> list[str]:
    """The status page must name the listing and point at the playbook that says how to fix it.

    A row that links the listing but not the playbook leaves the next reader with a third-party
    URL and no procedure — which is the state this issue was filed in.
    """
    text = (root / "docs" / "integrations" / "status.md").read_text(encoding="utf-8")
    problems = []
    if LISTING_URL not in text:
        problems.append(f"docs/integrations/status.md does not name the listing {LISTING_URL}")
    if "glama-listing.md" not in text:
        problems.append(
            "docs/integrations/status.md does not link the Glama listing playbook "
            "(glama-listing.md), so the row sends the reader to a third-party URL and nowhere else"
        )
    return problems


def _section(text: str, heading: re.Match[str]) -> str:
    """The body of the section a heading match opens, up to the next `## ` heading."""
    start = heading.end()
    following = re.search(r"^##\s", text[start:], re.M)
    return text[start:start + following.start()] if following else text[start:]


def playbook_problems(root: Path) -> list[str]:
    """The playbook must be a record, not a placeholder.

    Three things it has to carry, and each one is a way the page could rot:

    * a **dated review**, so a reader can tell how old the facts are;
    * a **concrete trigger** — a heading about the trigger, with a body that names a place to
      act, rather than an empty section that says "ask Glama";
    * the **mechanism** behind "a rescan will not change the tool set" — the Dockerfile. If
      that sentence is ever true for a different reason, the page must be rewritten, and this
      rule is what says so.
    """
    path = root / "docs" / "integrations" / "glama-listing.md"
    if not path.is_file():
        return ["docs/integrations/glama-listing.md does not exist — the playbook is the record "
                "of what actually refreshes the listing"]

    text = path.read_text(encoding="utf-8")
    problems = []

    reviewed = LAST_REVIEWED.search(text)
    if reviewed is None:
        problems.append(
            "docs/integrations/glama-listing.md has no '> Last reviewed: YYYY-MM-DD' line, so a "
            "reader cannot tell how old the measurements in it are"
        )
    else:
        try:
            date.fromisoformat(reviewed.group(1))
        except ValueError:
            problems.append(
                f"docs/integrations/glama-listing.md says 'Last reviewed: "
                f"{reviewed.group(1)}', which is not a date"
            )

    heading = TRIGGER_HEADING.search(text)
    if heading is None:
        problems.append(
            "docs/integrations/glama-listing.md has no section about the trigger — the issue "
            "asked for the step that actually refreshes the listing to be written down"
        )
    else:
        body = _section(text, heading)
        if len(body.strip()) < 200:
            problems.append(
                "the trigger section of docs/integrations/glama-listing.md is empty or a "
                "placeholder — it has to say which step to press"
            )
        if "glama.ai" not in body:
            problems.append(
                "the trigger section of docs/integrations/glama-listing.md names no place to act "
                "(no glama.ai URL or control), so it cannot be followed"
            )

    if LISTING_URL not in text:
        problems.append(
            f"docs/integrations/glama-listing.md does not name the listing {LISTING_URL}"
        )
    if "Dockerfile" not in text:
        problems.append(
            "docs/integrations/glama-listing.md does not mention the Dockerfile — the reason a "
            "rescan cannot change the tool set is that Glama introspects what the Dockerfile "
            "starts, and a page that drops the mechanism becomes a claim with no evidence"
        )
    return problems


# ── the repository-side rules ───────────────────────────────────────────────────────────────────


def test_the_listing_version_is_one_version_across_the_manifest_the_package_and_the_served_card():
    problems = version_problems(REPO)
    assert not problems, "\n".join(problems)


def test_the_status_page_names_the_listing_and_links_the_playbook():
    problems = status_problems(REPO)
    assert not problems, "\n".join(problems)


def test_the_playbook_is_a_dated_record_with_a_concrete_trigger():
    problems = playbook_problems(REPO)
    assert not problems, "\n".join(problems)


# ── the rules can go red ────────────────────────────────────────────────────────────────────────


def _scratch_repo(tmp_path: Path) -> Path:
    """A copy of the files the three rules read, so a mutation cannot touch the checkout."""
    root = tmp_path / "repo"
    for rel in ("glama.json", "package.json",
                "docs/.well-known/glama.json",
                "docs/integrations/status.md",
                "docs/integrations/glama-listing.md"):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, target)
    return root


def test_the_version_rule_notices_a_manifest_that_moved_without_the_package(tmp_path):
    """Guard the guard: a rule that cannot fail is a comment.

    The copy starts clean, so a finding below can only come from the mutation.
    """
    root = _scratch_repo(tmp_path)
    assert version_problems(root) == [], "the copied tree must start clean"

    manifest = root / "glama.json"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            json.loads(manifest.read_text(encoding="utf-8"))["version"], "0.0.1", 1),
        encoding="utf-8",
    )
    problems = version_problems(root)
    assert problems, "a glama.json that moved without package.json must be reported"
    assert any("glama.json" in problem for problem in problems), problems


def test_the_version_rule_notices_a_served_card_that_moved_without_the_manifest(tmp_path):
    root = _scratch_repo(tmp_path)
    assert version_problems(root) == [], "the copied tree must start clean"

    served = root / "docs" / ".well-known" / "glama.json"
    data = json.loads(served.read_text(encoding="utf-8"))
    data["version"] = "0.0.1"
    served.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    problems = version_problems(root)
    assert problems, "a served card behind the manifest must be reported"
    assert any(".well-known" in problem for problem in problems), problems


def test_the_status_rule_notices_a_row_that_no_longer_links_the_playbook(tmp_path):
    root = _scratch_repo(tmp_path)
    assert status_problems(root) == [], "the copied tree must start clean"

    status = root / "docs" / "integrations" / "status.md"
    status.write_text(
        status.read_text(encoding="utf-8").replace("glama-listing.md", ""), encoding="utf-8"
    )
    problems = status_problems(root)
    assert problems, "a Glama row that links no playbook must be reported"
    assert any("glama-listing.md" in problem for problem in problems), problems


def test_the_playbook_rule_notices_an_empty_trigger_section(tmp_path):
    root = _scratch_repo(tmp_path)
    assert playbook_problems(root) == [], "the copied tree must start clean"

    playbook = root / "docs" / "integrations" / "glama-listing.md"
    text = playbook.read_text(encoding="utf-8")
    heading = TRIGGER_HEADING.search(text)
    assert heading is not None, "the fixture playbook must have a trigger heading"
    body_start = heading.end()
    following = re.search(r"^##\s", text[body_start:], re.M)
    body_end = body_start + following.start() if following else len(text)
    playbook.write_text(text[:body_start] + "\n\n" + text[body_end:], encoding="utf-8")

    problems = playbook_problems(root)
    assert problems, "an empty trigger section must be reported"
    assert any("trigger" in problem for problem in problems), problems


def test_the_playbook_rule_notices_a_review_date_that_is_not_a_date(tmp_path):
    root = _scratch_repo(tmp_path)
    assert playbook_problems(root) == [], "the copied tree must start clean"

    playbook = root / "docs" / "integrations" / "glama-listing.md"
    playbook.write_text(
        playbook.read_text(encoding="utf-8").replace(
            LAST_REVIEWED.search(playbook.read_text(encoding="utf-8")).group(1), "last Tuesday", 1
        ),
        encoding="utf-8",
    )
    problems = playbook_problems(root)
    assert problems, "a review line that is not a date must be reported"
    assert any("Last reviewed" in problem for problem in problems), problems


# ── the probe's three outcomes, decided offline ─────────────────────────────────────────────────


def _probe_tree(tmp_path: Path, *replacements: tuple[str, str]) -> ModuleType:
    """A copy of the probe, with `replacements` applied, over a copy of the files it reads.

    The probe resolves the repository from its own location, so the copy needs the three files
    it reads: the worker, the stdio server's tool list and `glama.json`.
    """
    root = tmp_path / "repo"
    for rel in ("workers/register-proxy-sw.js", "misakanet/server/tools.py", "glama.json"):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, target)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    target = root / "scripts" / "verify-glama-listing.py"

    text = DETECTOR.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, f"the mutation {old!r} did not apply — the probe's shape moved"
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")
    return _load_probe(target)


def _listing(tools: list[str], version: str) -> dict:
    """A listing as Glama would answer it, handed to the probe instead of fetched."""
    return {
        "tools": sorted(tools),
        "version": version,
        "inspected_version": None,
        "inspected_at": None,
        "scored_at": None,
        "error": None,
        "source": "api",
    }


def _worker_tools() -> list[str]:
    return [f"misakanet_{name}" for name in _load_probe().get_local_tools()]


def test_a_probe_that_could_not_answer_says_so_and_exits_two(capsys):
    """The shape the old probe could not express: Glama did not answer, so nothing is claimed.

    The API answers 401 without a key (measured 2026-10-22), so this is the path a probe
    actually takes today — and it must not be reported as a mismatch, or a Glama outage sends
    a maintainer to re-publish a correct listing.
    """
    probe = _load_probe()
    listing = {
        "tools": [], "version": None, "inspected_version": None, "inspected_at": None,
        "scored_at": None, "source": None,
        "error": "the API answered HTTP 401: it requires an API key",
    }

    verdict = probe.compare(_worker_tools(), probe.get_declared_version(), listing)
    assert verdict["outcome"] == "cannot-answer", verdict
    assert verdict["stale_on_glama"] == [], "nothing was compared, so nothing is stale"

    assert probe.main([], listing=listing) == 2, "a probe that could not answer exits 2"
    printed = capsys.readouterr().out
    assert "could not answer" in printed, printed


def test_a_matching_listing_exits_zero(capsys):
    probe = _load_probe()
    listing = _listing(_worker_tools(), probe.get_declared_version())

    assert probe.compare(_worker_tools(), probe.get_declared_version(), listing)["outcome"] == "match"
    assert probe.main([], listing=listing) == 0
    assert "matches" in capsys.readouterr().out


def test_a_listing_that_advertises_a_tool_the_worker_does_not_serve_exits_one(capsys):
    probe = _load_probe()
    tools = sorted(set(_worker_tools()) | {"misakanet_usage_status"})
    listing = _listing(tools, probe.get_declared_version())

    verdict = probe.compare(_worker_tools(), probe.get_declared_version(), listing)
    assert verdict["outcome"] == "mismatch", verdict
    assert verdict["stale_on_glama"] == ["misakanet_usage_status"], verdict
    assert probe.main([], listing=listing) == 1
    assert "Stale on Glama" in capsys.readouterr().out


def test_a_listing_that_is_missing_a_core_tool_exits_one():
    probe = _load_probe()
    tools = [name for name in _worker_tools() if name != "misakanet_search"]
    listing = _listing(tools, probe.get_declared_version())

    verdict = probe.compare(_worker_tools(), probe.get_declared_version(), listing)
    assert verdict["outcome"] == "mismatch", verdict
    assert verdict["missing_core_tools"] == ["misakanet_search"], verdict


def test_a_listing_that_is_missing_a_tool_the_worker_serves_exits_one():
    probe = _load_probe()
    tools = [name for name in _worker_tools() if name != "misakanet_me_inbox"]
    listing = _listing(tools, probe.get_declared_version())

    verdict = probe.compare(_worker_tools(), probe.get_declared_version(), listing)
    assert verdict["outcome"] == "mismatch", verdict
    assert verdict["missing_from_glama"] == ["misakanet_me_inbox"], verdict


def test_a_listing_that_publishes_an_older_version_exits_one():
    """The version half of the comparison — the half the probe did not make before.

    The tool set can be perfect while the version behind it is stale: that is exactly what
    issue #3644 is about, and a probe that only compared tool names could not see it.
    """
    probe = _load_probe()
    listing = _listing(_worker_tools(), "0.0.1")

    verdict = probe.compare(_worker_tools(), probe.get_declared_version(), listing)
    assert verdict["outcome"] == "mismatch", verdict
    assert verdict["version_ok"] is False, verdict


def test_a_listing_that_publishes_a_newer_version_is_not_a_mismatch():
    """Glama may know about a release this repository has not published yet. That is not drift."""
    probe = _load_probe()
    listing = _listing(_worker_tools(), "99.0.0")

    verdict = probe.compare(_worker_tools(), probe.get_declared_version(), listing)
    assert verdict["outcome"] == "match", verdict
    assert verdict["version_ok"] is True, verdict


# ── the probe's mutations go red ─────────────────────────────────────────────────────────────────


def test_a_probe_that_reported_could_not_answer_as_a_mismatch_would_be_caught(tmp_path):
    """Guard the guard: the outcome this file exists for must be able to lose.

    The mutation is the shape that shipped — one boolean for "not healthy" — reduced to the
    smallest version of itself: "we could not ask" becomes "the listing is wrong".
    """
    probe = _probe_tree(tmp_path, (
        '    if not advertised or not advertised_version:\n'
        '        return {\n'
        '            "outcome": "cannot-answer",',
        '    if not advertised or not advertised_version:\n'
        '        return {\n'
        '            "outcome": "mismatch",',
    ))
    listing = {"tools": [], "version": None, "error": "the API answered HTTP 401"}
    verdict = probe.compare(_worker_tools(), "2.48.0", listing)
    assert verdict["outcome"] == "mismatch", "the mutation was supposed to change the outcome"
    assert probe.main([], listing=listing) == 1, "and with it the exit code"


def test_a_probe_without_the_version_check_would_not_see_a_stale_version(tmp_path):
    """The version comparison must be load-bearing, not decoration."""
    probe = _probe_tree(tmp_path, (
        "    version_ok = published >= declared",
        "    version_ok = True",
    ))
    verdict = probe.compare(_worker_tools(), "2.48.0", _listing(_worker_tools(), "0.0.1"))
    assert verdict["outcome"] == "match", "the mutation was supposed to drop the version check"
    assert verdict["version_ok"] is True


def test_a_probe_with_the_old_prose_scrape_would_report_a_tool_that_is_not_advertised(tmp_path):
    """The scrape is what made "13 advertised" out of 11.

    The old pattern matched `misakanet_([a-z]\\w*)` anywhere in the page; the new one reads
    the tool cards' own ids. This mutation puts the old pattern back and checks that it
    over-counts — so the fixture page below is known to be one the old pattern gets wrong.
    """
    probe = _probe_tree(tmp_path, (
        'TOOL_CARD = re.compile(r\'<details[^>]*\\bid="(misakanet_[a-z0-9_]+)"\')',
        'TOOL_CARD = re.compile(r"misakanet_([a-z0-9_]+)")',
    ), (
        "    tools = sorted(set(TOOL_CARD.findall(html)))",
        "    tools = sorted({f\"misakanet_{name}\" for name in TOOL_CARD.findall(html)})",
    ))
    tools = probe.listing_from_page(FIXTURE_PAGE)["tools"]
    assert "misakanet_cli" in tools, (
        "the old pattern must over-count on this fixture — otherwise the fixture does not "
        "demonstrate the false positive it exists to demonstrate"
    )
    assert "misakanet_usage_status" in tools, "the same for a name the README mentions"


# ── the page parser ─────────────────────────────────────────────────────────────────────────────

#: A listing page, in the shape the live page has. The flat record array is the live page's
#: shape renumbered so the fixture stays small: on the live page (measured 2026-10-22)
#: `flat[3163] == "latestRelease"`, `flat[3164] == {"_3172": 3173}`,
#: `flat[3172] == "version"` and `flat[3173] == "2.48.0"`. The values are indexed once and an
#: object's key is written `_` plus the index of the key string.
FIXTURE_FLAT = [
    {"_1": 2},
    "latestRelease",
    {"_3": 4},
    "version",
    "2.48.0",
]

#: The page. Two of the names below appear only in prose — one in a README bullet, one in a
#: tool description quoting an old name — and neither is a tool Glama advertises. The old
#: scrape counted both.
FIXTURE_PAGE = (
    "<html><body>"
    "<p>From the README: run <code>python3 scripts/misakanet_cli.py smoke</code>, and check "
    "<code>misakanet_usage_status</code> for the quota.</p>"
    "<details id=\"misakanet_search\"><summary>search</summary></details>"
    "<details id=\"misakanet_get_lesson\"><summary>get_lesson</summary></details>"
    "<details id=\"misakanet_me_events\"><summary>me_events</summary></details>"
    "<h2>Tool Schema Changelog</h2>"
    "<span><code>v<!-- -->2.43.0</code></span>"
    "<time dateTime=\"2026-10-15T16:44:56.961170Z\">Oct 15, 2026</time>"
    "<p>Scored<!-- --> <time dateTime=\"2026-10-16T21:15:25.208460Z\">2026-10-16 21:15</time>"
    "<!-- -->across<!-- -->11<!-- -->tools</p>"
    "<script>window.__reactRouterContext.streamController.enqueue("
    + json.dumps(json.dumps(FIXTURE_FLAT))
    + ");</script>"
    "</body></html>"
)


def test_the_page_parser_reads_the_tool_cards_and_not_the_prose():
    """The advertised tool set is the set of tool cards, not every name on the page.

    Two names on the fixture page exist only in prose. Reading them as advertised tools is how
    the old probe reported 13 tools for a listing that advertises 11.
    """
    probe = _load_probe()
    answer = probe.listing_from_page(FIXTURE_PAGE)

    assert answer["tools"] == [
        "misakanet_get_lesson", "misakanet_me_events", "misakanet_search",
    ], answer["tools"]
    assert answer["error"] is None, answer["error"]


def test_the_page_parser_reads_the_version_the_listing_publishes():
    probe = _load_probe()
    answer = probe.listing_from_page(FIXTURE_PAGE)
    assert answer["version"] == "2.48.0", answer
    assert answer["inspected_version"] == "2.43.0", answer
    assert answer["inspected_at"] == "2026-10-15T16:44:56.961170Z", answer
    assert answer["scored_at"] == "2026-10-16T21:15:25.208460Z", answer


def test_the_page_parser_reports_no_version_when_the_page_carries_none():
    """No version is not the same as an old version, and it is not a mismatch either."""
    probe = _load_probe()
    page = FIXTURE_PAGE.replace(json.dumps(json.dumps(FIXTURE_FLAT)), "")
    answer = probe.listing_from_page(page)
    assert answer["version"] is None, answer
    assert answer["tools"], "the tool cards are still readable without the record array"


def test_the_page_parser_reports_an_unreadable_page_instead_of_an_empty_tool_list():
    """A page that is not a listing must be reported, not returned as "no tools advertised".

    "No tools" and "we could not read the page" are different facts, and the second one must
    not be turned into a mismatch.
    """
    probe = _load_probe()
    answer = probe.listing_from_page("<html><body>nothing here</body></html>")
    assert answer["tools"] == [], answer
    assert answer["error"], "an unreadable page must carry a reason"
