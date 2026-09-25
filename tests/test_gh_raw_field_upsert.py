#!/usr/bin/env python3
"""`gh api -f body=@file` posts the literal string `@/tmp/…`, and it succeeds.

Found on 2026-09-25 on the release PR (#2020). `pr-checks.yml` posts the audit report as an *upsert* — find
the previous comment by marker, update it in place instead of stacking a new one (issue #1498) — and the
update half was:

    gh api -X PATCH .../issues/comments/$ID -f "body=@$REPORT_FILE" >/dev/null 2>&1 || <fallbacks>

`--raw-field` has no `@file` placeholder; `-F/--field` and `--input` do. So the call sent `@/tmp/tmp.XYZ`
as the body and **returned success**, which meant the `||` fallbacks never ran. Each audit run replaced the
previous report with a file path, the marker went with it, and the next run created another comment. The
result on the release PR: **53 comments reading `@/tmp/tmp.…` and no readable verdict** on a PR that had been
blocked for four days — the explanation of *why* it was blocked was the thing being deleted.

`dco-audit` had the identical line for its DCO block comment, so a contributor who had one DCO failure got a
file path instead of the list of commits to fix.

This file is the repo-wide half of the rule: the audit step in `pr-checks.yml` is a 900-line shell block that
cannot be executed in a test, so the misspelling is banned by inspection everywhere. The *behaviour* is
covered where it can be run — `tests/test_fix_dco_wiring.py` executes `dco-audit`'s comment step with a fake
`gh` and asserts the body sent to the API is the report, not its path.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
ACTIONS = sorted((REPO / ".github" / "actions").glob("*/action.yml"))

# `-f`/`--raw-field` followed by its value, in either quoting style.
RAW_FIELD = re.compile(r"""(?:^|\s)(?:-f|--raw-field)\s+(?:"([^"]*)"|'([^']*)'|(\S+))""")
AT_PATH = re.compile(r"^(?:[\w.-]+=)?@")


def raw_field_problems(sources: dict[str, str]) -> list[str]:
    """Every `--raw-field` whose value is an `@path` or `key=@path` — a file that will never be read."""
    problems = []
    for name, text in sources.items():
        for lineno, line in enumerate(text.splitlines(), 1):
            # Comments are stripped, not searched: the explanation of this bug names the spelling it bans,
            # and a rule that cannot tell code from prose flags its own documentation.
            if line.lstrip().startswith("#"):
                continue
            for match in RAW_FIELD.finditer(line):
                value = next(group for group in match.groups() if group is not None)
                if AT_PATH.match(value):
                    problems.append(f"{name}:{lineno}: --raw-field {value!r} reads nothing — use "
                                    f"-F/--field, --input, or \"$(cat file)\"")
    return problems


def _sources() -> dict[str, str]:
    # Keyed by repository-relative path, not by file name: every composite action is called `action.yml`,
    # so `p.name` collapsed 20+ files into one entry and the rule above read exactly one of them.
    return {p.relative_to(REPO).as_posix(): p.read_text(encoding="utf-8") for p in WORKFLOWS + ACTIONS}


def test_no_raw_field_reads_a_file_by_at_path():
    problems = raw_field_problems(_sources())
    assert not problems, (
        "these calls would post the file's *path* and still exit 0, so the fallback never runs:\n  - "
        + "\n  - ".join(problems))


def test_the_rule_catches_the_spelling_that_destroyed_the_reports():
    fixture = {
        "a.yml": '          gh api -X PATCH "repos/o/r/issues/comments/1" -f "body=@$REPORT_FILE"\n',
        "b.yml": "          gh api -f body=@/tmp/report.md\n",
        "c.yml": "          gh api --raw-field 'body=@/tmp/report.md'\n",
    }
    assert len(raw_field_problems(fixture)) == 3, raw_field_problems(fixture)


def test_the_rule_accepts_the_forms_that_do_read_the_file():
    fixture = {
        "cat.yml": '            -f "body=$(cat "$REPORT_FILE")" >/dev/null 2>&1 ||\n',
        "typed.yml": '            -F "body=@$REPORT_FILE"\n',
        "input.yml": "            --input /tmp/payload.json\n",
        "plain.yml": '            -f "body=hello"\n',
    }
    assert raw_field_problems(fixture) == [], raw_field_problems(fixture)


def test_a_comment_mentioning_the_bad_spelling_is_not_a_violation():
    """The rule's own documentation has to be allowed to name what it bans."""
    fixture = {"a.yml": "              # not `-f body=@$REPORT_FILE`, which posts the path\n"}
    assert raw_field_problems(fixture) == []


def test_the_scanned_sources_are_the_real_ones():
    """Guard the guard: a bad glob would make the rule above pass over an empty mapping."""
    sources = _sources()
    assert len(sources) > 40, f"only read {len(sources)} workflow/action files"
    assert sum(1 for name in sources if name.endswith("action.yml")) >= 5, (
        "the actions were dropped or collapsed by the keying — every one of them is called action.yml")
    assert ".github/workflows/pr-checks.yml" in sources
    assert ".github/actions/dco-audit/action.yml" in sources
