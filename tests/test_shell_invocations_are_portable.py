#!/usr/bin/env python3
"""A test that shells out must say which shell it means, not just name `bash`.

`scripts/posix_shell.py` exists because on `windows-latest` the name `bash` on PATH is
`C:\\Windows\\System32\\bash.exe` — the WSL launcher — and that image has no distribution
installed, so every `subprocess.run(["bash", ...])` dies with

    Windows Subsystem for Linux has no installed distributions.

Its docstring records what that looks like from the outside: the assertion fails carrying a
banner in UTF-16LE (`W\\x00i\\x00n\\x00d\\x00o\\x00w\\x00s...`), because the subprocess printed
that text rather than running anything.

That module was written on 2026-09-21 and turned ~20 red legs green. It was still not enough,
because **nothing required anyone to use it**. A test added on 2026-10-07
(`test_workflow_hygiene.py`) called `subprocess.run(["bash", ...])` directly, and three
`windows-latest` legs went red on every pull request — the same failure, from the same cause,
thirteen weeks later. A helper that only some callers use is not a guard. This is the guard.

## The rule

**No test may hand `subprocess` a literal shell name.** Either the shell comes from
`posix_shell`, or the test declares itself POSIX-only — in which case it skips on Windows and
the literal never runs there. Both are honest; a bare literal is not. Note that merely importing
`posix_shell` does **not** excuse a literal: a file can resolve the shell for one call and hand
a literal to another, and a mutation is what caught that exemption being written too wide.

## A second rule that was written, measured, and dropped

This file first also forbade writing a `.sh` through `Path.write_text` without `newline="\\n"`,
on the theory that `write_text` emits CRLF on Windows and bash reads the `\\r` as part of the
token. **That theory is wrong here, and the repository's own CI says so.**

The supporting measurement was real but narrower than claimed: a CRLF script does fail on a
Linux `bash` —

    crlf_probe.sh: line 1: set: -: invalid option
    crlf_probe.sh: line 2: syntax error near unexpected token `$'do\\r''`

— but nine call sites in this suite write a shell script exactly that way, run it through
`require_posix_shell()`, and **all of them pass on `windows-latest`**, including ones that assert
the script exited 0 and that a stub binary was actually invoked. If CRLF were fatal under Git
Bash, those legs would be red. They are not.

So the rule was removed rather than kept with a softened message: it would have forced nine
edits on the strength of an extrapolation from Linux bash to Git Bash that the evidence
contradicts. `newline="\\n"` is still worth writing in a test that builds a shell script — it
makes the bytes deterministic whatever the platform — but it is hygiene here, not a gate.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

TESTS = Path(__file__).resolve().parent

#: This file, and the helper itself, are about shells and are allowed to name them.
SELF = frozenset({TESTS / "test_shell_invocations_are_portable.py", TESTS / "posix_shell.py"})

#: `subprocess.run(["bash", ...])`, `["sh", ...]`, and the single-quoted spellings.
LITERAL_SHELL_ARGV = re.compile(r"""\[\s*["'](?:ba)?sh["']""")

#: A POSIX-only test skips on Windows, so a literal shell in it is never executed there.
POSIX_ONLY_MARKERS = ("win32", 'os.name != "posix"', "os.name != 'posix'")


def _test_files():
    return sorted(p for p in TESTS.glob("test_*.py") if p not in SELF)


def _code_without_comments(path: Path) -> str:
    """The module's code, with comments and docstrings dropped.

    Two gates in this repository already strip comments before scanning themselves
    (`test_workflow_hygiene.py`, `test_workflow_script_injection.py`), and for the same reason:
    a rule that reads prose reports the prose that explains the rule back at it.
    """
    out = []
    previous_type = tokenize.INDENT
    try:
        for token in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline):
            if token.type == tokenize.COMMENT:
                continue
            if token.type == tokenize.STRING and previous_type in (
                tokenize.INDENT, tokenize.NEWLINE, tokenize.NL, tokenize.DEDENT,
            ):
                continue
            if token.type not in (tokenize.NL, tokenize.NEWLINE):
                out.append(token.string)
            previous_type = token.type
    except tokenize.TokenError:
        return path.read_text(encoding="utf-8")
    return "\n".join(out)


def _is_posix_only(text: str) -> bool:
    """Whitespace-insensitive, because the code above is reassembled one token per line.

    A joined-with-newlines rendering turns `os.name != "posix"` into five separate tokens, so a
    substring test for it would silently never match — and a guard that cannot match anything is
    the same shape this repository keeps removing.
    """
    squeezed = "".join(text.split())
    return any("".join(marker.split()) in squeezed for marker in POSIX_ONLY_MARKERS)


def test_no_test_hands_subprocess_a_literal_shell_name():
    """`["bash", ...]` on `windows-latest` is the WSL launcher, not a shell."""
    offenders = []
    for path in _test_files():
        code = _code_without_comments(path)
        if not LITERAL_SHELL_ARGV.search(code):
            continue
        # Only a POSIX-only test is exempt. **Importing `posix_shell` is not** — a file can take
        # its shell from the helper for one call and still hand a literal to another, and that is
        # precisely the regression: the first version of this rule exempted anything mentioning
        # the helper, and a mutation that put the literal back into `test_workflow_hygiene.py`
        # sailed through. An import is not a resolution.
        if _is_posix_only(code):
            continue
        offenders.append(path.name)
    assert not offenders, (
        f"these tests name a shell as a literal in a subprocess argv, so on windows-latest they "
        f"run C:\\Windows\\System32\\bash.exe and fail with 'has no installed distributions' "
        f"rather than with anything about the code under test: {offenders}. Take the shell from "
        "`posix_shell.require_posix_shell()`, or declare the test POSIX-only with a skipif that "
        "names the reason.")


def test_the_gate_can_tell_a_guarded_call_from_an_unguarded_one(tmp_path):
    """Both directions run against fixtures, so the rule is shown rather than merely asserted.

    A rule that has only ever been exercised on files that already satisfy it is the shape this
    repository keeps deleting.
    """
    unguarded = 'subprocess.run(["bash", str(script)])'
    guarded_shell = "shell = require_posix_shell()\nsubprocess.run([shell, str(script)])"
    guarded_skip = '@pytest.mark.skipif(sys.platform == "win32")\nsubprocess.run(["bash", "x.sh"])'

    assert LITERAL_SHELL_ARGV.search(unguarded), "the rule stopped seeing the shape it forbids"
    assert not LITERAL_SHELL_ARGV.search(guarded_shell), "a resolved shell must not read as a literal"
    assert LITERAL_SHELL_ARGV.search(guarded_skip), "a POSIX-only test still names the literal"
    assert _is_posix_only(guarded_skip) and not _is_posix_only(guarded_shell)

    # Prose must not be able to trip the rule. This file's own module docstring quotes the shape
    # several times, so the stripping is checked against a fixture rather than against itself —
    # a gate that only ever runs on itself is not showing that its filter works.
    quoted_in_prose = tmp_path / "test_prose_only.py"
    quoted_in_prose.write_text(
        '"""A docstring that says subprocess.run(["bash", "x.sh"]) is describing, not calling."""\n'
        "# and a comment saying subprocess.run([\"bash\", \"x.sh\"])\n"
        "print('nothing')\n",
        encoding="utf-8",
    )
    stripped = _code_without_comments(quoted_in_prose)
    assert "bash" not in stripped, f"prose survived the strip:\n{stripped}"
    assert "print" in stripped and "nothing" in stripped, f"code was stripped too:\n{stripped}"