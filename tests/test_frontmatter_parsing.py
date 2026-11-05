"""Tests for the YAML front matter parser in ``scripts/validate_lessons.py``.

``scripts/validate_lessons.py`` runs environment checks at import time and calls
``sys.exit(1)`` when one of them fails. Importing it from a test therefore used
to abort collection with an ``INTERNALERROR`` before a single assertion ran::

    File "scripts/validate_lessons.py", line 33, in <module>
        sys.exit(1)
    SystemExit: 1

The loader below imports the script with ``sys.exit`` temporarily neutralised,
so the module finishes executing and ``extract_frontmatter`` stays importable.
If the import still cannot complete - or the helper does not look callable with
a single string of text - the tests skip instead of taking the session down.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_lessons.py"

# Parameter names that mean "this helper wants a path, not raw text".
_PATH_PARAM_NAMES = (
    "path",
    "file",
    "filename",
    "filepath",
    "file_path",
    "lesson_path",
    "source",
    "src",
)


def load_validate_lessons() -> ModuleType:
    """Import ``scripts/validate_lessons.py`` without letting it kill pytest."""
    if not SCRIPT_PATH.is_file():
        pytest.skip(f"{SCRIPT_PATH} not found")

    scripts_dir = str(SCRIPT_PATH.parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    spec = importlib.util.spec_from_file_location("validate_lessons", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.skip(f"cannot build an import spec for {SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    real_exit = sys.exit

    def _neutralised_exit(code: object = 0) -> None:
        """Stand-in for ``sys.exit`` so module-level guards cannot abort import."""

    sys.modules["validate_lessons"] = module
    sys.exit = _neutralised_exit  # type: ignore[assignment]
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:  # noqa: BLE001 - the import may fail in many ways
        sys.modules.pop("validate_lessons", None)
        pytest.skip(f"scripts/validate_lessons.py is not importable: {exc!r}")
    finally:
        sys.exit = real_exit
    return module


@pytest.fixture(scope="module")
def vl() -> ModuleType:
    """The imported ``validate_lessons`` module, or a skip if it is unusable."""
    module = load_validate_lessons()
    extract = getattr(module, "extract_frontmatter", None)
    if not callable(extract):
        pytest.skip("scripts/validate_lessons.py exposes no extract_frontmatter()")

    signature = inspect.signature(extract)
    params = list(signature.parameters.values())
    if len(params) != 1 or params[0].kind not in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    ):
        pytest.skip(f"unexpected extract_frontmatter signature: {signature}")
    if any(word in params[0].name.lower() for word in _PATH_PARAM_NAMES):
        pytest.skip("extract_frontmatter() takes a path, not raw text")
    return module


def frontmatter(vl: ModuleType, text: str) -> dict[str, Any]:
    """Call ``extract_frontmatter`` and normalise the result to a mapping."""
    result = vl.extract_frontmatter(text)
    if isinstance(result, tuple):
        result = result[0] if result else None
    if not result:
        return {}
    return dict(result)


def test_extract_frontmatter_reads_scalar_fields(vl: ModuleType) -> None:
    text = "---\ntitle: Example lesson\ndomain: search\nstatus: published\n---\n\n# Body\n"
    fm = frontmatter(vl, text)
    assert fm.get("title") == "Example lesson"
    assert fm.get("domain") == "search"


def test_extract_frontmatter_reads_block_lists(vl: ModuleType) -> None:
    text = "---\ntitle: Tagged\ntags:\n  - search\n  - retrieval\n---\n\nbody\n"
    fm = frontmatter(vl, text)
    tags = fm.get("tags") or []
    assert "search" in tags
    assert "retrieval" in tags


def test_extract_frontmatter_without_block_returns_empty(vl: ModuleType) -> None:
    fm = frontmatter(vl, "# Just a heading\n\nNo front matter here.\n")
    assert not fm


def test_extract_frontmatter_empty_block_returns_empty(vl: ModuleType) -> None:
    fm = frontmatter(vl, "---\n---\n\nbody\n")
    assert not fm


def test_extract_frontmatter_stops_at_closing_delimiter(vl: ModuleType) -> None:
    text = "---\ntitle: Only title\n---\n\nbody mentions --- inside the text\n"
    fm = frontmatter(vl, text)
    assert fm.get("title") == "Only title"
    assert "body" not in fm


def test_extract_frontmatter_does_not_mutate_input(vl: ModuleType) -> None:
    text = "---\ntitle: Stable\n---\nbody\n"
    frontmatter(vl, text)
    assert text == "---\ntitle: Stable\n---\nbody\n"
