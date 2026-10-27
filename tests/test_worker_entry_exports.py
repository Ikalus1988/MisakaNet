#!/usr/bin/env python3
"""A Worker's entry module may only export functions — workerd refuses to start otherwise.

**What went wrong, and how it stayed invisible.** `workers/register-proxy-sw.js` exports 130 names,
because the worker test files reach the helpers they assert against through them. Forty-four of
those 130 are constants (`ACTIVITY_CACHE_CONTROL`, `MCP_TOOLS`, `SUBMITTED_TEXT_CAP`, …). workerd
builds a map of the **entry** module's exports when it starts the Worker, and every entry in that
map has to be a function or an `ExportedHandler`:

    Uncaught TypeError: Incorrect type for map entry 'ACTIVITY_CACHE_CONTROL':
    the provided value is not of type 'function or ExportedHandler'.

So naming the implementation module as the entry made the Worker **unstartable** — `wrangler dev`
failed at startup every time, which means the Worker could not be run locally at all, and the only
thing a Worker is run locally for. It was invisible in CI because the worker tests import the
implementation module directly, and Node has no such rule: a constant is a perfectly good export
there. A Worker that cannot start and a Worker that works looked identical to every gate in this
repository — the same shape as #1825, where a bot that ran and a bot that found nothing had to be
told apart.

**The rule is about the entry, not about the module.** An imported module's exports are ordinary ES
module exports and are not restricted. That is why the fix is a separate entry file rather than a
migration of forty-four constants into a shared library: `workers/register-proxy-entry.js` exports
the default handler and nothing else, `register-proxy-sw.js` keeps every export the tests need, and
the Worker starts.

**How it reads the file.** With a regular expression, the export list is not a list: a `/*` inside
a regular-expression literal starts a "comment" that swallows the rest of the file — which is how
an earlier version of this gate found **zero** exports in a file with 130 of them and passed
silently. So the JavaScript is read with `scripts/check_page_scripts.py`'s tokenizer, the same one
that keeps `/[&<>"']/g` from swallowing the file it is in. Only the *import specifiers* come from a
line-anchored pattern, because a tokenizer cannot hand back the contents of a string literal and a
line that begins with `import` is not a coincidence in this repository.

**What this gate can and cannot see.** It reads the entry out of `workers/wrangler.toml`, so moving
the entry moves the gate with it. It can see a constant exported from the entry itself and a
constant re-exported from a module the entry imports; it cannot see through an import that leaves
the repository, and it cannot see a value whose kind is only known at runtime. Those are stated
rather than left to be discovered.

A gate that cannot go red is not a gate, so the fixtures at the bottom of this file assert that
the rule fires — on the exact shape this repository had.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from test_worker_compat_dates import load_config, wrangler_configs  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# The JavaScript tokenizer, borrowed from the page gate. It is the one thing in this repository
# that already reads hand-written JavaScript correctly.
_spec = importlib.util.spec_from_file_location(
    "check_page_scripts", REPO / "scripts" / "check_page_scripts.py"
)
assert _spec and _spec.loader
_pages = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pages)
tokenize = _pages.tokenize

#: workerd's own words, so a reader who hits this in a log knows where the rule came from.
WORKERD_MESSAGE = ("Incorrect type for map entry '{name}': the provided value is not of type "
                   "'function or ExportedHandler'.")

#: A declaration keyword and the kind of value it binds.
_KINDS = {"function": "function", "class": "class", "const": "const", "let": "let", "var": "var"}

#: `import x from './y.js'` / `import { A, B as C } from './y.js'` / both at once. Line-anchored:
#: the tokenizer cannot return the contents of a string literal, and a line that *begins* with
#: `import` is not a coincidence in this repository.
_IMPORT = re.compile(
    r"^[ \t]*import\s+(?:(?P<default>[A-Za-z_$][\w$]*)\s*,?\s*)?"
    r"(?:\{(?P<named>[^}]*)\}\s*)?from\s*['\"](?P<source>[^'\"]+)['\"]",
    re.M,
)


def _kind_map(tokens: list[tuple[str, str]]) -> dict[str, str]:
    """``{name: kind}`` for the top-level declarations of a module."""
    kinds: dict[str, str] = {}
    depth = 0
    for i, (kind, text) in enumerate(tokens):
        if kind == "punct":
            if text in ("(", "[", "{"):
                depth += 1
            elif text in (")", "]", "}"):
                depth -= 1
            continue
        if kind != "ident" or depth != 0 or text not in _KINDS:
            continue
        if i + 1 < len(tokens) and tokens[i + 1][0] == "ident":
            kinds.setdefault(tokens[i + 1][1], _KINDS[text])
    return kinds


def _named_exports(tokens: list[tuple[str, str]]) -> tuple[list[str], bool]:
    """``(named exports, has a default export)`` of a module.

    Three shapes: `export default …`, `export { a, b as c }` and `export function f(…)`.
    """
    names: list[str] = []
    has_default = False
    depth = 0
    for i, (kind, text) in enumerate(tokens):
        if kind == "punct":
            if text in ("(", "[", "{"):
                depth += 1
            elif text in (")", "]", "}"):
                depth -= 1
            continue
        if kind != "ident" or text != "export" or depth != 0:
            continue
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if nxt is None:
            continue
        if nxt == ("ident", "default"):
            has_default = True
            continue
        if nxt[0] == "punct" and nxt[1] == "{":
            # The export list: `a`, `b as c` — the exported name is the one *after* `as`.
            inner = 0
            exported: list[str] = []
            for j in range(i + 2, len(tokens)):
                k, t = tokens[j]
                if k == "punct" and t == "{":
                    inner += 1
                elif k == "punct" and t == "}":
                    if inner == 0:
                        break
                    inner -= 1
                elif k == "ident" and inner == 0:
                    exported.append(t)
            for j, name in enumerate(exported):
                # `a as b` — `b` is the exported name; `b` is followed by `,` or `}`.
                if j + 1 < len(exported) and exported[j + 1] == "as":
                    continue
                names.append(name)
            continue
        if nxt[0] == "ident" and nxt[1] in _KINDS:
            if i + 2 < len(tokens) and tokens[i + 2][0] == "ident":
                names.append(tokens[i + 2][1])
    return names, has_default


def _imports(text: str) -> dict[str, str]:
    """``{local name: module specifier}`` for the static imports of a module."""
    found: dict[str, str] = {}
    for match in _IMPORT.finditer(text):
        source = match.group("source")
        if match.group("default"):
            found[match.group("default")] = source
        named = match.group("named")
        if named:
            for part in named.split(","):
                part = part.strip()
                if not part:
                    continue
                local = part.split(" as ")[-1].strip()
                if local:
                    found[local] = source
    return found


def _is_class_expression(text: str, name: str) -> bool:
    """Whether a binding is a class expression — `const Foo = class extends DurableObject {}`.

    workerd accepts a class as an `ExportedHandler`, so a Durable Object bound this way is legal
    and must not be reported.
    """
    return bool(re.search(rf"^(?:export\s+)?(?:const|let|var)\s+{re.escape(name)}\s*=\s*class\b",
                          text, re.M))


def _resolve(name: str, path: Path, seen: set[Path]) -> str | None:
    """The kind of an exported name: ``function``/``class``, a non-function kind, or None.

    ``None`` means "this gate cannot tell" — an import that leaves the repository, or a name with
    no declaration anywhere it can reach.
    """
    if path in seen:
        return None
    seen.add(path)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    kinds = _kind_map(tokenize(text))
    kind = kinds.get(name)
    if kind in ("function", "class"):
        return kind
    if kind in ("const", "let", "var"):
        return "class" if _is_class_expression(text, name) else kind
    source = _imports(text).get(name)
    if source and source.startswith("."):
        return _resolve(name, (path.parent / source).resolve(), seen)
    return None


def entry_problems(entry: Path) -> list[str]:
    """The reasons this entry module would be refused by workerd."""
    if not entry.is_file():
        return [f"{entry} does not exist — the deploy would fail on a missing entry point"]
    text = entry.read_text(encoding="utf-8", errors="replace")
    names, _has_default = _named_exports(tokenize(text))
    problems: list[str] = []
    for name in sorted(set(names)):
        kind = _resolve(name, entry, set())
        if kind in (None, "function", "class"):
            continue
        problems.append(
            f"{entry.name} exports `{name}` and it is a {kind}, not a function — workerd refuses to "
            f"start the Worker: {WORKERD_MESSAGE.format(name=name)}"
        )
    return problems


def _entries() -> list[tuple[str, Path]]:
    """``(config name, entry path)`` for every wrangler config that deploys code."""
    found: list[tuple[str, Path]] = []
    for config_path in wrangler_configs(REPO):
        config = load_config(config_path)
        main = config.get("main")
        if not isinstance(main, str) or not main.strip():
            continue  # an assets-only config has no entry module
        found.append((config_path.relative_to(REPO).as_posix(),
                      (config_path.parent / main).resolve()))
    return found


def test_every_worker_entry_module_exports_only_functions():
    """The gate itself: no entry module exports a non-function."""
    entries = _entries()
    assert entries, "no wrangler config with a `main` was found — this gate would pass vacuously"
    problems: list[str] = []
    for _name, entry in entries:
        problems.extend(entry_problems(entry))
    assert not problems, "\n".join(problems)


# ── fixtures: proof that the rule can go red ─────────────────────────────────────────────────────


def test_a_constant_exported_from_the_entry_is_flagged(tmp_path):
    """The exact shape this repository had: a constant in the entry's export list."""
    entry = tmp_path / "w.js"
    entry.write_text(
        "const ACTIVITY_CACHE_CONTROL = 'public, max-age=300';\n"
        "export default { async fetch() { return new Response('ok'); } };\n"
        "export { ACTIVITY_CACHE_CONTROL };\n",
        encoding="utf-8",
    )
    problems = entry_problems(entry)
    assert len(problems) == 1, problems
    assert "ACTIVITY_CACHE_CONTROL" in problems[0], problems
    assert "function or ExportedHandler" in problems[0], problems


def test_the_implementation_module_would_be_refused_as_an_entry():
    """The shape this repository actually had, read from the repository itself.

    The implementation module exports 130 names for the tests, forty-four of them constants. It is
    a legal module and an illegal entry — which is the whole reason the entry is a separate file.
    """
    implementation = (REPO / "workers" / "register-proxy-sw.js").resolve()
    problems = entry_problems(implementation)
    assert problems, "the implementation module must be refused as an entry — it is the shape this gate exists for"
    assert len(problems) >= 40, f"expected the whole constant list, got {len(problems)}"
    assert any("ACTIVITY_CACHE_CONTROL" in p for p in problems), problems


def test_a_constant_re_exported_from_another_module_is_flagged(tmp_path):
    """The shape the fix could have drifted into: the constants move out, and get re-exported."""
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "consts.js").write_text(
        "export const SUBMITTED_TEXT_CAP = 60000;\n", encoding="utf-8")
    entry = tmp_path / "w.js"
    entry.write_text(
        "import { SUBMITTED_TEXT_CAP } from './lib/consts.js';\n"
        "export default { async fetch() { return new Response(String(SUBMITTED_TEXT_CAP)); } };\n"
        "export { SUBMITTED_TEXT_CAP };\n",
        encoding="utf-8",
    )
    problems = entry_problems(entry)
    assert len(problems) == 1, problems
    assert "SUBMITTED_TEXT_CAP" in problems[0], problems


def test_functions_and_the_default_export_are_not_flagged(tmp_path):
    """The other half: the gate must stay quiet on the shapes that are fine."""
    entry = tmp_path / "w.js"
    entry.write_text(
        "export function helper() { return 1; }\n"
        "export async function other() { return 2; }\n"
        "export class Thing {}\n"
        "export default { async fetch() { return new Response('ok'); } };\n",
        encoding="utf-8",
    )
    assert entry_problems(entry) == []


def test_a_class_bound_to_a_constant_is_not_flagged(tmp_path):
    """A Durable Object class is an `ExportedHandler`, so `const X = class …` is legal."""
    entry = tmp_path / "w.js"
    entry.write_text(
        "export const Thing = class { constructor(state) { this.state = state; } };\n"
        "export default { async fetch() { return new Response('ok'); } };\n",
        encoding="utf-8",
    )
    assert entry_problems(entry) == []


def test_a_regular_expression_literal_does_not_swallow_the_file(tmp_path):
    """The bug that made an earlier version of this gate pass silently.

    A `/*` inside a regular-expression literal looks like the start of a comment to a scanner that
    is not a tokenizer, and the "comment" then runs to the next `*/` — thousands of lines later.
    The export list was inside it, so the gate found zero exports in a file with 130 of them and
    reported nothing.
    """
    entry = tmp_path / "w.js"
    entry.write_text(
        "function esc(v) { return String(v).replace(/[&<>\"']/g, c => c); }\n"
        "const NOT_A_COMMENT = '/*';\n"
        "export const LEAKED = 'export const SHOULD_NOT_BE_SEEN = 1;';\n"
        "export default { async fetch() { return new Response(esc('x')); } };\n",
        encoding="utf-8",
    )
    problems = entry_problems(entry)
    assert len(problems) == 1, problems
    assert "LEAKED" in problems[0], problems
    assert "SHOULD_NOT_BE_SEEN" not in problems[0], problems


def test_a_missing_entry_file_is_reported(tmp_path):
    """A `main` that points at nothing is a deploy that fails on the last step."""
    problems = entry_problems(tmp_path / "nope.js")
    assert len(problems) == 1, problems
    assert "does not exist" in problems[0], problems


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
