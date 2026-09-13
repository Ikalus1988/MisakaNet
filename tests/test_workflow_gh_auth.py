#!/usr/bin/env python3
"""Every workflow that shells out to `gh` must authenticate it (2026-09-12).

Why this exists
---------------
`Intake Salvage Digest` failed on its daily schedule from at least 2026-09-09 with
nothing but `Process completed with exit code 4`. Two details made it invisible:

* the job declared `permissions: issues: write` but never exported `GH_TOKEN`, so
  `gh` was unauthenticated — exit code 4 is gh's auth failure, not a shell error;
* the step runs under `bash -e`, and its first `gh` call ended with `2>/dev/null`,
  so the message that would have named the problem was discarded.

The consequence was silent and load-bearing: the digest that exists to surface
auto-rejected intakes never ran, so the salvage queue sat untouched while every
run reported a green schedule (a failed run is easy to miss in a list of daily
schedules).

A test cannot call `gh` with the runner's token, but it can check the invariant
that decides whether the call can work at all: `gh` needs GH_TOKEN (or
GITHUB_TOKEN) in its environment, and declaring workflow `permissions` does not
put it there.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# Where a `gh` command can appear, and where it cannot.
#
# The first version of this guard used one regex, and an adversarial review falsified
# it in both directions (2026-09-12): it MISSED three real gh-calling steps in this
# repository (an indented `gh pr comment`, `if gh release view …`, `if ! gh workflow
# run …`, `GH_TOKEN=… gh …`) and it FAILED a step that never calls gh but documents one
# inside a heredoc. It also silently passed a scratch workflow with three unauthenticated
# gh calls, and the digest's executable test still passed after its job-level GH_TOKEN was
# deleted — because a stub `gh` does not care about auth while the real one exits 4.
#
# So detection is now a small shell-aware scan: leading whitespace is irrelevant,
# `!`/pipes/separators/`env`/`sudo` wrappers are unwrapped, and heredoc bodies are
# skipped because they are data, not commands.
#
# Known limitation, stated rather than hidden: a gh binary reached through a variable
# (`"$GH_BIN" issue list`) cannot be identified statically. That is why the real
# guarantee for a workflow we depend on is the executable step test
# (tests/test_salvage_digest_script.py), which runs the script with a stub gh that
# enforces authentication exactly like the real one.
# Shell keywords (`if gh release view …`, `if ! gh workflow run …`, `then`, `{`) and
# command wrappers (`env X=1 gh …`, `sudo gh …`) both hide the command word from a
# naive scan.
GH_WRAPPERS = re.compile(
    r"^(?:sudo|command|env|nice|time)\s+|^[A-Za-z_][A-Za-z0-9_]*=\S+\s+"
    r"|^(?:if|then|elif|else|while|until|do|done|fi|!|\{|\(|\[\[)\s*")
HEREDOC_START = re.compile(r"<<-?\s*[\"\']?(\w+)")


def gh_invocations(script: str) -> list[tuple[int, str]]:
    """(line number, command) for every place the script runs `gh`."""
    found: list[tuple[int, str]] = []
    heredoc_end: str | None = None
    for number, raw in enumerate(script.splitlines(), 1):
        if heredoc_end is not None:
            if raw.strip() == heredoc_end:
                heredoc_end = None
            continue
        if raw.lstrip().startswith("#"):
            continue
        line = raw.split("#", 1)[0] if "#" not in raw[:1] else ""
        marker = HEREDOC_START.search(raw)
        if marker:
            heredoc_end = marker.group(1)
        for chunk in re.split(r"\|\||&&|[;|]", line):
            command = chunk.strip().lstrip("!").strip()
            while True:
                wrapper = GH_WRAPPERS.match(command)
                if not wrapper:
                    break
                command = command[wrapper.end():].strip()
            if re.match(r"gh\s+\w", command):
                found.append((number, command))
    return found


def _workflow_files() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.y*ml"))


def _gh_steps(workflow: dict):
    """Yield (job_name, step, job_env) for every step whose `run:` calls gh."""
    for job_name, job in (workflow.get("jobs") or {}).items():
        job_env = job.get("env") or {}
        for step in job.get("steps") or []:
            run = step.get("run") or ""
            if gh_invocations(run):
                yield job_name, step, job_env


def test_gh_is_authenticated_wherever_a_workflow_uses_it():
    offenders = []
    checked = 0
    for path in _workflow_files():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, step, job_env in _gh_steps(workflow):
            checked += 1
            step_env = step.get("env") or {}
            has_token = any(
                key in merged
                for merged in (step_env, job_env)
                for key in ("GH_TOKEN", "GITHUB_TOKEN")
            ) or "token" in (step.get("with") or {})   # checkout-style token input
            if not has_token:
                offenders.append(f"{path.name}:{job_name}:{step.get('name', '(unnamed step)')}")
    assert checked, "no workflow step calls gh — this guard has gone stale, check gh_invocations()"
    assert offenders == [], (
        "these steps call gh without GH_TOKEN/GITHUB_TOKEN in scope, so gh runs "
        "unauthenticated and exits 4 (and `permissions:` does not export it):\n  - "
        + "\n  - ".join(offenders)
    )


def test_the_salvage_digest_does_not_swallow_gh_errors():
    """The failure that motivated this file was silenced by `2>/dev/null`.

    Suppressing stderr on a `gh` call is what turned a one-line auth error into a
    multi-day mystery, so keep it off the inventory call in particular.
    """
    text = (WORKFLOWS / "intake-salvage-digest.yml").read_text(encoding="utf-8")
    assert "gh issue list" in text
    for line in text.splitlines():
        if "gh " in line and "2>/dev/null" in line:
            pytest.fail(f"a gh call discards its error output, hiding the reason: {line.strip()}")
    # The digest step must fail loudly instead: `bash -e` is in effect, so a bare
    # failure with stderr dropped is exactly the reported symptom.
    assert "GH_TOKEN" in text, "the digest job must export a token for gh"

# === The two falsifications, as fixtures (2026-09-12) ===

TRICKY_FORMS = {
    "indented inside an if": "    if [ -n \"$X\" ]; then\n      gh pr comment 5 --body hi\n    fi",
    "if gh release view": "if gh release view v1 >/dev/null 2>&1; then\n  echo yes\nfi",
    "negated": "if ! gh workflow run release-pypi.yml --ref main; then\n  echo retry\nfi",
    "env wrapper": "env FOO=1 gh issue list --repo x/y",
    "inline assignment": "GH_TOKEN=x gh workflow run a.yml",
    "after a separator": "make build && gh pr merge 1 --squash",
    "sudo": "sudo gh api /repos/x/y",
}


def test_every_tricky_gh_form_is_detected():
    """The forms the previous regex missed, including three present in this repository."""
    for name, script in TRICKY_FORMS.items():
        assert gh_invocations(script), f"missed {name}: {script!r}"


def test_documentation_that_mentions_gh_is_not_a_call():
    """A heredoc body is data. The old regex failed a step for documenting a command."""
    script = """cat <<'EOF' > /tmp/notes.md
gh issue list --label auto-rejected --state open
EOF
echo done"""
    assert gh_invocations(script) == []


def test_comments_are_not_calls():
    assert gh_invocations("# gh issue list\n   #   gh pr comment 1") == []


def test_the_known_limitation_is_stated():
    """Variable indirection is invisible to static scanning — the guard says so, and the
    executable step test is the stronger check for the workflows we depend on."""
    source = Path(__file__).read_text(encoding="utf-8")
    assert "cannot be identified statically" in source
    assert "test_salvage_digest_script" in source
