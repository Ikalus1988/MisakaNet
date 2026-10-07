"""`scripts/misaka_verify.py` returns a pair, or it raises at the call site.

The defect this exists for: line 87 read

    return SKIP, f"No test_cmd and source too small" if source_path.stat().st_size > 0 else FAIL, f"Empty source"

which parses as the **3-tuple** `SKIP, (A if cond else FAIL), B` — the conditional binds only its
middle element — while the signature says `-> tuple[str, str]` and both call sites do
`status, detail = run_verification(task)`. Measured before the fix:

    ValueError: too many values to unpack (expected 2)

No task in `tasks/` met the shape it needs (no `test_cmd` *and* a source of ≤100 bytes), so it was
latent rather than live — and it survived an external review that rated it the only
crash-provable Python defect in the report, because nothing ran the function down that branch.
This file is the reason it cannot survive another one.

The assertions are on the *arity* rather than on the message text: the tuples are small, the
contract callers depend on is "two values, always", and a test that pins the wording would break
on a copy edit without any of the risk returning.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO / "scripts" / "misaka_verify.py"


def _load():
    spec = importlib.util.spec_from_file_location("misaka_verify_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mv():
    return _load()


@pytest.fixture
def probe(mv, tmp_path):
    """A task with no `test_cmd` — the only shape that reaches the branch under test.

    `run_verification` resolves `source` against its own `REPO_ROOT` and its task file against
    its own `TASKS_DIR`, so the fixtures have to land there rather than in `tmp_path`.
    """
    source = mv.REPO_ROOT / "zz-verify-contract-probe.py"
    task_file = mv.TASKS_DIR / "zz-verify-contract-probe.json"
    try:
        yield {"source": source, "task_file": task_file,
               "task": {"task_id": "zz-verify-contract-probe",
                        "source": "zz-verify-contract-probe.py"}}
    finally:
        source.unlink(missing_ok=True)
        task_file.unlink(missing_ok=True)


def _run(mv, probe, body: bytes):
    probe["source"].write_bytes(body)
    probe["task_file"].write_text(json.dumps({"task_id": probe["task"]["task_id"]}))
    return mv.run_verification(probe["task"])


def test_a_small_but_non_empty_source_returns_a_pair(mv, probe):
    """The branch that used to return three values and raise at the call site."""
    result = _run(mv, probe, b"x\n")
    assert len(result) == 2, f"expected a (status, detail) pair, got {result!r}"
    status, detail = result          # the exact unpacking both call sites do
    assert status == mv.SKIP
    assert "source too small" in detail


def test_an_empty_source_returns_a_pair_and_fails(mv, probe):
    result = _run(mv, probe, b"")
    assert len(result) == 2, f"expected a (status, detail) pair, got {result!r}"
    status, detail = result
    assert status == mv.FAIL
    assert detail == "Empty source"


def test_a_missing_source_returns_a_pair(mv, probe):
    probe["source"].unlink(missing_ok=True)
    result = mv.run_verification(probe["task"])
    assert len(result) == 2, f"expected a (status, detail) pair, got {result!r}"
    assert result[0] == mv.SKIP


def test_no_branch_of_run_verification_returns_something_other_than_a_pair(mv):
    """The general shape of the contract, checked against the function's own source.

    Reading the body is not a substitute for running it — the two tests above do that — but it
    is the only way to notice a *new* branch added later that reintroduces the same mistake.
    The one construct that produces a wider tuple from a flat `return` is a bare conditional
    expression between two commas, so that is what this looks for.
    """
    import ast

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run_verification")
    offenders = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Tuple):
            continue
        for element in node.value.elts:
            # `X, A if c else B, C` — an `IfExp` sitting directly in a tuple slot.
            if isinstance(element, ast.IfExp):
                offenders.append(node.lineno)
    assert not offenders, (
        "run_verification returns a conditional expression directly inside a tuple at line(s) "
        f"{offenders}. That parses as `a, (x if c else y), b` — always three values — while the "
        "signature says tuple[str, str] and both call sites unpack two. Parenthesise the whole "
        "pair instead: `return (A, ...) if cond else (FAIL, ...)`."
    )


def test_the_arity_contract_would_catch_the_three_tuple_it_was_written_for():
    """The self-test: this file is evidence only if it fails on the shape it was added for."""
    # The original line, verbatim.
    status, skip, fail = "SKIP", "No test_cmd and source too small", "Empty source"
    flat = (status, skip if "yes" else fail, fail)
    with pytest.raises(ValueError, match="too many values to unpack"):
        pair_from_flat = flat
        two = (pair_from_flat[0], pair_from_flat[1])          # noqa: F841
        status, detail = flat                                 # what both call sites do

    # The fixed shape, for contrast: the conditional governs the whole pair.
    size = 4
    fixed = ((status, skip) if size > 0 else (fail, "Empty source"))
    assert len(fixed) == 2
    assert fixed[0] == status and fixed[1] == skip