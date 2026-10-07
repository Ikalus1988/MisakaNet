#!/usr/bin/env python3
"""Workflow checks that are either dead or dishonest about what they do.

Two shapes, both found by an external review (OPEN-CODE-REVIEW-2026-10-06.md §3.4) and both of
which turned out to be something other than the one-line fix the review proposed:

* **`pr-checks.yml`'s action-pinning advisory** filtered with `grep -v '@[a-f0-9]{40}'`. The
  review was right that `{40}` is a literal in a basic regular expression, so the filter matched
  nothing — and wrong about what follows from it. Adding `-E`, as suggested, makes the filter
  *live* and makes the check worse: `[a-f0-9]` does not contain `v`, so it can only fire on a
  line that names a 40-hex SHA somewhere else, and then it drops a genuine tag pin. The filter is
  removed, and the remaining grep is fed comment-stripped input so a `uses:` in prose is not
  reported as an unpinned action.

* **`example-capture.yml`** ran `python -m pytest || true` and then gated the capture on
  `if: failure()`. The `|| true` makes the condition permanently false, so the example could
  never capture anything — and it is a file people copy, so it taught the dead pattern.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
PR_CHECKS = WORKFLOWS / "pr-checks.yml"
EXAMPLE_CAPTURE = WORKFLOWS / "example-capture.yml"

#: The pinning check as a shell pipeline, recovered from the step so the test reads the real thing
#: rather than a transcription of it. A copy here could drift and still be green.
PINNING_MARKER = "Checking workflow action pinning"

#: `uses: owner/repo@v1` — the pattern a real tag pin matches.
TAG_PIN = re.compile(r"uses:\s+[A-Za-z0-9_-]+/[A-Za-z0-9_-]+@v[0-9]")


def _shell_files(directory: Path, *needles: str) -> list[str]:
    """Every `run:` body in `directory` that mentions one of `needles`.

    Comment lines inside the body are removed first. The note explaining *why* the dead filter was
    deleted has to quote that filter, and a rule that read comments would then be reporting this
    test's own explanation back at it — which is the same mistake the check it guards was making.
    """
    found = []
    for path in sorted(set(directory.glob("*.yml")) | set(directory.glob("*.yaml"))):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job in (document.get("jobs") or {}).values():
            for step in (job or {}).get("steps") or []:
                script = str(step.get("run", ""))
                code = "\n".join(line for line in script.splitlines()
                                 if not line.strip().startswith("#"))
                if any(needle in code for needle in needles):
                    found.append(code)
    return found


def _run_pinning_check(workflow_text: str, tmp_path: Path) -> tuple[int, str]:
    """Execute the real pinning check against a directory we control, and report what it flagged."""
    document = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    script = None
    for job in document["jobs"].values():
        for step in job.get("steps", []):
            if PINNING_MARKER in str(step.get("run", "")):
                script = str(step["run"])
    assert script, "the action-pinning check disappeared from pr-checks.yml"

    # Keep only the pinning loop: the step also runs a permission scan and a README check that
    # need the repository root, and this is the part under test.
    start = script.index("for wf in")
    end = script.index("# 2. Overly broad permissions")
    loop = script[start:end]
    target = tmp_path / "wf.yml"
    target.write_text(workflow_text, encoding="utf-8")
    body = loop.replace('.github/workflows/*.yml .github/workflows/*.yaml', str(target))
    runner = tmp_path / "run.sh"
    runner.write_text("set -u\n" + body, encoding="utf-8")
    proc = subprocess.run(["bash", str(runner)], capture_output=True, text=True, timeout=60)
    return proc.returncode, proc.stdout + proc.stderr


# ── The pinning advisory ───────────────────────────────────────────────────────────────────────────

def test_the_pinning_check_has_no_regex_that_can_never_match():
    """`grep -v '@[a-f0-9]{40}'` without `-E` matches the literal 16 characters, never a SHA.

    A filter that can never remove anything is not a safety net; it is a comment that looks like
    one. The fix is to remove it, because *adding* `-E` turns it into a real filter that drops
    genuine tag pins — see the next two tests for why that is worse.
    """
    for script in _shell_files(WORKFLOWS, PINNING_MARKER):
        for line in script.splitlines():
            if "grep -v" in line and "{40}" in line:
                raise AssertionError(
                    f"the pinning check still filters with `{line.strip()}`. A basic regular "
                    "expression reads `{40}` literally, so this removes nothing.")


def test_a_tag_pin_is_still_reported(tmp_path):
    body = "jobs:\n  a:\n    steps:\n      - uses: actions/checkout@v4\n"
    code, output = _run_pinning_check(body, tmp_path)
    assert "@v4" in output, f"a real tag pin was not reported:\n{output}"
    assert "::warning" in output, output


def test_a_sha_pin_is_not_reported(tmp_path):
    body = ("jobs:\n  a:\n    steps:\n"
            "      - uses: actions/setup-python@3d3c42e5aac5ba805825da76410c181273ba90b1\n")
    _code, output = _run_pinning_check(body, tmp_path)
    assert "::warning" not in output, f"a properly SHA-pinned action was reported:\n{output}"


def test_a_tag_pin_naming_a_sha_elsewhere_is_still_reported(tmp_path):
    """The case that makes `-E` the wrong fix.

    A tag-pinned action whose line also mentions the SHA it was upgraded from is still
    tag-pinned. With `-E` added to the old filter, the 40-hex mention swallows the line and the
    finding is lost; measured on this exact input before the change.
    """
    body = ("jobs:\n  a:\n    steps:\n"
            "      - uses: owner/repo@v1 upgraded-from @deadbeef1234567890abcdef1234567890abcdef12\n")
    _code, output = _run_pinning_check(body, tmp_path)
    assert "::warning" in output, (
        "a tag pin was dropped because its line also names a SHA. That is what adding `-E` to the "
        f"old filter would have done:\n{output}")


def test_a_uses_inside_a_comment_is_not_reported(tmp_path):
    """Prose is not a pin. Two such lines exist in the repository today, and both were reported."""
    body = "jobs:\n  a:\n    steps:\n      # - uses: actions/checkout@v4\n"
    _code, output = _run_pinning_check(body, tmp_path)
    assert "::warning" not in output, f"a comment was reported as an unpinned action:\n{output}"


# ── example-capture.yml ────────────────────────────────────────────────────────────────────────────

def test_the_example_capture_step_does_not_swallow_its_own_failure():
    """`if: failure()` after a step that always exits 0 is a step that never runs.

    `example-capture.yml` is a file other repositories copy, so a dead capture is a dead pattern
    being taught. The rule is general: within one job, no `run:` may end in `|| true` when a
    later step's `if:` depends on that run having failed.
    """
    for path in sorted(set(WORKFLOWS.glob("*.yml")) | set(WORKFLOWS.glob("*.yaml"))):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, job in (document.get("jobs") or {}).items():
            steps = (job or {}).get("steps") or []
            for index, step in enumerate(steps):
                run = str(step.get("run", ""))
                if not re.search(r"\|\|\s*true\s*$", run.rstrip()):
                    continue
                later = steps[index + 1:]
                guarded = [s for s in later if "failure()" in str(s.get("if", ""))]
                if not guarded:
                    continue
                raise AssertionError(
                    f"{path.name}:{job_name} step {index} ends in `|| true`, so "
                    f"{len(guarded)} later step(s) gated on `if: failure()` can never run: "
                    f"{[s.get('name') for s in guarded]}")


def test_the_example_still_contains_a_capture_step():
    """The regression guard for the regression guard: removing `|| true` must not have taken the
    capture with it, and the file must still be the example it claims to be."""
    document = yaml.safe_load(EXAMPLE_CAPTURE.read_text(encoding="utf-8"))
    steps = [s for job in document["jobs"].values() for s in job.get("steps", [])]
    uses = [str(s.get("uses", "")) for s in steps]
    assert any("misaka-capture" in u for u in uses), (
        "example-capture.yml no longer demonstrates the capture it exists to document")
    assert "not active" in str(document.get("name", "")).lower(), (
        "the file is still an example; if it became a real workflow its name and trigger would "
        "have to change with it")
