#!/usr/bin/env python3
r"""The homepage's contributor wall read conventional-commit **scopes** as contributor names.

`docs/index.html` builds its 贡献排行 client-side from closed PRs. A contributor's display name is taken
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

import re
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
    # the wall and the agent counter must both route through it
    assert html.count("!isOwnerRow(node, data)") >= 2 or html.count("!isOwnerRow(") >= 2, (
        "the wall or the agent counter bypasses the owner filter"
    )


def test_the_skip_owner_set_still_names_the_owners():
    html = HTML.read_text(encoding="utf-8")
    match = re.search(r"SKIP_OWNER = new Set\(\[([^\]]+)\]\)", html)
    assert match, "SKIP_OWNER is gone"
    entries = {e.strip().strip('"').lower() for e in match.group(1).split(",") if e.strip()}
    for owner in ("ikalus1988", "sheldonisspark-lab", "misakanet-bot", "claude"):
        assert owner in entries, f"{owner} is no longer excluded from the wall: {sorted(entries)}"
