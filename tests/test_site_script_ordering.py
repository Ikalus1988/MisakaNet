#!/usr/bin/env python3
"""A top-level call that reaches a `const` declared below it is a temporal dead zone — and it is silent.

The site hit this class twice on 2026-09-30. The homepage's stats card rendered "—" for **every** counter
because `loadLessons();` ran ~450 lines above `const LESSONS_LITE_URL`, so the page threw
`ReferenceError: Cannot access 'LESSONS_LITE_URL' before initialization`, the corpus never loaded, and the
"Frontend Shield" banner told the visitor the feed "contains anomalies or failed to load". The search page
reported the same message from its own cached copy of the same change.

The first rule written for this was too narrow: it compared one entry-point string (`loadLessons();`,
`init();`) against the declaration in **two** files, and looked at nothing under `docs/js/`. It also could not
have caught the real shape, because the top-level call did not mention the constant at all — it called a
function that called a function that read it.

This rule models that: for every script the site ships, it builds a tiny call graph, finds the functions that
(transitively) read a corpus-URL constant, and fails if any **top-level** call to one of them precedes the
declaration. Top-level means an unindented line, which is the style every one of these scripts uses.

Stated limits, so nobody trusts it further than it goes: it does not follow calls through objects or
callbacks (`addEventListener('DOMContentLoaded', init)` is invisible to it), it reads only `const`/`let`
declarations at column 0, and it cannot see a hazard inside an indented block that a top-level statement
enters. It is a lint for one repeated mistake, not a JS semantics checker.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

CORPUS_CONSTS = ("LESSONS_LITE_URL", "LESSONS_FULL_URL")
DECL = re.compile(r"^(?:const|let)\s+([A-Za-z_$][\w$]*)")
FUNC = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
TOP_CALL = re.compile(r"^(?:await\s+)?([A-Za-z_$][\w$]*)\s*\(")
CALL_NAME = re.compile(r"\b([A-Za-z_$][\w$]*)\s*\(")
# Two things code scanning read correctly, kept written down so the next edit does not undo them
# (`py/bad-tag-filter`):
#
#  * `re.I`: HTML tags are case-insensitive, so `<SCRIPT>` is the same block as `<script>` (alert #293);
#  * the **closing** tag is `</script[^>]*>`, not `</script>`. The strict form misses `</script >` and
#    `</script\t\n bar>` — both of which a browser closes the block on — so the extractor would keep
#    consuming the rest of the page as "script body" (alert #314: "does not match script end tags like
#    `</script >`"). That is not a linter reading; it is the difference between one scanned block and a
#    body that swallows the file, and `test_the_extractor_closes_on_a_tag_with_whitespace_or_attributes`
#    pins it.
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script[^>]*>", re.S | re.I)


def inline_scripts(text: str) -> list[str]:
    """The non-empty inline `<script>` bodies in one HTML document, in document order."""
    return [match.group(1) for match in INLINE_SCRIPT.finditer(text) if match.group(1).strip()]


def site_scripts() -> dict[str, str]:
    """Every script the site ships: inline blocks in `docs/**/*.html`, plus `docs/js/*.js`."""
    found: dict[str, str] = {}
    for path in sorted(DOCS.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for index, body in enumerate(inline_scripts(text)):
            found[f"{path.relative_to(DOCS).as_posix()}#script{index}"] = body
    for path in sorted((DOCS / "js").glob("*.js")):
        found[path.relative_to(DOCS).as_posix()] = path.read_text(encoding="utf-8")
    return found


def _function_bodies(source: str) -> dict[str, str]:
    """Top-level function name -> body, by brace matching from the declaration."""
    bodies: dict[str, str] = {}
    for match in re.finditer(r"(?m)^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{", source):
        name = match.group(1)
        depth = 0
        for index in range(match.end() - 1, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies[name] = source[match.end():index]
                    break
    return bodies


def tdz_hazards(source: str) -> list[str]:
    """Top-level uses or top-level calls that reach a corpus constant before it is declared."""
    lines = source.splitlines()
    declarations = {}
    for index, line in enumerate(lines):
        if line[:1].isspace():
            continue
        match = DECL.match(line)
        if match and match.group(1) in CORPUS_CONSTS:
            declarations.setdefault(match.group(1), index)
    if not declarations:
        return []

    bodies = _function_bodies(source)
    # which functions read a corpus constant, and which functions reach one of those (transitively)
    readers = {name for name, body in bodies.items() if any(c in body for c in CORPUS_CONSTS)}
    changed = True
    while changed:
        changed = False
        for name, body in bodies.items():
            if name in readers:
                continue
            if any(called in readers for called in CALL_NAME.findall(body)):
                readers.add(name)
                changed = True

    def inert(line: str) -> bool:
        """Lines that cannot read anything *at this point in the file's execution*.

        Comments (the fix for this very bug quotes the ReferenceError in one), and function/class
        declarations — their bodies run when called, not where they are written. A `const X = …` line is
        deliberately **not** inert: a top-level initializer reading a constant declared below it is a hazard.
        """
        stripped = line.lstrip()
        return (stripped.startswith(("//", "*", "/*", "<!--"))
                or bool(FUNC.match(line)) or stripped.startswith("class "))

    hazards: list[str] = []
    for name, decl_line in declarations.items():
        for index, line in enumerate(lines[:decl_line]):
            if line[:1].isspace() or inert(line):
                continue
            if name in line and not DECL.match(line):
                hazards.append(f"line {index + 1} uses `{name}` before its declaration on line "
                               f"{decl_line + 1}: {line.strip()[:80]}")
        for index, line in enumerate(lines[:decl_line]):
            if line[:1].isspace() or DECL.match(line) or inert(line):
                continue
            call = TOP_CALL.match(line)
            if call and call.group(1) in readers:
                hazards.append(f"line {index + 1} calls `{call.group(1)}()`, which reaches `{name}` "
                               f"declared on line {decl_line + 1}: {line.strip()[:80]}")
    return hazards


def test_no_script_uses_a_corpus_constant_before_declaring_it():
    scripts = site_scripts()
    assert len(scripts) >= 13, f"expected the site's scripts, found {len(scripts)}: {sorted(scripts)[:5]}"
    for known in ("index.html#script0", "search/index.html#script0", "js/core.js"):
        assert known in scripts, f"{known} is no longer scanned — the rule would silently miss it"
    problems = {name: tdz_hazards(body) for name, body in scripts.items()}
    problems = {name: found for name, found in problems.items() if found}
    assert not problems, "\n".join(
        ["a top-level statement reaches a corpus-URL constant before its declaration — at run time that is "
         "`ReferenceError: Cannot access 'X' before initialization`, which aborts the page's data load and "
         "shows the Frontend Shield banner (2026-09-30):"]
        + [f"  {name}: {hazard}" for name, found in problems.items() for hazard in found])


def test_the_rule_catches_the_exact_shape_that_broke_the_homepage():
    """Guard: the real failure was indirect — a top-level call of a function that reached the constant."""
    broken = """
let _allLessons = null;
loadLessons();

async function loadLessons() { _allLessons = await safeFetchLessons(); }
async function safeFetchLessons() { return fetchLessonsWithFallback(); }
async function fetchLessonsWithFallback() { return fetchLessonsOnce(LESSONS_LITE_URL); }
async function fetchLessonsOnce(url) { return url; }
const LESSONS_LITE_URL = "data/lessons-lite.json";
const LESSONS_FULL_URL = "data/lessons.json";
"""
    found = tdz_hazards(broken)
    assert any("loadLessons()" in hazard and "reaches" in hazard for hazard in found), found

    fixed = broken.replace("loadLessons();\n\n", "").replace(
        'const LESSONS_FULL_URL = "data/lessons.json";',
        'const LESSONS_FULL_URL = "data/lessons.json";\nloadLessons();')
    assert tdz_hazards(fixed) == [], tdz_hazards(fixed)


def test_the_rule_sees_a_direct_use_and_ignores_an_unrelated_name():
    assert tdz_hazards('console.log(LESSONS_LITE_URL);\nconst LESSONS_LITE_URL = "x";')
    assert tdz_hazards('const OTHER = 1;\nconsole.log(OTHER);') == []
    # a constant declared first and used afterwards is the normal, correct order
    assert tdz_hazards('const LESSONS_LITE_URL = "x";\nfunction load() { return LESSONS_LITE_URL; }\nload();') == []


def test_the_extractor_closes_on_a_tag_with_whitespace_or_attributes():
    """Guard: a permissive closing tag is what keeps one script from swallowing the rest of the page.

    Code scanning read the strict `</script>` as `py/bad-tag-filter` (alert #314, "does not match script
    end tags like `</script >`"). It is a real weakness here rather than a lint: an unmatched closing tag
    makes the body run on to the *next* `</script>`, so the TDZ rule would analyse a concatenation of two
    scripts and could miss the hazard it exists to find. Each spelling below closes the block in a browser.

    This is its own red case: under the old strict pattern the first assertion returns `[]` for every
    spelling except the first (no close is found at all), and the "two scripts" one below returns a single
    body that spans both. The strict pattern is deliberately **not** written out here — a regular
    expression in this file that matches `<script>…</script>` is itself a `py/bad-tag-filter` finding, which
    is how the fix for #314 first arrived as a fresh #314 on this very test.
    """
    for closing in ("</script>", "</script >", "</SCRIPT >", '</script foo="bar">', "</script\t\n bar>"):
        html = f"<script>const a = 1;{closing}<p>after</p>"
        assert inline_scripts(html) == ["const a = 1;"], (closing, inline_scripts(html))

    # The shape the alert named: `</script >` closes the first block, so the second stays a second block.
    two = "<script>a();</script ><script>b();</script>"
    assert inline_scripts(two) == ["a();", "b();"]

    # …and an external script is still not an inline body
    assert inline_scripts('<script src="js/core.js"></script>') == []
