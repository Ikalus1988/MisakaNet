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
import subprocess
import tempfile
from pathlib import Path
from typing import Any

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


def _run(command: str, workdir: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, shell=True, cwd=workdir, text=True, capture_output=True, timeout=timeout)


def verify_fixture(name: str) -> dict[str, Any]:
    fixture = load_fixture(name)
    path = Path(fixture["path"])
    expected = fixture["expected"]
    workdir = Path(tempfile.mkdtemp(prefix=f"misakanet-fixture-{name}-"))
    try:
        setup = subprocess.run([str(path / "setup.sh"), str(workdir)], text=True, capture_output=True, timeout=10)
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
        subprocess.run([str(path / "teardown.sh"), str(workdir)], text=True, capture_output=True, timeout=10)
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
