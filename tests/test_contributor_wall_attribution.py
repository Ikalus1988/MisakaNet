#!/usr/bin/env python3
r"""The homepage's contributor wall read conventional-commit **scopes** as contributor names.

`docs/index.html` builds its 贡献排行 client-side from merged PRs. A contributor's display name is taken
from the PR title when it carries one — `feat: xxx (太阳/Misaka10004)` — and the fallback pattern was
unanchored:

```js
titleMatch = pr.title.match(/\(([a-zA-Z\\u4e00-\\u9fff][\\w.\\-]{1,20}?)\\)(?![\\s\\w])/);
```

So every `fix(worker): …`, `docs(skill): …`, `fix(ci): …` matched with `worker` / `skill` / `ci` as the
"contributor". Measured against the live API on 2026-09-25: **81 of the last 100 closed PRs** yielded such
a name, **75 of them authored by the maintainer** (this session's own titles among them), so the wall's
top rows were `worker`, `ci`, `cf`, `data`, `site`, `doctor`, `dco`, `search`…

The owner filter did not save it, because it compares the **display name** against `SKIP_OWNER`:
`"worker"` is not a member, so the maintainer's own PRs stayed on the wall under their commit scopes —
which is the opposite of "自产自销不计入排行".

Two assertions follow from that, and the patterns are **read out of the page** rather than copied here, so
this test tracks what ships.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HTML = REPO / "docs" / "index.html"


def _title_patterns() -> list[str]:
    """The PR-title patterns the page uses, in order, as Python-compatible sources.

    `\\/` is unescaped because that is a JavaScript string-literal escape rather than a regex one.
    """
    html = HTML.read_text(encoding="utf-8")
    sources = re.findall(r"titleMatch = pr\.title\.match\(/(.+?)/\)", html)
    assert len(sources) == 2, f"expected the name/MisakaID pattern and a fallback, found {sources}"
    return [s.replace("\\/", "/") for s in sources]


def live_pattern() -> re.Pattern:
    """The pattern that runs when the title has no `(name/MisakaID)` — the one that was wrong."""
    return re.compile(_title_patterns()[1])


def extract_name(title: str) -> str | None:
    """The page's own logic: first pattern wins, then the fallback."""
    for source in _title_patterns():
        match = re.search(source, title)
        if match:
            return match.group(1).strip()
    return None


# ── the defect ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("title", [
    "fix(worker): the counter's last resort read a branch that no longer has the file",
    "docs(skill): the skill taught a hosted-only tool without saying which surface",
    "fix(ci): the claim window said 8 hours and released after 4",
    "feat(doctor): read the deployed version back",
    "feat(lesson): LLM god-moding in roleplay (#1650)",
    "docs(arch): the map still pointed at a script that was deleted",
])
def test_a_commit_scope_is_not_a_contributor_title(title):
    """These are this repository's real PR titles; each one used to name a fake contributor."""
    assert extract_name(title) is None, (
        f"{title!r} yields a contributor name — a conventional-commit scope is a *type*, not a person, "
        "and reading it as one put the maintainer's own PRs on the wall under names like 'worker'"
    )


def test_the_fallback_requires_a_name_boundary():
    """Anchoring is the fix: the convention writes the name after a space, a scope is glued to its type."""
    source = _title_patterns()[1]
    assert source.startswith("(?:^|\\s)"), (
        f"the fallback is unanchored again ({source!r}) — every `type(scope):` title will be read as a "
        "contributor name"
    )


# ── the convention it exists for ────────────────────────────────────────────────────
@pytest.mark.parametrize("title,expected", [
    ("feat: xxx (太阳/Misaka10004)", "太阳"),            # the documented name/MisakaID form
    ("fix: something broken (Rushikesh)", "Rushikesh"),  # a plain name after a space
    ("docs: dedupe (zsxh1990)", "zsxh1990"),
    # NB: a name starting with a digit is not extracted — the pattern requires a letter or CJK first
    # character. Pre-existing, unchanged here, and worth knowing when reading the wall.
])
def test_the_documented_name_convention_still_resolves(title, expected):
    """The fix must not cost the names the wall is *supposed* to show."""
    assert extract_name(title) == expected, (title, extract_name(title))


# ── the owner filter ────────────────────────────────────────────────────────────────
def test_the_owner_filter_keys_on_the_login_not_on_the_display_name():
    """The row's name can be rewritten from the title, so a name-only filter cannot exclude an owner."""
    html = HTML.read_text(encoding="utf-8")
    assert "isOwnerRow" in html, "the owner-row helper is gone"
    helper = re.search(r"const isOwnerRow = \(node, data\) =>(.+?);", html, re.DOTALL)
    assert helper, "isOwnerRow is not defined as a two-argument arrow"
    body = helper.group(1)
    assert "SKIP_OWNER.has(node)" in body, body
    assert "data" in body and "user" in body, (
        "the filter no longer looks at the row's login, so an owner's PR can still appear under a "
        f"name taken from its title: {body}"
    )
    # The wall routes its rows through it. This used to require **two** callers, because the stats
    # card's "agent contributors" count was the second one — that count was removed on 2026-09-26
    # (its input was an optional self-declared `Agent-Type:` header, so it measured who wrote a header,
    # not who contributes). The assertion is about the wall now: a rendered row that skips the filter
    # puts the owner back on their own wall under a name taken from a PR title, which is the defect the
    # helper exists for.
    assert "!isOwnerRow(node, data)" in html, "the wall bypasses the owner filter"


def test_the_skip_owner_set_still_names_the_owners():
    html = HTML.read_text(encoding="utf-8")
    match = re.search(r"SKIP_OWNER = new Set\(\[([^\]]+)\]\)", html)
    assert match, "SKIP_OWNER is gone"
    entries = {e.strip().strip('"').lower() for e in match.group(1).split(",") if e.strip()}
    for owner in ("ikalus1988", "sheldonisspark-lab", "misakanet-bot", "claude"):
        assert owner in entries, f"{owner} is no longer excluded from the wall: {sorted(entries)}"


# ── who is on the wall at all: merged, not merely closed ────────────────────────────────────────────
# The wall's headline claim is that these people **contributed**. The first cut of this filter took
# every PR with a `closed_at`, and the comment beside it called that intentional ("merged via API or
# force-push merged"). Measured against the live page on 2026-10-02 — the homepage's own proxy,
# `/api/github/repos/Ikalus1988/MisakaNet/pulls?state=closed&sort=updated&direction=desc&per_page=100`
# — 100 rows came back, **11 with `merged_at: null`**, and **6 of those from non-owner accounts**
# (`alienvisitor8675-bit` ×4, `shruhicollections-beep`, `zsxh1990`; `s6pa1rta3n-lab` ×1 was a draft and
# already filtered). So a stranger could open a PR and close it themselves and land on the wall — which
# is how *any* GitHub user came to put script on the homepage through the row this filter feeds (the
# sink is fixed; this is the admission rule behind it).
#
# `merged_at` is the API's own answer to "was this merged": it is set on exactly the merged PRs and
# null otherwise. The owner chose the plain rule on 2026-10-02, with no maintainer exception.
#
# The cost first claimed for that rule — force-push landings leaving the wall — did not survive reading
# the rejection comments. Each of the 6 non-owner rows was refused ("cannot merge") or superseded by the
# author's own follow-up; the two accounts whose rows actually go (`alienvisitor8675-bit`,
# `shruhicollections-beep`) answer 0 to `commits?author=`, and `zsxh1990` keeps a row because #2438 was
# merged inside the same window. The visible change is 2 accounts / 5 PRs of rows that should never have
# been counted.
def _wall_filter_predicate() -> str:
    """The wall's admission predicate, read out of the page so the gate tracks what ships."""
    html = HTML.read_text(encoding="utf-8")
    match = re.search(r"^\s*const \w+ = prs\.filter\((.+)\);\s*$", html, re.MULTILINE)
    assert match, "the wall's `.filter(…)` over the pulled PR list moved — this test reads it to check what ships"
    return match.group(1).strip()


#: The three API shapes the admission rule has to tell apart. `merged_at` is GitHub's own answer to
#: "was this merged"; `closed_at` is set on a PR that was abandoned unmerged; `draft` is what the
#: `!p.draft` half exists for. Only `merged` may be admitted.
WALL_ROWS = [
    {"id": "merged", "merged_at": "2026-09-30T11:55:23Z", "closed_at": "2026-09-30T11:55:23Z", "draft": False},
    {"id": "unmerged", "merged_at": None, "closed_at": "2026-09-30T14:25:39Z", "draft": False},
    {"id": "merged-draft", "merged_at": "2026-09-30T11:55:23Z", "closed_at": "2026-09-30T11:55:23Z", "draft": True},
]


def _admitted_ids(predicate: str) -> list[str]:
    """Run the page's own predicate over the fixtures in node — JavaScript is the language it ships in."""
    node = shutil.which("node")
    assert node, "node is required: the wall's admission rule is JavaScript and must be evaluated, not grepped"
    script = (
        f"const admits = ({predicate});"
        f"const rows = {json.dumps(WALL_ROWS)};"
        "process.stdout.write(JSON.stringify(rows.filter(admits).map(r => r.id)));"
    )
    done = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert done.returncode == 0, (
        f"the page's predicate does not evaluate: {done.stderr.strip()}\npredicate: {predicate!r}"
    )
    return json.loads(done.stdout)


def test_the_wall_admits_merged_pull_requests_only():
    """A text check passes on any predicate that mentions `merged_at`; this runs the predicate itself.

    Mutation-checked 2026-10-02 by editing the page's filter to each wrong rule in turn — all three go
    red: `p => p.merged_at` admits `merged-draft`, `p => p.merged_at || !p.draft` admits `unmerged`, and
    the previous `p => p.closed_at && !p.draft` admits `unmerged` as well.
    """
    predicate = _wall_filter_predicate()
    assert _admitted_ids(predicate) == ["merged"], (
        f"the wall's admission rule ({predicate!r}) does not admit exactly the merged, non-draft PRs — a "
        "PR that was never merged is not a contribution, and measured 2026-10-02 six of the last hundred "
        "rows from non-owner accounts had `merged_at: null`"
    )


# ── the render path is an innerHTML sink fed by *public, unauthenticated* PR metadata ──────────────
# Measured 2026-10-02 in a real browser against a stubbed `/api/github/.../pulls` response: a PR that was
# merely **closed** (the filter then was `p.closed_at && !p.draft`, so `merged_at` could be null — any
# GitHub user could open a PR and close it) put script on the homepage. Three fields reached `innerHTML`
# unescaped:
#
#   pr.title        -> the display name       "<div class=\"contrib-name\">${node}"
#   Supported-by:   -> data.agentModel        "<span class=\"contrib-model-badge\">…${data.agentModel}"
#   a "- " body line-> the lesson label       "<a href=\"${l.url}\">📘 ${l.name…}"
#
# and the lesson id also landed inside the `href`, so the attribute could be broken out of as well.
# The page already owns both primitives — `escapeHTML` (escapes & < > " ') and `safeHref` (http(s) only)
# — and the search results and voice cards use them. This wall was the one path that did not.
#
# The *escaping* and the *admission rule* are separate defects: escaping decides whether a stranger's
# title can run script, admission decides whether that stranger is on the wall at all. The filter moved
# to `p.merged_at && !p.draft` on 2026-10-02 (owner's decision; the gate is
# `test_the_wall_counts_only_merged_pull_requests` in this file); the escaping gates below stay exactly
# as they were.

def _contributor_row_template() -> str:
    """The template literal the wall's rows are built from, read out of the page."""
    html = HTML.read_text(encoding="utf-8")
    match = re.search(r'return `\s*\n\s*<div class="contrib-item">(.*?)`\s*;', html, re.DOTALL)
    assert match, "the wall's row template moved — this test reads it to check what ships"
    return match.group(1)


#: Values the template may interpolate *raw* because the page computes them itself. Each is either a
#: literal (`rank`, `level`, the class names) or a fragment assembled above from already-escaped input —
#: `classBadge` also passes through a `switch` that returns '' for anything unknown.
PAGE_COMPUTED = {"rank", "level", "levelClass", "classBadge", "modelBadge", "contribDetail", "xpBar",
                 "details"}


def test_every_interpolation_in_the_wall_is_escaped_or_page_computed():
    """A gate, not three literals: it fails on the *next* field someone interpolates here."""
    raw = []
    for expr in re.findall(r"\$\{([^}]*)\}", _contributor_row_template()):
        expr = expr.strip()
        if expr in PAGE_COMPUTED:
            continue
        if expr.startswith(("escapeHTML(", "safeHref(")):
            continue
        raw.append(expr)
    assert not raw, (
        "these values reach the contributor wall's innerHTML without escaping, and the wall is built "
        f"from other people's pull requests: {raw}"
    )


@pytest.mark.parametrize("sink", [
    "escapeHTML(node)",
    "escapeHTML(data.agentModel)",
    "escapeHTML(l.name.substring(0, 40))",
    "safeHref(l.url)",
])
def test_the_pull_request_fields_are_escaped_at_the_sink(sink):
    """Named explicitly, so a refactor that moves the fragments around still has to keep them escaped."""
    html = HTML.read_text(encoding="utf-8")
    assert sink in html, f"{sink} is gone — that field comes from a PR title or body"


def test_the_lesson_id_is_url_encoded_where_the_href_is_built():
    """`id` is a `- ` line from a PR body, so it must not be able to close the href attribute."""
    html = HTML.read_text(encoding="utf-8")
    assert "lessons/${encodeURIComponent(id)}.md" in html, (
        "the lesson id is interpolated into a URL unencoded; a `\"` in it closes the href attribute"
    )

def test_a_lesson_line_only_counts_when_it_names_a_lesson_in_the_corpus():
    """The ranking is `count + lessons.length` and the wall shows the top 10.

    Every `- ` line used to be pushed regardless of `exists`, so a body with ~30 filler lines took the
    first row — which is also what put a stranger's payload above the fold. A line that names nothing in
    `data/lessons.json` is not a contribution to the corpus and must not count.
    """
    html = HTML.read_text(encoding="utf-8")
    block = re.search(r"lessonLines\.forEach\(line => \{(.*?)\n      \}\);", html, re.DOTALL)
    assert block, "the lesson-line loop moved"
    body = block.group(1)
    assert re.search(r"if \(!exists\) return;", body), (
        "a `- ` line now counts even when its id is not in the corpus, so a PR body can stuff the "
        f"ranking: {body.strip()[:200]}"
    )
