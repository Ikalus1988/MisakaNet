#!/usr/bin/env python3
"""No workflow may push to `main`, and the two that still would are named here on purpose.

`main` carries the ruleset **"main: the deterministic gates"** (id 23826057): three required status
checks and an empty `bypass_actors`. A direct push therefore arrives without the checks GitHub
demands and is refused — `remote: - 3 of 3 required status checks are expected.` That is how five
automated writers silently stopped landing their output on 2026-09-22 (see
`docs/maintainer/automation-lands-via-pr.md`), and *silently* is the operative word: each of those
jobs only pushes when it has something to write, so the runs where nothing changed stayed green
while the runs that mattered went red in a step nobody was watching.

The mechanism that replaced them is `scripts/ci/land_change.py` — branch, pull request, required
checks, auto-merge. This file is the part of that change that does not depend on anyone
remembering it: a workflow that goes back to `git push`-ing `main` fails here, in a test that runs
on every PR, instead of failing months later in a scheduled run nobody reads.

Two exceptions are listed with the reason they are exceptions, and the reason has to survive being
read by the next person to touch them:

* `register.yml` assigns the next node number on a registration issue. Its write is on a user's
  critical path, so a pull request's latency would be paid by the person registering, and two
  registrations racing through two unmerged branches could hand out the same number. The fix for
  that path is to read the number from the worker's KV counter (the source `data/counter.json`
  mirrors) rather than to invent one in git — see the issue linked in the entry below.
* `cite-lesson.yml` reacts to an issue labelled `usage` and its `git push` currently pushes
  nothing (the step before it writes no files), so it is a no-op rather than a blocked write.

Both entries are checked in both directions: an unlisted main-pusher fails, **and** a listed file
that no longer pushes to main fails too — so converting or deleting one forces the list to be
trimmed instead of quietly rotting into a lie.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow steps")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
LANDER = "scripts/ci/land_change.py"

# file → why it still pushes to `main` instead of using the lander.
MAIN_PUSHERS = {
    "register.yml": (
        "assigns the next node number on a registration issue — a pull request would put the "
        "required checks' latency on the person registering, and two unmerged branches racing "
        "could issue the same number. Tracked in #2106, which recommends reading the number from "
        "the worker's KV counter (the source `data/counter.json` mirrors) instead of writing it in "
        "git at all."
    ),
    "cite-lesson.yml": (
        "reacts to an issue labelled `usage`; its push is currently a no-op (the preceding step "
        "writes no files), so nothing is being lost while that path is decided."
    ),
}

# The jobs converted on 2026-09-23. They must call the lander, not a push.
CONVERTED = (
    "sync-node-counter.yml",
    "update-lessons.yml",
    "build-feed.yml",
    "leaderboard-watch.yml",
    "benchmark-workers-ai.yml",
    "d1-bootstrap.yml",
    "release-please.yml",
)

# A `git push` only counts when it is in command position. Written this way because the strings
# below are *about* pushing — `dco-check.yml` ships instructions to contributors containing
# "git push --force-with-lease", and my own comments in the converted workflows quote the command
# they replaced. A rule that reads raw text is satisfied by the prose describing the defect it is
# looking for; this repository has made that mistake five times.
_SEPARATORS = set(";&|({")
_REDIRECT_RE = re.compile(r"^\d*[<>]")
# A command can follow a shell keyword rather than a separator: `if git push …; then` is the shape
# `register.yml` uses, and a scanner that only accepted separators declared that workflow clean.
_KEYWORDS = {"if", "then", "else", "elif", "while", "until", "do", "time", "not", "!"}


def shell_code(script: str) -> str:
    """The script without its comments (see `tests/test_workflow_env_is_used.py` for the history)."""
    kept = []
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        kept.append(line.split("  #")[0] if "  #" in line else line)
    return "\n".join(kept)


def in_command_position(text: str, start: int) -> bool:
    """True when `text[start:]` starts a command rather than sitting inside a word or a string."""
    i = start - 1
    while i >= 0 and text[i] in " \t":
        i -= 1
    if i < 0:
        return True
    if text[i] in _SEPARATORS or text[i] == "\n":
        return True
    word_end = i
    while i >= 0 and (text[i].isalnum() or text[i] in "_!"):
        i -= 1
    return text[i + 1:word_end + 1] in _KEYWORDS


def push_commands(script: str) -> list[str]:
    """The argument text of every `git push` that actually runs, in `script`."""
    code = shell_code(script)
    commands = []
    for match in re.finditer(r"\bgit\s+push\b", code):
        if not in_command_position(code, match.start()):
            continue
        rest = code[match.end():]
        stop = len(rest)
        for i, ch in enumerate(rest):
            if ch in ";\n|&)":
                stop = i
                break
        commands.append(rest[:stop].strip())
    return commands


def pushes_to_main(script: str) -> bool:
    """True when any `git push` in `script` can only be going to the branch the job checked out.

    A push with no refspec (`git push`, `git push origin`) publishes the checked-out branch, which
    for these jobs is `main` — that is exactly the shape the ruleset refuses, and exactly the shape
    the converted workflows used.
    """
    for command in push_commands(script):
        tokens = [t for t in command.split() if t and not t.startswith("-")]
        tokens = [t for t in tokens if not _REDIRECT_RE.match(t)]
        refspecs = tokens[1:]
        if not refspecs:
            return True
        for refspec in refspecs:
            if refspec == "HEAD":
                return True
            if refspec in ("main", "refs/heads/main") or refspec.endswith(":main") \
                    or refspec.endswith("/main"):
                return True
    return False


def step_scripts(workflow: Path) -> list[str]:
    """Every shell script a workflow runs, including scripts passed to a local action wrapper.

    `cite-lesson.yml` runs its commands through `./.github/actions/retry/`, which executes the
    `run:` input it is given — so `with.run` is a script too, and a scanner that only looked at
    `steps[].run` would have declared that workflow clean while it pushed.
    """
    data = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    scripts = []
    for job in (data.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            if not isinstance(step, dict):
                continue
            if isinstance(step.get("run"), str):
                scripts.append(step["run"])
            passed = (step.get("with") or {}).get("run")
            if isinstance(passed, str):
                scripts.append(passed)
    return scripts


def main_pushers() -> dict[str, list[str]]:
    found = {}
    for workflow in sorted(WORKFLOWS.glob("*.y*ml")):
        hits = [c for s in step_scripts(workflow) for c in push_commands(s)]
        if any(pushes_to_main(s) for s in step_scripts(workflow)):
            found[workflow.name] = hits
    return found


def test_the_scan_sees_the_repository_s_workflows():
    """A glob that silently matched nothing would make every assertion below vacuous."""
    assert len(list(WORKFLOWS.glob("*.y*ml"))) > 50
    assert len(step_scripts(WORKFLOWS / "sync-node-counter.yml")) >= 3


def test_only_the_documented_exceptions_push_to_main():
    found = set(main_pushers())
    unexpected = found - set(MAIN_PUSHERS)
    assert not unexpected, (
        "these workflows push to `main` and the ruleset on `main` will refuse the push "
        "(see docs/maintainer/automation-lands-via-pr.md); land the change through "
        f"`{LANDER}` instead, or add the workflow to MAIN_PUSHERS with its reason: "
        f"{sorted(unexpected)}"
    )


def test_the_exception_list_does_not_rot():
    """Each listed file must exist and must still push to `main`.

    Without this half, converting `register.yml` would leave an entry claiming it still pushes —
    a comment that has become false, which is worse than no comment.
    """
    found = main_pushers()
    for name in MAIN_PUSHERS:
        assert (WORKFLOWS / name).exists(), f"{name} is listed in MAIN_PUSHERS but no longer exists"
        assert name in found, (
            f"{name} no longer pushes to `main` — delete its MAIN_PUSHERS entry, and say so in the "
            "issue that tracked the conversion"
        )


def test_the_converted_writers_go_through_the_lander():
    for name in CONVERTED:
        workflow = WORKFLOWS / name
        assert workflow.exists(), f"{name} is listed as converted but does not exist"
        text = workflow.read_text(encoding="utf-8")
        assert LANDER in text, f"{name} does not call {LANDER}"
        assert "secrets.SHELDON_PAT" in text, (
            f"{name} must hand the lander a PAT: a branch pushed with GITHUB_TOKEN starts no "
            "workflow runs, so the required checks would never report and the auto-merge would "
            "wait forever"
        )
        assert not any(pushes_to_main(s) for s in step_scripts(workflow)), (
            f"{name} still pushes to `main` somewhere"
        )


def test_the_lander_itself_never_pushes_to_main():
    """The one script every converted workflow now depends on must not be the exception."""
    text = (REPO / LANDER).read_text(encoding="utf-8")
    assert "refs/heads/{branch}" in text, "the lander pushes to its bot branch by refspec"
    assert not pushes_to_main(text)


# ── the classifier's own tests: a gate that cannot go red is not a gate ──


@pytest.mark.parametrize("script", [
    "git push origin main",
    "git push",
    "git push origin",
    "git push origin HEAD:main",
    "git push --force-with-lease origin HEAD:refs/heads/main",
    "git push || { git pull --rebase --autostash && git push; }",
    "git push origin main 2>&1 || { sleep 5; git push origin main; }",
    "set -euo pipefail\ngit add -A\ngit push origin HEAD\n",
    "if git push --force-with-lease; then\n  echo assigned\nfi",  # the shape register.yml uses
])
def test_main_pushes_are_recognised(script):
    assert pushes_to_main(script), f"missed a push to main in: {script!r}"


@pytest.mark.parametrize("script", [
    'git push --force "$URL" HEAD:refs/heads/"$BRANCH"',
    'git push origin "$BRANCH" --force',
    "git push origin data",
    "git push origin HEAD:data",
    "git push -f origin v1",
    "git push origin HEAD:refs/heads/${{ steps.pr.outputs.headRef }}",
    "git push origin refs/heads/maintenance",  # not `main`
])
def test_pushes_that_are_not_main_are_left_alone(script):
    assert not pushes_to_main(script), f"false positive on: {script!r}"


@pytest.mark.parametrize("script", [
    "# git push origin main",
    "  # main moves under this job; retry the push rather than losing the read: git push",
    ': \'One or more commits are missing the trailer. Fix:\\n\\ngit push --force-with-lease\\n\'',
    'echo "run \\"git push --force-with-lease\\" after signing off"',
    'core.info("git push --force-with-lease")',
])
def test_text_about_pushing_is_not_a_push(script):
    """The strings that describe a push must not be mistaken for one — five gates in this
    repository have been satisfied by the prose describing the defect they look for."""
    assert not pushes_to_main(script), f"read prose as a command: {script!r}"
