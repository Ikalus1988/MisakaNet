#!/usr/bin/env python3
"""Every workflow and composite action must be valid YAML — GitHub's parser is not more forgiving.

`actions/classify-failure/action.yml` was not parseable and nothing noticed. Its `run: |` block
contains a Python heredoc whose body sat at column 0, which **ends the block scalar**: the remaining
lines then look like mapping keys with no value, and the document is a syntax error. The file had been
in that state since 2026-06-06 (#331), and `.github/workflows/ci-self-heal.yml` still references it —
the last runs of that workflow list steps 1–5 and then jump to 9, with the classify and notify steps
absent (run 27079171896).

The second half of this gate is duplicate mapping keys. PyYAML's `safe_load` **silently keeps the
last one**, so a duplicated `env:` block — which GitHub rejects outright — reads as a perfectly normal
workflow to every test in this repository. This gate walks the documents with a loader that raises
instead. It caught a duplicate `env:` in this session's own `release-please.yml` edit.

Both checks are cheap and both failure modes are invisible without them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML is the parser under test")

REPO = Path(__file__).resolve().parent.parent
TARGETS = sorted(
    list((REPO / ".github" / "workflows").glob("*.yml"))
    + list((REPO / ".github" / "workflows").glob("*.yaml"))
    + list((REPO / ".github" / "actions").glob("*/action.yml"))
    + list((REPO / ".github" / "actions").glob("*/action.yaml"))
    # The root action.yml is the one GitHub Marketplace publishes and the one external callers
    # resolve as `Ikalus1988/MisakaNet@v1`. It is the least forgiving file to get wrong and, until
    # it moved here, no glob in this gate could see it.
    + [p for p in (REPO / "action.yml", REPO / "action.yaml") if p.exists()]
)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last one."""


def _no_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                None, None,
                f"duplicate mapping key {key!r} (line {key_node.start_mark.line + 1})",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def test_the_gate_has_files_to_check():
    # Guard the guard: a broken glob would make every assertion below vacuous.
    assert len(TARGETS) > 50, f"expected the repository's workflows, found {len(TARGETS)}"
    assert any(p.name == "action.yml" for p in TARGETS), "composite actions must be covered"


def test_every_target_is_valid_yaml():
    problems = []
    for path in TARGETS:
        try:
            yaml.load(path.read_text(encoding="utf-8"), Loader=_StrictLoader)
        except yaml.YAMLError as exc:
            detail = str(exc).strip().splitlines()
            problems.append(f"{path.relative_to(REPO)}: {detail[-1] if detail else exc}")
    assert not problems, (
        "these files are not valid YAML, so GitHub cannot run them (a block scalar ends at the first "
        "line indented less than its body, which turns the rest of the file into a syntax error):\n  - "
        + "\n  - ".join(problems)
    )


def test_the_validity_check_notices_the_file_that_was_broken(tmp_path):
    """Guard the guard, on the actual defect: unindent a heredoc body and the gate must fail."""
    source = REPO / ".github" / "actions" / "classify-failure" / "action.yml"
    text = source.read_text(encoding="utf-8")
    broken = tmp_path / "action.yml"
    broken.write_text(text.replace("\n        import os\n", "\nimport os\n", 1), encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        yaml.load(broken.read_text(encoding="utf-8"), Loader=_StrictLoader)
    # And the untouched file parses, so the failure is the perturbation rather than the fixture.
    yaml.load(text, Loader=_StrictLoader)


def test_the_duplicate_key_check_notices_a_duplicated_block(tmp_path):
    duplicated = tmp_path / "wf.yml"
    duplicated.write_text("on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    env:\n      X: '1'\n"
                          "    env:\n      X: '2'\n", encoding="utf-8")
    with pytest.raises(yaml.constructor.ConstructorError):
        yaml.load(duplicated.read_text(encoding="utf-8"), Loader=_StrictLoader)
    # safe_load is the reason this gate exists: it accepts the same document happily.
    assert yaml.safe_load(duplicated.read_text(encoding="utf-8"))["jobs"]["a"]["env"] == {"X": "2"}
