#!/usr/bin/env python3
"""YAML-frontmatter lessons must never be indexed with slug/dir metadata.

Why this exists
---------------
`scripts/update_lessons_json.py` and `scripts/sync_lessons_to_d1.py` both parse
lesson frontmatter "JSON first, YAML fallback", and both used to end the
fallback with a bare ``return {}``:

    try:
        import yaml
        fm = yaml.safe_load(raw)
        if isinstance(fm, dict):
            return fm
    except Exception:
        pass
    return {}

The callers then read ``fm.get("title", path.stem)`` and
``fm.get("domain", path.parent.name)``, so a frontmatter that failed to parse
degraded into a *plausible-looking* record instead of an error. The two CI
workflows that run these scripts installed no Python dependencies at all
(``actions/setup-python`` + ``wrangler`` only), so in CI ``import yaml`` raised
ImportError, ``except Exception`` swallowed it, and every lesson with YAML
frontmatter (376 of 440 files when this test was written) was written to
``data/lessons.json`` and upserted into the D1 database with its file stem as
the title, the parent directory as the domain and empty tags — while CI stayed
green and ``data/lessons.json`` was committed that way.

So there are two invariants to hold, and this file tests both:

1. parsing: a non-JSON frontmatter block with no PyYAML available is an error
   (the JSON path and "no frontmatter at all" keep their old behaviour);
2. wiring: every workflow that runs a repo script which imports ``yaml``
   installs the dependencies first — the part that actually stops the bug from
   coming back, because the parser fix alone turns a silent corruption into a
   red workflow only *after* someone removes the dependency again.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))
LESSONS = REPO / "lessons"

# A representative lesson: YAML frontmatter whose title/domain/tags differ from
# what the slug/dir fallback would invent (stem `tmp-lesson`, parent dir `tmp`).
LESSON_BODY = """---
title: Redis connection pool exhaustion under burst load
domain: devops
tags: [redis, connection-pool, timeout]
status: active
language: en
summary: Pool size, not the timeout, is what surfaces first.
---

## Problem

Burst traffic exhausted the pool.

## Root Cause

The pool was sized for average load.

## Fix

Raise max_connections and add a bounded wait.

## Verification

Reproduce with `wrk -c 200`.
"""

JSON_LESSON_BODY = """---
{"title": "JSON-frontmatter lesson", "domain": "networking", "tags": ["dns"]}
---

## Problem

Resolvers timed out.
"""


# ── the two parsers under test ────────────────────────────────────────────────


def _load_script(stem: str) -> ModuleType:
    """Import ``scripts/<stem>.py`` by path — ``scripts/`` is not a package."""
    path = REPO / "scripts" / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(f"_fm_guard_{stem}", path)
    assert spec and spec.loader, f"could not load scripts/{stem}.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PARSERS = {
    "update_lessons_json.parse_frontmatter": _load_script("update_lessons_json").parse_frontmatter,
    "sync_lessons_to_d1.parse_frontmatter": _load_script("sync_lessons_to_d1").parse_frontmatter,
}


@pytest.fixture(params=sorted(PARSERS), ids=lambda key: key.split(".")[0])
def parse_frontmatter(request):
    return PARSERS[request.param]


class _BlockYaml:
    """A meta_path finder that makes ``import yaml`` raise ImportError.

    Deleting ``sys.modules["yaml"]`` is not enough on its own: an already
    imported module is returned from the cache without consulting meta_path, and
    other tests in this suite do import yaml.
    """

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "yaml" or fullname.startswith("yaml."):
            raise ImportError("No module named 'yaml' (simulated: PyYAML not installed)")
        return None


@pytest.fixture
def pyyaml_missing(monkeypatch):
    """Simulate a checkout where PyYAML was never installed (i.e. CI before the fix)."""
    monkeypatch.delitem(sys.modules, "yaml", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_BlockYaml(), *sys.meta_path])
    with pytest.raises(ImportError):
        __import__("yaml")  # guard the guard: the simulation must actually block
    yield


# ── 1. parsing ────────────────────────────────────────────────────────────────


def test_yaml_frontmatter_lesson_parses_to_its_metadata(tmp_path, parse_frontmatter):
    """The reported bug, stated positively: YAML frontmatter yields real metadata."""
    lesson = tmp_path / "tmp" / "tmp-lesson.md"
    lesson.parent.mkdir()
    lesson.write_text(LESSON_BODY, encoding="utf-8")

    fm = parse_frontmatter(lesson.read_text(encoding="utf-8"))

    assert fm["title"] == "Redis connection pool exhaustion under burst load"
    assert fm["domain"] == "devops"
    assert fm["tags"] == ["redis", "connection-pool", "timeout"]
    # The two fields the silent fallback replaced with path-derived guesses.
    assert fm["title"] != lesson.stem
    assert fm["domain"] != lesson.parent.name


def test_real_yaml_frontmatter_lesson_parses_to_its_metadata(parse_frontmatter):
    """Same assertion against a file that actually ships in lessons/."""
    lesson, raw = _first_yaml_lesson_with_domain()

    fm = parse_frontmatter(lesson.read_text(encoding="utf-8", errors="replace"))

    # Read the two scalars out of the block without a YAML parser (a regex on
    # the frontmatter is deliberately independent of the parser under test).
    expected_title = re.search(r"^title:[ \t]*(.+)$", raw, re.M).group(1).strip().strip("'\"")
    expected_domain = re.search(r"^domain:[ \t]*(.+)$", raw, re.M).group(1).strip().strip("'\"")

    assert fm["title"] == expected_title, f"{lesson.name}: title fell back to the slug"
    assert fm["domain"] == expected_domain, f"{lesson.name}: domain fell back to the directory"
    assert fm["tags"], f"{lesson.name}: tags were dropped"
    # The file was chosen precisely because both fallbacks would be visible.
    assert fm["title"] != lesson.stem
    assert fm["domain"] != lesson.parent.name


def test_yaml_frontmatter_without_pyyaml_raises(pyyaml_missing, parse_frontmatter):
    """No PyYAML + YAML frontmatter → loud error, never a slug/dir record."""
    with pytest.raises(RuntimeError) as excinfo:
        parse_frontmatter(LESSON_BODY)

    message = str(excinfo.value)
    assert "PyYAML" in message
    assert "pip install" in message, "the error must name the fix"


def test_json_frontmatter_still_parses_without_pyyaml(pyyaml_missing, parse_frontmatter):
    """The JSON path never needs PyYAML — it must keep working without it."""
    fm = parse_frontmatter(JSON_LESSON_BODY)

    assert fm == {"title": "JSON-frontmatter lesson", "domain": "networking", "tags": ["dns"]}


def test_no_frontmatter_still_returns_empty_without_pyyaml(pyyaml_missing, parse_frontmatter):
    """Unchanged behaviour: no frontmatter block at all is still an empty dict."""
    assert parse_frontmatter("# Just a heading\n\nSome content.\n") == {}
    assert parse_frontmatter("---\nnever closed\n") == {}


def _first_yaml_lesson_with_domain() -> tuple[Path, str]:
    """A YAML-frontmatter lesson whose metadata the fallbacks would visibly break.

    Chosen by scanning rather than hardcoded, so the test survives the lesson
    being renamed, retitled or deleted — it only requires that *some* lesson
    still exercises the case (and says so loudly if none does).
    """
    from misakanet.lesson_index import EXCLUDED_LESSON_FILES

    for path in sorted(LESSONS.rglob("*.md")):
        if path.name in EXCLUDED_LESSON_FILES or path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            continue
        end = text.find("\n---", 4)
        if end == -1:
            continue
        raw = text[4:end].strip()
        if not raw or raw.startswith("{"):
            continue
        if not re.search(r"^title:", raw, re.M) or not re.search(r"^domain:", raw, re.M):
            continue
        if not re.search(r"^tags:", raw, re.M):
            continue
        title = re.search(r"^title:[ \t]*(.+)$", raw, re.M).group(1).strip().strip("'\"")
        domain = re.search(r"^domain:[ \t]*(.+)$", raw, re.M).group(1).strip().strip("'\"")
        if title != path.stem and domain != path.parent.name:
            return path, raw
    pytest.fail("no YAML-frontmatter lesson with title/domain/tags left in lessons/ — "
                "either the corpus changed format or this scan is broken")


# ── 2. the workflows that run those parsers ───────────────────────────────────

# Where a repo-local module can live, for the transitive import scan below.
_MODULE_ROOTS = ("*.py", "scripts/*.py", "misakanet/**/*.py", ".github/scripts/*.py", "tests/*.py")
# `python3 scripts/foo.py`, `python scripts/foo.py` — any interpreter spelling.
_PYTHON_SCRIPT = re.compile(r"(?<![\w.-])python[0-9.]*\s+([\w./-]+\.py)")


def _repo_local_modules() -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for pattern in _MODULE_ROOTS:
        for path in REPO.glob(pattern):
            if "__pycache__" in path.parts:
                continue
            modules.setdefault(path.stem, path)
            modules.setdefault(str(path.relative_to(REPO).with_suffix("")).replace("/", "."), path)
    return modules


_MODULES = _repo_local_modules()


def _imports(path: Path) -> tuple[bool, set[str]]:
    """``(imports yaml directly?, every root module name imported)``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return False, set()
    direct = False
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module] if node.module and not node.level else []
        else:
            continue
        for name in names:
            root = name.split(".")[0]
            roots.add(root)
            direct |= root == "yaml"
    return direct, roots


def _needs_pyyaml(path: Path, _seen: set[Path] | None = None) -> bool:
    """Does this script need PyYAML — directly or through a repo module it imports?

    Mechanical on purpose: an earlier guard in this repo was defeated by
    hand-maintained lists, and a script that grows a `yaml` import must not need
    anyone to remember to update this test.
    """
    path = path.resolve()
    seen = _seen if _seen is not None else set()
    if path in seen or not path.exists():
        return False
    seen.add(path)
    direct, roots = _imports(path)
    if direct:
        return True
    for root in roots:
        module = _MODULES.get(root)
        if module is not None and module.resolve() != path and _needs_pyyaml(module, seen):
            return True
    return False


def _scripts_run_by(workflow: Path) -> set[Path]:
    """Repo scripts invoked as ``python <script>.py`` anywhere in the workflow.

    Two stated limits, both erring toward "ask for an install" rather than
    "stay quiet": a commented-out line is skipped, but a documented example
    inside a heredoc body is treated as a command, and the install check is
    per workflow rather than per job (a multi-job workflow that installs the
    dependency in one job would satisfy it).
    """
    found: set[Path] = set()
    text = workflow.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for match in _PYTHON_SCRIPT.finditer(line):
            candidate = (REPO / match.group(1)).resolve()
            if candidate.exists():
                found.add(candidate)
    return found


def test_every_workflow_running_a_yaml_importing_script_installs_dependencies():
    """A workflow that runs such a script must install its dependencies first."""
    needs_install: list[str] = []
    detected: set[str] = set()
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8", errors="replace")
        yaml_needing = sorted(p for p in _scripts_run_by(workflow) if _needs_pyyaml(p))
        if not yaml_needing:
            continue
        detected.add(workflow.name)
        if "pip install" not in text:
            names = ", ".join(str(p.relative_to(REPO)) for p in yaml_needing)
            needs_install.append(f"{workflow.name} (runs {names})")

    assert needs_install == [], (
        "these workflows run a script that imports yaml but install no Python dependencies; "
        "the script will fail (or, worse, degrade silently — this is how 376 YAML lessons "
        "were indexed with slug titles), so add `pip install -r requirements.txt`:\n  - "
        + "\n  - ".join(needs_install)
    )
    # Guard the guard: a broken glob/regex would make the assertion above vacuous.
    assert {"update-lessons.yml", "sync-d1.yml"} <= detected, (
        f"the scan stopped detecting the known offenders — found {sorted(detected)}"
    )


def test_parser_test_covers_both_scripts():
    """Both parsers of the same "JSON first, YAML fallback" shape stay in the net."""
    assert len(PARSERS) == 2


def test_json_fixture_is_valid_json():
    """The JSON fixture must not silently become YAML if its delimiters are edited."""
    body = JSON_LESSON_BODY.split("---")[1].strip()
    assert json.loads(body)["domain"] == "networking"
