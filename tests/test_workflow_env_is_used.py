#!/usr/bin/env python3
"""An `env:` key a step declares and its script never mentions is dead configuration — and the usual
cause is a rename that only landed on one side.

That is exactly what `.github/workflows/ci-lesson-search.yml` shipped on 2026-09-21 (#1984):

```yaml
run: printf '%s\\n' "$ERROR_SIG" > /tmp/ci_error.log
env:
  ERROR_SIGNATURES: ${{ steps.context.outputs.error_signatures }}
```

An undefined shell variable expands to the empty string, so the file the intake bot read was one
newline. It answered `{"decision":"ignore","reason":"错误签名过短"}`, the comment step was skipped for
being false, and the run was **green**. A manual dispatch added in the same commit "verified" that
path in seconds — and verified nothing, which is why this gate exists: the new capability could be
triggered, and the thing it does was still impossible.

The rule reads the pair together, which is the only place the mismatch is visible: a name declared on
the step and absent from its own script. Names a *tool* consumes from the environment (`gh` reads
`GH_TOKEN`; `wrangler` reads `CLOUDFLARE_API_TOKEN`) are exempt, because no script ever mentions them.
Measured on the whole repository before landing: 2 hits, both real (this one, and a dead `PR_TITLE`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's steps")

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / ".github" / "workflows"

# Read by the tool the step invokes, not by the script text.
TOOL_CONSUMED = {
    "GH_TOKEN", "GITHUB_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "AI_GATEWAY_ID",
    "AI_GATEWAY_TOKEN", "NODE_AUTH_TOKEN", "NPM_TOKEN", "PYTHONPATH", "ACTIONS_STEP_DEBUG",
}


def script_code(script: str) -> str:
    """The script without its comments.

    Not a nicety: the fix for this very bug carries a comment that *names* `$ERROR_SIGNATURES` to
    explain the rename, so a rule reading raw text is satisfied by the prose describing the defect it
    is looking for. That has now happened five times in this repository's gates; stripping first is
    the standing correction.
    """
    kept = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        kept.append(line.split("  #")[0] if "  #" in line else line)
    return "\n".join(kept)


def unmentioned_env_keys(text: str, exempt: set[str] = frozenset(TOOL_CONSUMED)) -> list[str]:
    """`step: KEY` for every env key a `run:` step declares and its script never names."""
    workflow = yaml.safe_load(text)
    problems = []
    for job in (workflow.get("jobs") or {}).values():
        for step in (job.get("steps") or []):
            raw = step.get("run")
            if not isinstance(raw, str):
                continue
            script = script_code(raw)
            for key in sorted(set((step.get("env") or {})) - set(exempt)):
                if key not in script:
                    problems.append(f"{step.get('name', '(unnamed step)')}: {key}")
    return problems


def test_no_run_step_declares_an_env_key_it_never_reads():
    problems = {}
    for path in sorted(WF_DIR.glob("*.yml")):
        found = unmentioned_env_keys(path.read_text(encoding="utf-8"))
        if found:
            problems[path.name] = found
    assert not problems, (
        "these steps declare an env key their own script never mentions — the name is a rename that "
        f"only landed on one side, or a leftover: {problems}")


# ── guard the guard ─────────────────────────────────────────────────────────────────────────────

def _record(path: str) -> str:
    return (WF_DIR / path).read_text(encoding="utf-8")


def test_the_rule_flags_the_mismatch_that_shipped():
    """The real case, replayed: the step read `$ERROR_SIG` while declaring `ERROR_SIGNATURES`."""
    text = _record("ci-lesson-search.yml")
    assert not unmentioned_env_keys(text), "the file is clean now"
    broken = text.replace('printf \'%s\\n\' "$ERROR_SIGNATURES"', 'printf \'%s\\n\' "$ERROR_SIG"')
    assert broken != text, "the mutation did not take"
    found = unmentioned_env_keys(broken)
    assert any("ERROR_SIGNATURES" in f for f in found), found


def test_a_tool_consumed_name_is_not_flagged():
    """`gh` reads GH_TOKEN; the script never says `$GH_TOKEN`, and that is correct."""
    assert unmentioned_env_keys("""
name: X
on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - name: s
        env:
          GH_TOKEN: ${{ secrets.X }}
        run: gh pr list
""") == []


def test_a_comment_naming_the_variable_does_not_satisfy_the_rule():
    """The regeneration guard for the paragraph above `script_code`."""
    text = """
name: X
on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - name: s
        env:
          ERROR_SIGNATURES: value
        run: |
          # we used to write $ERROR_SIGNATURES here
          printf '%s' "$ERROR_SIG"
"""
    assert unmentioned_env_keys(text) == ["s: ERROR_SIGNATURES"]


def test_an_undefined_variable_is_the_shape_this_rule_is_about():
    """The mechanism, stated once: an unset variable is the empty string, and nothing fails."""
    assert unmentioned_env_keys("""
name: X
on: push
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - name: s
        env:
          REAL_NAME: hello
        run: printf '%s' "$MISSPELLED_NAME"
""") == ["s: REAL_NAME"]
