#!/usr/bin/env python3
"""The docs auto-merge gate must never treat a lesson as documentation.

`auto-merge-docs.yml` merges external contributors' docs-only PRs to main, where `docs.yml` publishes
them. Its "docs-only" test was

    f.filename.endsWith('.md') || f.filename.endsWith('.txt') || f.filename.startsWith('docs/') || …

— which is true for **any** `.md` anywhere, `lessons/**` included, directly under a comment saying
"`lessons/` is deliberately NOT docs-only". And `.github/labeler.yml` gives `area:docs` to every
`**/*.md`, so the job's label condition is satisfied by lesson PRs too: #1746 and #1750 carry
`area:docs` + `area:lessons` + `lessons-only` + `needs-human-review`, and both are still open.

The hole was armed, not theoretical: the job runs on `synchronize` and `ready_for_review`, so an
external lesson PR that is pushed again (or leaves draft) after the label lands reaches
`gh pr merge --auto` with `docs-only: true`. The only thing that stopped those two was `needs-dco` — a
check about commit trailers, not about review (found 2026-09-19).

So the rule is now one named function in the workflow, and this test *runs* it over a table of paths
instead of grepping for it. Node is used because the rule executes inside Actions; where node is
unavailable the behavioural half is skipped rather than faked.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "auto-merge-docs.yml"
START = "// ── docs-only rule"
END = "// ── end docs-only rule ──"

# path -> is this a docs-only PR made of exactly this one file?
CASES = {
    # documentation: yes
    "docs/field-reports/2026-09-18-report.md": True,
    "docs/.well-known/mcp.json": True,
    "docs/index.html": True,
    "README.md": True,
    "CONTRIBUTING.md": True,
    "CHANGELOG.md": True,
    "JOIN.md": True,
    # lessons are read and acted on by agents: a human merges them, always
    "lessons/contrib/some-lesson.md": False,
    "lessons/en/ci-dco-fork-pr-signoff.md": False,
    # neither: a stray file at the root, or a doc under a code directory, is not "the docs"
    "fork-error.txt": False,
    "scripts/README.md": False,
    "workers/notes.md": False,
    ".github/workflows/x.yml": False,
    "search_knowledge.py": False,
}


def _rule_source() -> str:
    """The region between the two marker comments, marker lines excluded.

    Sliced by whole lines: the start marker carries a trailing note, and taking a character offset
    from the marker text left that note dangling as invalid JavaScript (the first version of this
    test failed with `SyntaxError: Unexpected identifier 'place'`).
    """
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if START in line)
    end = next(i for i, line in enumerate(lines) if END in line)
    assert end > start, "the docs-only rule markers are out of order"
    return "\n".join(lines[start + 1:end])


def test_the_rule_exists_and_excludes_lessons_by_name():
    """Structural half: the exclusion is present even where node cannot run it."""
    rule = _rule_source()
    assert "lessons/" in rule, "the rule must exclude lessons/ explicitly"
    assert "isDocsFile" in rule
    job_if = WORKFLOW.read_text(encoding="utf-8").split("runs-on:")[0]
    for refusal in ("lessons-only", "needs-human-review"):
        assert refusal in job_if, (
            f"the job condition must refuse PRs labelled '{refusal}': `area:docs` is applied "
            "automatically to every *.md by .github/labeler.yml, so the label alone is not a "
            "human checkpoint"
        )


@pytest.mark.skipif(shutil.which("node") is None, reason="node runs the rule inside Actions")
def test_the_rule_returns_what_the_gate_needs_for_each_path():
    """Behavioural half: evaluate the real function, not a paraphrase of it."""
    rule = _rule_source()
    # The rule text is a comment block plus one arrow function; hand the whole region to node and
    # pull the function out of it, so the test cannot drift from the workflow.
    body = rule
    script = f"""
{body}
const cases = {json.dumps(CASES)};
const wrong = [];
for (const [path, expected] of Object.entries(cases)) {{
  const got = isDocsFile(path);
  if (got !== expected) wrong.push(`${{path}}: got ${{got}}, expected ${{expected}}`);
}}
if (wrong.length) {{ console.error(wrong.join('\\n')); process.exit(1); }}
console.log(`${{Object.keys(cases).length}} paths classified as expected`);
"""
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, (
        "the docs-only rule misclassifies paths:\n" + (result.stderr or result.stdout)
    )
    assert "as expected" in result.stdout
