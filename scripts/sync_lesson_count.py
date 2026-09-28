#!/usr/bin/env python3
"""Lesson-count SSOT: keep every public "N lessons" claim equal to data/lessons.json.

Why this exists (2026-09-12)
----------------------------
The previous mechanism (``update_lessons_json.refresh_lesson_count_markers``,
audit QW6) substituted the literal number for each ``{{LESSONS_COUNT}}``
placeholder. Substitution *consumes* the placeholder, so the second run found
nothing left to replace and every managed count froze at its first
materialization:

    ARCHITECTURE.md  "358+ .md files"        (placeholder gone since 2026-09-05)
    README.md        "310+ failure lessons"
    docs/index.html  "435 indexed failure-recovery lessons"  (<meta description>
                      + og:description — the copy that appears in search results
                      and social cards)
    docs/search/…    "249 indexed failure-recovery lessons"

An SSOT that silently stops refreshing is worse than no SSOT: the tooling
advertises "counts cannot silently drift" while they drift by +15%.

This module is idempotent **by construction**: every managed site is a regex
whose numeric ``n`` group is re-matched on every run, so the tenth run is as
correct as the first. Two properties are pinned by
``tests/test_lesson_count_ssot.py``:

1. re-running with a *different* count rewrites the site again (no write-once);
2. a site whose wording changed is a **hard error**, never a silent skip —
   drift can throttle loudly instead of hiding.

Managed surfaces also normalise the trust vocabulary: ``verified failure
lessons`` is rewritten to ``indexed failure lessons`` because
``docs/trust-semantics.md`` reserves "verified" for manually fact-checked
lessons (✅ "N indexed failure-recovery lessons" / ❌ "N verified failure
lessons").

Deliberately NOT managed
------------------------
Historical snapshots keep the number they were written with: ``docs/blog/**``,
``docs/releases/**``, ``docs/reviews/**``, ``docs/prd/**``,
``docs/maintainer/handoff-*.md``, course bodies (``lessons/**``) and dated audit
reports. So does *testimony* (``docs/community/voices.json`` quotes a user
saying "200+ lessons") and any metric that is not the lesson total or the node
total (per-domain topic pages).

The **domain** count was unmanaged on purpose until 2026-09-28 (2026-09-15, issue
#1687): three different numbers were in play and none of them was wrong about the
thing it measured — ``docs/install/index.html`` said "18 domains" (the curated
``docs/domains/`` list), the ``domains`` badge counted raw frontmatter strings, and
a normalised count sat between them. Picking one was a product decision, so no gate
pretended otherwise. The product decision is now to **stop quoting a domain number
in prose at all**: ``llms.txt`` (and its served copy) keeps the one number that is
verifiable from the corpus, and the surfaces that used to advertise a different
domain figure — the install page, ``skill.md``, ``JOIN.md``, ``ROADMAP.md`` —
describe the coverage without a count. ``canonical_domains`` therefore still exists
and still owns two rows; what changed is who is allowed to quote it.

Registered nodes were managed here from 2026-09-15 (issue #1683) until
2026-09-26, and are **no longer published at all**. The gate was correct about
its own job — the same fact read 52+ (``docs/llms.txt``), 59 (a hardcoded
shields badge in ``README.zh-CN.md``) and 73 (``data/counter.json``) at once —
but the number it kept consistent was never a measurement of anything a reader
would take it for: ``data/counter.json`` ``current`` is a **monotonic allocation
counter** that node IDs are handed out from (the first node is Misaka10001),
nothing ever comes off it, and anonymous callers get a fresh node per call
(``AGENTS.md`` §3.3), so it grows with our own automation. It cannot show churn,
retention or adoption, and any surface quoting it invites exactly those
readings — the honest label ("node IDs issued") only moved the problem from a
false claim to a true number nobody needs.

So the five surfaces it was synced into carry no node count now, and the metric
is gone from this file: :data:`SITES` (lessons) and :data:`DOMAIN_SITES` are the
whole registry.

Two days later the *copies* of that number went too (2026-09-28): ``data/counter.json``,
``sync-node-counter.yml`` and ``scripts/node_status.py --mirror`` were deleted
together, and ``/api/counter`` stopped falling back to the file — it answers 503
``counter_unavailable`` when D1 and KV are both down. Retiring the surfaces left
the reason for the file intact (it was the endpoint's last resort), but the file
was the wrong shape for what the number is *for*: a registrant reads their id
immediately, so a mirror that can be months behind is worse than no answer. Issue
#1820 was filed because the ``data`` branch's copy sat frozen on 2026-06-01, and
``/api/counter``'s old default ref would have served it as current.

Count surfaces: three, not twenty-four (2026-09-28)
---------------------------------------------------
A correct sync over a surface that should not carry the number is still the wrong
shape: 38 rows across 24 files meant every surface anyone ever wrote a number into
became *our* maintenance liability, and the number was duplicated into contexts
(registry descriptions, fenced sample output, translated taglines) where a daily
commit is the only thing keeping it true. The registry is now three files —
``docs/index.html`` (its ``<meta>``/``og:`` copy and the no-JS body fallbacks),
``docs/llms.txt`` and its served ``.well-known`` copy — chosen because they are
**read without running anything**: crawlers and social cards never execute the JS
that fetches ``data/lessons.json``, and an agent reads ``llms.txt`` before it is
willing to make an MCP call, so both need a number that is present *in the bytes*.

Every other surface points instead of copying: GitHub-rendered markdown (the three
READMEs, ``ROADMAP.md``) carries the shields **dynamic badge**, which reads
``data/badges/lessons.json`` from the ``data`` branch — refreshed daily by
``update-badges.yml``, never committed to ``main``; prose, descriptions and sample
output name the source (``data/lessons.json`` / ``llms.txt``) rather than quoting
it. ``tests/test_lesson_count_ssot.py`` pins both directions: the registry may not
grow past its cap, and a de-numbered surface may not quietly acquire a corpus count
again (``gemini-cli.md`` had already drifted to "402 indexed failure lessons" with
no writer to notice, and ``README.zh-CN.md`` still published the retired **node**
badge from a file nothing writes any more).

The two ``update-badges.yml`` metrics that stay are the ones a badge can carry: the
badge reads the badge file, so the number is computed once, on a schedule, and
never lands in a document anyone edits.


Usage
-----
    python3 scripts/sync_lesson_count.py            # rewrite every managed site
    python3 scripts/sync_lesson_count.py --check     # CI gate: exit 1 on drift
    python3 scripts/sync_lesson_count.py --quiet
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_JSON = Path("data") / "lessons.json"
COUNT_FILE = Path("docs") / "_lessons_count.txt"
# The base that turns the allocation counter into the node id a registrant sees (Misaka10001 is
# 10000 + 1). It stayed here when the node *count* stopped being published: `scripts/register_issue.py`
# writes the number into the welcome comment and `docs/index.html` estimates it the same way, so the
# arithmetic still needs one home — it is simply no longer a gate input.
NODE_OFFSET = 10000


@dataclass(frozen=True)
class Site:
    """One managed count occurrence (or one family of identical occurrences).

    ``pattern`` must contain a named group ``n`` holding the count currently
    written in the file; ``replace`` is the re.Stemplate that writes the
    canonical count (may use ``\\g<k>`` backreferences and ``{n}``).
    ``min_matches`` guards against a partial loss of the surface (a meta tag
    quietly deleted) — it is a minimum, so adding another occurrence is fine.
    """

    path: str
    pattern: str
    replace: str
    note: str
    min_matches: int = 1

    def compiled(self) -> re.Pattern[str]:
        return re.compile(self.pattern, re.MULTILINE)


_COUNT = r"(?P<n>\d{2,4})"
# meta / og / JSON-LD scale claim: "435 indexed failure-recovery lessons". Only `docs/index.html`
# uses it now — the search page, mcp-quickstart and the issue templates point at the count instead
# (2026-09-28). The optional "+" is normalised away: the number is exact, and "N+" made two files
# disagree about the same claim.
_META = rf"{_COUNT}\+? indexed failure-recovery lessons"
_META_REPL = "{n} indexed failure-recovery lessons"
# "205+ verified failure lessons": the `\+?`/`(?:…)?` groups make the pattern
# match its own output ("378 indexed failure lessons"), which is what keeps the
# refresh idempotent. `tests/test_lesson_count_ssot.py` asserts that property for
# every row, so a row that cannot match its replacement fails before it ships.
_SCALE_CLAIM = rf"{_COUNT}\+? (?:verified |indexed )?failure lessons"


def _build_sites() -> tuple[Site, ...]:
    sites: list[Site] = []

    def add(path: str, pattern: str, replace: str, note: str, min_matches: int = 1) -> None:
        sites.append(Site(path, pattern, replace, note, min_matches))

    # ── repo-facing prose: badge, not a number (2026-09-28) ─────────────────
    # README.md / README.zh-CN.md / README.ja.md / ARCHITECTURE.md / ROADMAP.md / JOIN.md /
    # docs/skill.md / docs/mcp-quickstart.md / docs/integrations/*.md used to be registered rows
    # here. They are GitHub-rendered markdown, so the live number is the shields *dynamic badge*
    # (`data` branch `badges/lessons.json`, written daily by update-badges.yml) — a number that
    # cannot be stale because it is not in the bytes. The badge was already in README.md and
    # README.zh-CN.md for exactly this reason while the same files also hard-coded the total two
    # paragraphs above it; that contradiction ("418+" next to a badge reading 418, and in
    # `gemini-cli.md` a badge-less "402") is what this change removes.
    #
    # `docs/install/index.html` also left the registry: its feature list advertised both counts in
    # one sentence ("418+ lessons across 44 domains"), which is where the 2026-09-15 `\g<1>` bug
    # shipped ("393+ lessons across 393 domains", both numbers plausible) — see the module
    # docstring and `lessons/contrib/` for the write-up. With no number in the sentence the failure
    # mode is gone rather than guarded.

    # ── public website metadata (static: no JS can fix these) ───────────────
    add("docs/index.html", _META, _META_REPL,
        "<meta description> + og:description + JSON-LD (search/social copy)", 3)

    # ── website body fallbacks (JS overwrites them once data/lessons.json loads,
    #    but crawlers and no-JS readers only ever see the static text) ────────
    add("docs/index.html", rf'(<span id="lesson-count-(?:hero|product)">){_COUNT}\+?(</span>)',
        r"\g<1>{n}\g<3>", "hero + product count spans", 2)
    add("docs/index.html", rf'(id="lesson-count-search"[^>]*>){_COUNT} indexed lessons',
        r"\g<1>{n} indexed lessons", "search-panel fallback line")
    add("docs/index.html", rf"(_allLessons\.length : ){_COUNT}",
        r"\g<1>{n}", "JS fallback count shown before the index finishes loading")

    # ── agent-facing entry points ───────────────────────────────────────────
    # The only prose that keeps a literal count, and the reason is in the module docstring: an
    # agent reads this file *instead of* running something, so "how big is this corpus" has to be
    # answerable from the bytes. The served `.well-known` copy is registered as its own row (two
    # files, one logical surface) because static hosting has no way to alias it.
    add("docs/llms.txt", _SCALE_CLAIM, "{n} indexed failure lessons",
        "llms.txt scale claim (trust vocabulary enforced: indexed, not verified)")
    add("docs/.well-known/llms.txt", _SCALE_CLAIM, "{n} indexed failure lessons",
        "served copy of llms.txt")
    # `.well-known/{mcp,agent,agent-card,glama}.json`, `skill.md`, `JOIN.md`, the integration
    # guides, the two issue templates and `worker-bm25-search.md` were rows here until 2026-09-28.
    # Several were registered only *after* they were caught lying: the agent-discovery documents
    # advertised "300+ verified debugging lessons" (stale count *and* the vocabulary
    # docs/trust-semantics.md forbids); glama.json served "320+ …" at 380+ lessons; JOIN.md's
    # Version-Info block advertised "384+ lessons" next to a version two releases behind; README's
    # Glama section said "385+ verified failure-recovery lessons". Each fix added the file to this
    # registry — which is how the registry reached 24 files, one per incident. They now name the
    # source instead of quoting it, and `docs/integrations/gemini-cli.md` (never registered, and
    # found by the 2026-09-28 sweep still advertising "402 indexed failure lessons") is the
    # argument for that: a surface nobody wrote into the registry drifts with nothing to catch it.
    #
    # .github/workflows/pr-thank-you.yml is still deliberately NOT managed. It used to hardcode
    # "MisakaNet's 298+ lessons", but GITHUB_TOKEN is refused any push that touches
    # .github/workflows/** ("refusing to allow a GitHub App to create or update workflow ...
    # without `workflows` permission") — so managing it made the daily update job fail at push time
    # the first time a count actually changed (caught 2026-09-12 by dispatching that job). It reads
    # docs/_lessons_count.txt at runtime, which this script writes.

    return tuple(sites)


SITES: tuple[Site, ...] = _build_sites()


def _lesson_domain(path: Path) -> str:
    """The frontmatter `domain:` of one lesson, normalised (unquoted, lowercased)."""
    head = path.read_text(encoding="utf-8", errors="ignore")[:2000]
    as_json = re.match(r'\s*\{\s*"domain"\s*:\s*"([^"]+)"', head)
    if as_json:
        return as_json.group(1).strip().lower()
    found = re.search(r"(?m)^domain\s*:\s*(.+)$", head)
    if not found:
        return ""
    return found.group(1).strip().strip('"').strip("'").lower()


def canonical_domains(root: Path = REPO) -> int:
    """Distinct domains in the published corpus — and the definition, which is the point.

    Issue #1687: the same claim read 18 (``docs/install/index.html``, ``docs/skill.md``,
    ``JOIN.md``), 69 (the badge, which counted raw strings, so ``devops`` and ``"devops"``
    were two) and 61 (the same strings normalised). None was derivable from anything a reader
    could check.

    The definition now: the frontmatter ``domain`` values of the lessons we publish
    (``core``/``contrib``/``en``, READMEs excluded), unquoted and lowercased, counted once
    each. Whatever that number is, it is a fact about the corpus rather than a slogan, and the
    surfaces that quote it are gated on it. The taxonomy itself (an allowlist, synonyms, the
    dead ``data/synonyms.json`` copy) is separate work, tracked in the issue.
    """
    values: set[str] = set()
    for sub_dir in ("core", "contrib", "en"):
        for path in sorted((root / "lessons" / sub_dir).rglob("*.md")):
            if path.name == "README.md":
                continue
            value = _lesson_domain(path)
            if value:
                values.add(value)
    return len(values)


# The hosted endpoint's tool list lives in three places that nobody compared (#1822):
#   * `AGENTS.md` §3.2 — the table an agent reads before calling anything;
#   * `docs/mcp.md` — the same set, described by derivation from the stdio list;
#   * `workers/register-proxy-sw.js` — what actually answers `tools/list`.
# The badge job derived its expected value from the third one alone, so the count could not
# disagree with the file it measured, and could not notice that the file disagreed with the
# documents.
_MCP_TOOL_RE = re.compile(r"(misakanet_[a-z_]+)")
_AGENTS_TOOL_TABLE_HEADING = re.compile(r"(?m)^###\s+3\.2\s+工具清单")


def documented_hosted_tools(root: Path = REPO) -> frozenset[str]:
    """The hosted tools `AGENTS.md` §3.2 promises — the *expectation*, read from a document.

    Parsed from the table rather than from the ``（7 个）`` in the heading: the heading is a
    number a human retypes, so gating on it would only prove that two hand-written numbers
    agree with each other. A missing heading is an error, not an empty set — a reader that
    silently finds nothing is how a gate stops existing.
    """
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    start = _AGENTS_TOOL_TABLE_HEADING.search(text)
    if not start:
        raise ValueError("AGENTS.md has no §3.2 tool table — moving it means updating this reader")
    rest = text[start.end():]
    end = rest.find("\n### ")
    section = rest if end == -1 else rest[:end]
    names = set()
    for line in section.splitlines():
        if line.startswith("|") and line.count("|") >= 2:
            found = _MCP_TOOL_RE.search(line.split("|")[1])
            if found:
                names.add(found.group(1))
    if not names:
        raise ValueError("AGENTS.md §3.2 parsed to an empty tool list — check the table shape")
    return frozenset(names)


def registered_hosted_tools(root: Path = REPO) -> frozenset[str]:
    """What the worker registers: the measurement, taken from the file that serves it."""
    text = (root / "workers" / "register-proxy-sw.js").read_text(encoding="utf-8")
    return frozenset(re.findall(r'name:\s*"(misakanet_[a-z_]+)"', text))


def canonical_mcp_tools(root: Path = REPO) -> int:
    """The hosted MCP tool count, with its expectation taken from *another* file (#1822).

    `update-badges.yml` used to compute this with
    ``grep -cE 'name: "misakanet_' workers/register-proxy-sw.js``: the expected value and the
    measured value read the same file, so the badge could not disagree with the worker — and
    could not notice when the worker disagreed with the documentation. Adding a tool without
    documenting it was invisible, and so was documenting one that was never registered.

    Now the two sides are one file and one document, and a disagreement is an error rather than
    a number: the caller (the badge job) fails, which is the only outcome that reaches anybody.
    Raising instead of returning a best-effort count is the deliberate difference from
    ``canonical_domains`` above — a count that cannot be wrong is not a gate.
    """
    documented = documented_hosted_tools(root)
    registered = registered_hosted_tools(root)
    if documented != registered:
        raise ValueError(
            "the hosted MCP tool list disagrees between AGENTS.md §3.2 and the worker (#1822): "
            f"documented but not registered: {sorted(documented - registered)}; "
            f"registered but not documented: {sorted(registered - documented)}. "
            "Update the document and workers/register-proxy-sw.js together — "
            "tests/test_mcp_tool_count_ssot.py pins both legs."
        )
    return len(documented)


def _build_domain_sites() -> tuple[Site, ...]:
    """Surfaces that advertise how many domains the corpus covers (issue #1687).

    Two rows, both the agent-facing ``llms.txt`` pair, same reason as its lesson rows. The
    install page / ``skill.md`` / ``JOIN.md`` / ``ROADMAP.md`` rows were removed on 2026-09-28
    together with the lesson rows for those files: they are the surfaces that disagreed about the
    domain figure in the first place (18 curated vs 69 raw strings vs 61 normalised, #1687), so
    the product decision recorded in the module docstring — describe the coverage, do not quote a
    second number — retires them rather than picking a winner per page.
    """
    sites: list[Site] = []

    def add(path: str, pattern: str, replace: str, note: str, min_matches: int = 1) -> None:
        sites.append(Site(path, pattern, replace, note, min_matches))

    add("docs/llms.txt", rf"(?m)^- {_COUNT} domains:", "- {n} domains:",
        "llms.txt domain line (agent-facing)")
    add("docs/.well-known/llms.txt", rf"(?m)^- {_COUNT} domains:", "- {n} domains:",
        "served copy of llms.txt")
    return tuple(sites)


DOMAIN_SITES: tuple[Site, ...] = _build_domain_sites()


def canonical_count(root: Path = REPO) -> int:
    """Lesson count from the single source of truth: data/lessons.json."""
    data = json.loads((root / LESSONS_JSON).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError("data/lessons.json root must be a list")
    return len(data)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


@dataclass
class _Scan:
    site: Site
    text: str
    hits: list[re.Match[str]]


def _scan(root: Path, sites: tuple[Site, ...]) -> tuple[list[_Scan], list[str]]:
    """Collect every match; report missing files and non-matching patterns."""
    scans: list[_Scan] = []
    errors: list[str] = []
    for site in sites:
        path = root / site.path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{site.path}: unreadable ({exc}) — {site.note}")
            continue
        hits = list(site.compiled().finditer(text))
        if len(hits) < site.min_matches:
            errors.append(
                f"{site.path}: pattern {site.pattern!r} matched {len(hits)}×, "
                f"expected ≥{site.min_matches} — {site.note}. "
                "The sentence was reworded: fix the file or update SITES."
            )
            continue
        scans.append(_Scan(site, text, hits))
    return scans, errors


def stale_entries(count: int, *, root: Path = REPO,
                  sites: tuple[Site, ...] = SITES,
                  check_count_file: bool = True) -> list[str]:
    """Every health problem with the count surface; empty list == healthy.

    ``check_count_file`` is off for a metric that has no ``COUNT_FILE`` of its own
    (the domain count is derived from the corpus); leaving it on would compare the
    lesson count's copy against a different measure.
    """
    scans, errors = _scan(root, sites)
    for scan in scans:
        for hit in scan.hits:
            if hit.group("n") != str(count):
                found = " ".join(hit.group(0).split())
                if len(found) > 60:
                    found = f"…{found[-60:]}"
                errors.append(
                    f"{scan.site.path}:{_line_of(scan.text, hit.start())}: "
                    f"{found!r} should be {count} — {scan.site.note}"
                )
    if not check_count_file:
        return errors
    count_file = root / COUNT_FILE
    try:
        disk = count_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        errors.append(f"{COUNT_FILE}: unreadable ({exc})")
    else:
        if disk != str(count):
            errors.append(f"{COUNT_FILE}: says {disk!r}, data/lessons.json says {count}")
    return errors


def sync_all(count: int, *, root: Path = REPO, sites: tuple[Site, ...] = SITES,
             dry_run: bool = False, write_count_file: bool = True) -> tuple[list[str], list[str]]:
    """Rewrite every managed site to ``count``. Returns (changes, errors).

    Rows are applied **per file, onto one accumulating text**: several rows can
    target the same file (docs/index.html has four), and writing each row from
    the text captured at scan time made every write clobber the previous row's
    (found the hard way — only the last row survived on disk).

    ``write_count_file`` is off for metrics whose source of truth is already a file
    in the tree (the domain count is derived from the corpus); ``COUNT_FILE`` is the
    lesson count's machine-readable copy and would otherwise be overwritten with a
    different measure.
    """
    scans, errors = _scan(root, sites)
    changes: list[str] = []
    by_path: dict[str, list[_Scan]] = {}
    for scan in scans:
        by_path.setdefault(scan.site.path, []).append(scan)

    for path, path_scans in by_path.items():
        original = path_scans[0].text
        text = original
        total = 0
        for scan in path_scans:
            text, replaced = scan.site.compiled().subn(
                scan.site.replace.format(n=count), text)
            total += replaced
        if total and text != original:
            if not dry_run:
                (root / path).write_text(text, encoding="utf-8")
            changes.append(f"{path}: {total} site(s) → {count}")

    if not write_count_file:
        return changes, errors
    count_file = root / COUNT_FILE
    try:
        current = count_file.read_text(encoding="utf-8").strip()
    except OSError:
        current = None
    if current != str(count):
        if not dry_run:
            count_file.parent.mkdir(parents=True, exist_ok=True)
            count_file.write_text(f"{count}\n", encoding="utf-8")
        changes.append(f"{COUNT_FILE}: {current or 'missing'} → {count}")
    return changes, errors


def _run_metric(label: str, count: int, sites: tuple[Site, ...], *, root: Path,
                check: bool, quiet: bool, write_count_file: bool) -> int:
    """Check or sync one metric. Returns 0 on health, 1 on drift."""
    if check:
        problems = stale_entries(count, root=root, sites=sites,
                                 check_count_file=write_count_file)
        if problems:
            print(f"❌ {label}-count SSOT drift (canonical = {count}):", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        if not quiet:
            print(f"✅ every managed {label} count == {count}")
        return 0

    changes, errors = sync_all(count, root=root, sites=sites,
                               write_count_file=write_count_file)
    if changes:
        print(f"✅ {label} counts synced to {count}:")
        for change in changes:
            print(f"  - {change}")
    elif not quiet:
        print(f"✅ already consistent: every managed {label} count == {count}")
    if errors:
        print(f"❌ some managed {label} sites could not be refreshed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync public lesson and domain counts with their sources of truth "
                    "(idempotent).")
    parser.add_argument("--check", action="store_true",
                        help="verify only; exit 1 on stale or unmatched counts")
    parser.add_argument("--quiet", action="store_true", help="silent on success")
    parser.add_argument("--metric", choices=("all", "lessons", "domains"), default="all",
                        help="narrow to one metric (default: all)")
    parser.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    # Each metric: (label, canonical reader, managed sites, owns a COUNT_FILE copy).
    metrics = [
        ("lesson", canonical_count, SITES, True),
        # Last: the install page carries both counts in one sentence, and this pass owns the
        # domain half of it.
        ("domain", canonical_domains, DOMAIN_SITES, False),
    ]
    wanted = {"all": {"lesson", "domain"},
              "lessons": {"lesson"}, "domains": {"domain"}}[args.metric]

    status = 0
    for label, canonical, sites, owns_count_file in metrics:
        if label not in wanted:
            continue
        try:
            count = canonical(args.root)
        except ValueError as exc:
            print(f"❌ {label} count unavailable: {exc}", file=sys.stderr)
            status = 1
            continue
        status |= _run_metric(label, count, sites, root=args.root, check=args.check,
                              quiet=args.quiet, write_count_file=owns_count_file)

    if args.check and status:
        print("\nFix: python3 scripts/sync_lesson_count.py   "
              "(or update SITES if a sentence was intentionally reworded)", file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
