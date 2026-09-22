"""Mechanical shape checks for bounty pull requests.

The checker deliberately judges only repository shape.  It does not attempt to
assess whether an implementation is good, complete, or relevant to an issue.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_ROOT_SOLUTION = re.compile(r"^(?:solution|test_solution)[^/]*\.py$")
_TEST_SOLUTION = re.compile(r"^tests/test_solution[^/]*\.py$")
_PROJECT_VALUE = re.compile(r"^\s*(name|version)\s*=\s*[\"']([^\"']+)[\"']\s*(?:#.*)?$")


@dataclass(frozen=True)
class Decision:
    """Result of the mechanical shape decision."""

    hit: bool
    reasons: tuple[str, ...] = ()


def _normalise_files(changed_files: Iterable[str]) -> tuple[str, ...]:
    """Return unique, repository-relative paths in stable order."""

    normalised = set()
    for raw_path in changed_files:
        path = raw_path.strip()
        if path.startswith("./"):
            path = path[2:]
        if path:
            normalised.add(path)
    return tuple(sorted(normalised))


def _project_identity(pyproject: str | None) -> tuple[str, str] | None:
    """Extract the package name/version from the top-level ``[project]`` table.

    A small line parser keeps this checker dependency-free and works on Python
    3.10.  Missing or malformed project metadata is intentionally represented
    as ``None``: deleting the package identity is itself a suspicious shape.
    """

    if pyproject is None:
        return None

    section: str | None = None
    values: dict[str, str] = {}
    for raw_line in pyproject.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section != "project":
            continue
        match = _PROJECT_VALUE.match(raw_line)
        if match:
            values[match.group(1)] = match.group(2)

    if "name" not in values or "version" not in values:
        return None
    return values["name"], values["version"]


def decide(
    changed_files: Iterable[str],
    *,
    base_pyproject: str | None = None,
    head_pyproject: str | None = None,
    enable_template_shape_rule: bool = True,
) -> Decision:
    """Apply the bounty claim shape rules.

    ``base_pyproject`` and ``head_pyproject`` are optional so callers that only
    have a file list can still use the root-stub and file-set rules.  A caller
    inspecting a changed ``pyproject.toml`` should provide both snapshots to
    enable the package-identity rule.
    """

    files = _normalise_files(changed_files)
    reasons: list[str] = []

    if "pyproject.toml" in files and _project_identity(base_pyproject) != _project_identity(
        head_pyproject
    ):
        reasons.append(
            "pyproject.toml changes or removes the [project] name/version identity"
        )

    root_stubs = tuple(path for path in files if _ROOT_SOLUTION.fullmatch(path))
    if root_stubs:
        reasons.append(
            "repository root contains solution*.py or test_solution*.py: "
            + ", ".join(root_stubs)
        )

    template_files = {
        path
        for path in files
        if path == "pyproject.toml"
        or _ROOT_SOLUTION.fullmatch(path)
        or _TEST_SOLUTION.fullmatch(path)
    }
    has_solution_test = any(
        _ROOT_SOLUTION.fullmatch(path) or _TEST_SOLUTION.fullmatch(path)
        for path in files
    )
    if (
        enable_template_shape_rule
        and "pyproject.toml" in files
        and has_solution_test
        and len(template_files) == len(files)
    ):
        reasons.append(
            "changed-file set is limited to pyproject.toml plus "
            "solution/test_solution template files"
        )

    return Decision(hit=bool(reasons), reasons=tuple(reasons))


def _read_optional(path: str | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    return file_path.read_text(encoding="utf-8") if file_path.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changed-files",
        required=True,
        help="Text file containing one changed repository path per line",
    )
    parser.add_argument("--base-pyproject", help="Base-version pyproject.toml snapshot")
    parser.add_argument("--head-pyproject", help="Head-version pyproject.toml snapshot")
    parser.add_argument("--json", action="store_true", help="Emit a JSON decision")
    args = parser.parse_args()

    changed_files = Path(args.changed_files).read_text(encoding="utf-8").splitlines()
    decision = decide(
        changed_files,
        base_pyproject=_read_optional(args.base_pyproject),
        head_pyproject=_read_optional(args.head_pyproject),
    )
    payload = {"hit": decision.hit, "reasons": list(decision.reasons)}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("HIT" if decision.hit else "PASS")
        for reason in decision.reasons:
            print(f"- {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
