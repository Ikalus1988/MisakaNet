#!/usr/bin/env python3
"""Load and verify the five canonical self-healing benchmark fixtures.

The fixture format is deliberately data-first: expected.json documents the
failure and verifier, while setup.sh and teardown.sh own the temporary state.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# `bench/` is not a package and this file is also loaded by path from the test suite, so
# make the shared resolver importable rather than assuming the repo root is on sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.posix_shell import find_posix_shell  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
REQUIRED_EXPECTED_FIELDS = {"scenario", "title", "failure", "expected_fix", "expected_outcome", "verifier"}
EXPECTED_OUTCOMES = {"success", "success_with_human_input", "timeout"}
VERIFIER_TYPES = {"command_exit", "file_content", "process_timeout"}


def fixture_names() -> list[str]:
    return sorted(path.name for path in FIXTURES_DIR.iterdir() if path.is_dir())


def load_fixture(name: str) -> dict[str, Any]:
    if name not in fixture_names():
        raise ValueError(f"unknown fixture {name!r}; choose from: {', '.join(fixture_names())}")
    path = FIXTURES_DIR / name
    expected_path = path / "expected.json"
    setup_path = path / "setup.sh"
    teardown_path = path / "teardown.sh"
    if not expected_path.is_file() or not setup_path.is_file() or not teardown_path.is_file():
        raise ValueError(f"fixture {name!r} must contain setup.sh, expected.json, and teardown.sh")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    missing = REQUIRED_EXPECTED_FIELDS - expected.keys()
    if missing:
        raise ValueError(f"fixture {name!r} missing expected.json fields: {sorted(missing)}")
    verifier = expected["verifier"]
    if verifier.get("type") not in VERIFIER_TYPES:
        raise ValueError(f"fixture {name!r} has unsupported verifier type {verifier.get('type')!r}")
    if expected["expected_outcome"] not in EXPECTED_OUTCOMES:
        raise ValueError(f"fixture {name!r} has unsupported expected outcome")
    return {"name": name, "path": str(path), "expected": expected}


def _kill_tree(process: subprocess.Popen) -> None:
    """Kill the process **and its children**.

    On Windows, `Popen.kill()` reaches only the shell that `shell=True` started. The process the
    shell spawned keeps running and keeps the stdout/stderr pipes open, so the `communicate()` that
    `subprocess.run` performs internally waits for an EOF that never arrives — the caller does not
    see its timeout, it hangs. Measured 2026-09-21: the `timeout-hang` fixture, whose entire purpose
    is to time out, hung the windows CI legs for the full 30-minute job bound, on three legs at once.
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def _run(command: str, workdir: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    """Run a fixture command with a real timeout — including on Windows.

    `subprocess.run(..., timeout=...)` is not enough here: see `_kill_tree`. The pipes are drained
    with their own bound so that even an unkillable child cannot turn a timeout into a hang.
    """
    process = subprocess.Popen(
        command, shell=True, cwd=workdir, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=(os.name != "nt"),   # so killpg can reach the whole tree on POSIX
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            stdout, stderr = "", ""
        # Re-raise: callers use this exception to mean "timed out as expected".
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def verify_fixture(name: str) -> dict[str, Any]:
    fixture = load_fixture(name)
    path = Path(fixture["path"])
    expected = fixture["expected"]
    workdir = Path(tempfile.mkdtemp(prefix=f"misakanet-fixture-{name}-"))
    try:
        # Fixtures are POSIX shell scripts: executing them directly works on macOS/Linux via
        # the shebang, but on Windows it raises WinError 193 (and `bash` there is the WSL
        # launcher, which may not work either). Run them through a shell we have probed.
        shell = find_posix_shell()
        if shell is None:
            return {"fixture": name, "status": "SKIP",
                    "reason": "no usable POSIX shell: the fixtures are shell scripts"}
        setup = subprocess.run([shell, str(path / "setup.sh"), str(workdir)], text=True,
                               capture_output=True, timeout=10, encoding="utf-8", errors="replace")
        if setup.returncode:
            return {"fixture": name, "status": "FAIL", "reason": "setup failed", "output": setup.stderr}

        verifier = expected["verifier"]
        verifier_type = verifier["type"]
        if verifier_type == "file_content":
            target = workdir / verifier["path"]
            content = target.read_text(encoding="utf-8") if target.exists() else ""
            if "must_contain" in verifier:
                ok = verifier["must_contain"] in content
            else:
                ok = verifier["must_not_contain"] not in content
            detail = f"checked {target}"
        elif verifier_type == "command_exit":
            result = _run(verifier["command"], workdir, 10)
            ok = result.returncode == verifier["expected_exit_code"]
            detail = f"exit={result.returncode}, expected={verifier['expected_exit_code']}"
        else:
            try:
                result = _run(verifier["command"], workdir, verifier["timeout_seconds"])
                ok = False
                detail = f"process exited with code {result.returncode} before timeout"
            except subprocess.TimeoutExpired:
                ok = True
                detail = f"timed out at {verifier['timeout_seconds']}s as expected"

        return {"fixture": name, "status": "PASS" if ok else "FAIL", "detail": detail}
    finally:
        if shell is not None:
            subprocess.run([shell, str(path / "teardown.sh"), str(workdir)], text=True,
                           capture_output=True, timeout=10, encoding="utf-8", errors="replace")
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list fixture names")
    parser.add_argument("--fixture", choices=fixture_names(), help="load and verify one fixture")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    args = parser.parse_args()

    if args.list:
        result: Any = [load_fixture(name)["expected"] | {"name": name} for name in fixture_names()]
    elif args.fixture:
        result = verify_fixture(args.fixture)
    else:
        result = [verify_fixture(name) for name in fixture_names()]

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.list:
        for item in result:
            print(f"{item['name']}: {item['title']}")
    elif isinstance(result, list):
        for item in result:
            print(f"{item['status']} {item['fixture']}: {item.get('detail', item.get('reason', ''))}")
    else:
        print(f"{result['status']} {result['fixture']}: {result.get('detail', result.get('reason', ''))}")
    return 0 if (args.list or all(item["status"] == "PASS" for item in (result if isinstance(result, list) else [result]))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
