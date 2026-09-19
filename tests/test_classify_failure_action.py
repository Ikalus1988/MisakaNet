#!/usr/bin/env python3
"""The failure classifier must not call a real bug "flaky".

`.github/actions/classify-failure/` decides whether the self-heal harness retries a failed command
and whether the maintainer gets notified (`ci-self-heal.yml` notifies only when `should_retry` is
false). Its category checks used bare substring matching against the lower-cased log, and the
`race_condition` list contains `"race"` — which is inside **"Traceback"**, the first line of every
Python traceback. So:

    ModuleNotFoundError: No module named 'requests'   ->  race_condition, should_retry=true

A real bug was retried and nobody was told. Reproduced by running this action's own script, which is
what these tests do too: the shell step is extracted from `action.yml` and executed with a table of
sample logs, so the assertions are about the deployed decision rather than a paraphrase of it.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML extracts the step's script")

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github" / "actions" / "classify-failure" / "action.yml"

POSIX_ONLY = pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None,
    reason="the step is a bash step; these legs do not run it",
)

# log text -> (failure_class, should_retry)
CASES = {
    # A Python traceback is a real bug. Before the fix this returned race_condition/true, because
    # "Traceback" contains "race".
    "Traceback (most recent call last):\n  File \"x.py\", line 3\nModuleNotFoundError: No module named 'requests'":
        ("real_bug", "false"),
    "SyntaxError: invalid syntax": ("real_bug", "false"),
    "OSError: [Errno 111] Connection refused": ("network_timeout", "true"),
    "ssl handshake failed": ("network_timeout", "true"),
    "Permission denied: /root/secret": ("permission_denied", "false"),
    "another process holds the lock": ("race_condition", "true"),
    "test passed on retry": ("flaky_test", "true"),
    "something odd happened": ("unknown", "true"),
}


def _step_script() -> str:
    workflow = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    for step in workflow["runs"]["steps"]:
        if step.get("id") == "classify":
            return step["run"]
    raise AssertionError("the classify step disappeared from the action")


@POSIX_ONLY
def test_each_sample_log_gets_the_right_class_and_retry_decision(tmp_path):
    script = tmp_path / "classify.sh"
    script.write_text(_step_script(), encoding="utf-8")
    wrong = []
    for log_text, (expected_class, expected_retry) in CASES.items():
        log = tmp_path / "failure.log"
        log.write_text(log_text + "\n", encoding="utf-8")
        output = tmp_path / "github_output"
        output.write_text("", encoding="utf-8")
        result = subprocess.run(
            ["bash", str(script)],
            env={**os.environ, "LOG_FILE": str(log), "EXIT_CODE": "1", "GITHUB_OUTPUT": str(output)},
            capture_output=True, text=True, check=True,
        )
        written = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if "=" in line)
        if written.get("failure_class") != expected_class or written.get("should_retry") != expected_retry:
            wrong.append(f"{log_text.splitlines()[0][:48]!r}: got "
                         f"{written.get('failure_class')}/{written.get('should_retry')}, "
                         f"expected {expected_class}/{expected_retry}")
    assert not wrong, "the classifier misclassifies these failures:\n  - " + "\n  - ".join(wrong)


def test_the_classifier_does_not_match_inside_longer_words():
    """The property behind the bug, asserted directly so it cannot come back in another category."""
    script = _step_script()
    assert "def matches(" in script, (
        "category matching must go through the word-boundary helper; bare `p in log_lower` matches "
        "'race' inside 'Traceback'"
    )
    assert "in log_lower for p in" not in script, "a category check still uses substring matching"
    assert "re.escape(p)" in script, "the helper must escape the pattern before embedding it"
