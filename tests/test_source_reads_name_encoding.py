#!/usr/bin/env python3
"""Every `read_text()` / `write_text()` in the maintained Python names its encoding (#4382).

Why this is a gate and not a convention: on 2026-11-03 three tests in `tests/` failed on a
Chinese-locale Windows (`locale.getpreferredencoding() == "cp936"`) purely because the files they
read are full of lesson text — `lessons/index.md` is 16 KB of non-ASCII — while CI (Linux, UTF-8)
stayed green. #4359 fixed the same class in `scripts/` and `misakanet/`; this is that rule one
directory over, and it is a rule now.

The scanner is **AST-based, not grep-based**: a call may span lines, `read_text()` inside a comment
must not be reported, and an already-explicit `read_text(errors="replace", encoding="utf-8")` must be
accepted. It then scans one more place an AST walk of the outer file cannot see: **Python programs
embedded in string literals** (the fake probes the tests write to disk and execute). That half was
the one case the issue's `grep` caught and an AST-only gate would have missed. The self-tests at the bottom feed the scanner a planted defect
and a correct call, because a gate that cannot fail on a known-bad input is not a gate — the
property this repository now expects of every one of them.
"""
from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

#: The trees whose Python runs on a contributor's machine and on CI. `archive/` is excluded on
#: purpose (it holds broken files by design — see `pyproject.toml`'s ruff exclusion).
TREES = ("tests", "scripts", "misakanet")

TEXT_CALLS = ("read_text", "write_text")


def _parse(source: str):
    """`ast.parse`, with the SyntaxWarnings other files' docstrings emit kept out of the report.

    The gate compiles every maintained file, and one of them carries `\b` in a docstring; that is a
    pre-existing warning about a different file, and printing it from this gate would make the gate
    look like the thing that is broken.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source)


def calls_without_encoding(source: str) -> list[tuple[int, str]]:
    """`(line, method)` for every text call in `source` that names no encoding.

    Parses, so a call inside a comment or a string is invisible and a multi-line call is seen in
    full — the two ways a regex version of this check would be both noisy and blind.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(_parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in TEXT_CALLS:
            continue
        if any(keyword.arg == "encoding" for keyword in node.keywords):
            continue
        found.append((node.lineno, node.func.attr))
    return sorted(found)


#: Programs that this repository writes to disk and runs — a fake probe, a generated script. They
#: are string constants to the outer file, so an AST walk of the outer file cannot see their calls.
EMBEDDED_ALLOWED_FILES = ("tests/test_source_reads_name_encoding.py",)


def embedded_bare_calls(source: str) -> list[tuple[int, int]]:
    """`(outer_line, count)` for string literals that parse as Python and call text I/O bare."""
    found: list[tuple[int, int]] = []
    for node in ast.walk(_parse(source)):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        program = node.value
        if "read_text" not in program and "write_text" not in program:
            continue
        try:
            inner = _parse(program)
        except SyntaxError:
            continue  # prose, a fragment, a docstring example that is not a program
        bare = 0
        for call in ast.walk(inner):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr in TEXT_CALLS
                    and not any(keyword.arg == "encoding" for keyword in call.keywords)):
                bare += 1
        if bare:
            found.append((node.lineno, bare))
    return found


def repo_calls_without_encoding(trees: tuple[str, ...] = TREES) -> list[str]:
    """`path:line method` for every violation in the maintained trees."""
    violations: list[str] = []
    for tree in trees:
        for path in sorted((REPO / tree).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for line, method in calls_without_encoding(source):
                violations.append(f"{path.relative_to(REPO)}:{line} {method}()")
    return violations


def embedded_violations() -> list[str]:
    violations: list[str] = []
    for tree in TREES:
        for path in sorted((REPO / tree).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(REPO).as_posix()
            if rel in EMBEDDED_ALLOWED_FILES:
                continue  # its fixtures are bare on purpose — they test this scanner
            for line, count in embedded_bare_calls(path.read_text(encoding="utf-8")):
                violations.append(f"{rel}:{line} ({count} bare call(s) in an embedded program)")
    return violations


def test_every_text_read_and_write_names_its_encoding():
    violations = repo_calls_without_encoding()
    assert violations == [], (
        "these text I/O calls encode or decode with the platform default, which is `cp936` on the "
        "Windows this project's users are on and UTF-8 on CI — the same suite, two answers. Add "
        "`encoding=\"utf-8\"`:\n  " + "\n  ".join(violations)
    )


def test_embedded_programs_name_their_encoding_too():
    """The fake-probe shape: a string that is a program, executed on this machine's locale."""
    violations = embedded_violations()
    assert violations == [], (
        "these string literals are Python programs this repository writes to disk and runs; their "
        "text I/O uses the platform default (cp936 on Windows):\n  " + "\n  ".join(violations)
    )


# ── the gate can see the defect it forbids ───────────────────────────────────────────────────────

def test_the_scanner_flags_a_bare_read():
    assert calls_without_encoding("data = path.read_text()\n") == [(1, "read_text")]


def test_the_scanner_flags_a_bare_write():
    assert calls_without_encoding("path.write_text('x')\n") == [(1, "write_text")]


def test_the_scanner_accepts_an_explicit_encoding():
    assert calls_without_encoding("path.read_text(encoding='utf-8')\n") == []
    assert calls_without_encoding("path.write_text('x', encoding='utf-8')\n") == []


def test_the_scanner_accepts_encoding_after_another_keyword():
    """`read_text(errors="replace")` is exactly the shape that was skipped by a regex fix."""
    source = 'cred.read_text(errors="replace", encoding="utf-8")\n'
    assert calls_without_encoding(source) == []
    assert calls_without_encoding('cred.read_text(errors="replace")\n') == [(1, "read_text")]


def test_the_scanner_reads_a_multi_line_call():
    source = 'data = (path / "x").write_text(\n    payload,\n)\n'
    assert calls_without_encoding(source) == [(1, "write_text")]


def test_a_call_in_a_comment_or_a_string_is_not_reported():
    source = (
        "# path.read_text() in prose is not a call\n"
        'MESSAGE = "path.write_text(data)"\n'
    )
    assert calls_without_encoding(source) == []


def test_the_gate_covers_the_three_maintained_trees():
    """A tree added later must be added here, not silently left out of the rule."""
    assert TREES == ("tests", "scripts", "misakanet")


def test_the_scanner_sees_a_bare_call_inside_an_embedded_program():
    """`grep` caught this one; an AST walk of the outer file would not."""
    source = 'PROBE = """import pathlib\npathlib.Path("x").read_text()\n"""\n'
    assert embedded_bare_calls(source) == [(1, 1)]


def test_an_embedded_program_with_encodings_is_accepted():
    source = 'PROBE = """import pathlib\npathlib.Path("x").read_text(encoding="utf-8")\n"""\n'
    assert embedded_bare_calls(source) == []


def test_prose_that_mentions_read_text_is_not_an_embedded_program():
    source = 'DOC = """Call `read_text()` only with an encoding; see the note above."""\n'
    assert embedded_bare_calls(source) == []
