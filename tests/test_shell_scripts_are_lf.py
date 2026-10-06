#!/usr/bin/env python3
"""A shell script that is stored with CRLF breaks on the machine that checks it out.

Found in the wild (2026-10-05)
------------------------------
On a checkout that lives on a Windows drive, git's default `core.autocrlf=true` rewrites
every LF in the working tree to CRLF, and `bash` then reads the carriage return as part of the
command name:

    scripts/misakanet_voice_hook.sh: line 14: $'\r': command not found
    integrations/agent-autostart/bootstrap.sh: line 15: set: pipefail

Measured on commit `4a8e5749`: **9 of the suite's tests failed for this reason alone**, all of
them tests that execute a `.sh`. The same commit, on an LF checkout, passed 12/12. CI never saw
it, because CI checks out on Linux.

That is the shape worth acting on. It is not a broken build — it is a **signal that silently
does not fire on the machine where the author is working**, which is the same failure this
repository already names twice: `handoff-2026-10-04.md` §1.4 ("本地全量绿不等于 F821/F811
通过", a gate that skips when its tool is missing) and `handoff-2026-10-05.md` §3.6 (a guard
whose coverage vanished on any machine that had built the SAG index). A contributor on Windows
sees nine failures, cannot tell which are theirs, and learns to ignore the suite.

Why `.sh` and nothing wider
---------------------------
CRLF is fatal to `bash` and harmless to everything else this repository executes: Python 3's
tokenizer accepts it, Node accepts it, and `git diff` normalises any file marked `text`. A
blanket `* text=auto eol=lf` would renormalise thousands of paths — including the 1.26 MB
generated `data/lessons.json` — to fix a problem only one interpreter has. The rule in
`.gitattributes` is therefore `*.sh text eol=lf`, and the rule below is that it stays.

What this checks, and why both halves
-------------------------------------
1. **The committed bytes.** Every `.sh` blob in the index must be LF-only. This is the invariant
   that actually matters, and it is checkable in CI with no checkout of its own — it reads the
   index, not the working tree, so it is true on a Windows runner *and* on Linux. A file that is
   already correct cannot satisfy it by accident.
2. **The rule.** `.gitattributes` must still declare `*.sh text eol=lf`, so that checkout does
   not re-introduce (1) on the next `git add` from a Windows drive. Without this half, someone
   could remove the attribute and every future commit would be clean *until* the next Windows
   contributor pushes one.

The narrow version of this rule was measured before it was adopted: the repository has 24
tracked `.sh` files, 0 of which currently contain a carriage return. A gate that finds nothing
today is not a gate that does not work, so both halves are mutation-checked in
`tests/test_shell_scripts_are_lf.py`'s own docstring, and the check itself is exercised against
a synthetic CRLF blob rather than a real one.

Usage:
    python3 tests/test_shell_scripts_are_lf.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GITATTRIBUTES = REPO / ".gitattributes"

# The exact rule the comment in `.gitattributes` justifies. Matched as a token so that
# `*.sh text eol=lf` and `*.sh binary` cannot both satisfy it, and so a commented-out
# mention of the rule does not either.
REQUIRED_RULE = "*.sh text eol=lf"

# A `.sh` carrying a shebang. Files without one are not executed, so a CRLF in them is inert;
# excluding them keeps the rule about *executed* scripts rather than about a filename suffix.
SHEBANG = b"#!"


def tracked_shell_scripts() -> list[str]:
    """Tracked paths ending in `.sh`, straight from the index.

    The index rather than the filesystem on purpose: this runs in CI, where a checkout is Linux
    and therefore LF, and reading the working tree there would make the check vacuous — it could
    not fail, because the checkout it just made is the thing that fixes the problem.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", "*.sh"],
        capture_output=True, check=True,
    )
    return [p.decode("utf-8") for p in out.stdout.split(b"\0") if p]


def blob(rel: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPO), "show", f":{rel}"],
        capture_output=True, check=True,
    ).stdout


def offenders() -> list[tuple[str, int]]:
    """Tracked `.sh` files whose committed bytes contain a carriage return."""
    found = []
    for rel in tracked_shell_scripts():
        data = blob(rel)
        if b"\r" in data:
            found.append((rel, data.count(b"\r")))
    return found


def rule_present() -> bool:
    if not GITATTRIBUTES.exists():
        return False
    for line in GITATTRIBUTES.read_text(encoding="utf-8").splitlines():
        if line.strip() == REQUIRED_RULE:
            return True
    return False


def test_every_committed_shell_script_is_lf_only() -> None:
    """The one that matters: the bytes in the index, not the bytes on this machine."""
    scripts = tracked_shell_scripts()
    assert scripts, (
        "no tracked .sh files were found — if this repository really has none, delete this test; "
        "if the git invocation broke, this gate now passes without checking anything"
    )
    bad = offenders()
    assert not bad, (
        f"{len(bad)} committed shell script(s) contain a carriage return:\n"
        + "\n".join(f"  {rel}  ({count} CR)" for rel, count in bad)
        + "\n\nbash reads the CR as part of the command name, so the script fails on any checkout "
        "that rewrites line endings — every Windows drive with git's default "
        "`core.autocrlf=true`. Measured 2026-10-05: 9 suite tests fail from this alone while CI "
        "stays green, because CI checks out on Linux.\n\n"
        "Fix the line endings (`dos2unix`, or an editor that saves LF), and check that "
        "`.gitattributes` still carries `*.sh text eol=lf` so the next `git add` keeps it that "
        "way. This is a test-only change: no shell script's content is being altered here."
    )


def test_the_shell_scripts_are_actually_executed() -> None:
    """Shebang presence, so the rule above is about scripts and not about a filename.

    A `.sh` with no shebang is never handed to `bash` by anything this repository does, so a
    carriage return in it is inert. If every tracked `.sh` lost its shebang, the CRLF gate would
    keep passing while covering nothing.
    """
    missing = [rel for rel in tracked_shell_scripts() if not blob(rel).lstrip().startswith(SHEBANG)]
    assert not missing, (
        f"{len(missing)} tracked .sh file(s) no longer start with a shebang:\n"
        + "\n".join(f"  {rel}" for rel in missing[:10])
        + "\n\nA script without a shebang is not executed, so the CRLF gate above would be "
        "asserting something that cannot fail. If these are meant to be sourced or passed to "
        "`bash <file>` rather than run, say so in the test; otherwise restore the shebang."
    )


def test_gitattributes_still_declares_the_shell_eol_rule() -> None:
    """Without the attribute, correct bytes stay correct only until the next Windows contributor.

    The first test reads the index, so it is unaffected by checkout settings. This is the half
    that keeps the *checkout* right: `*.sh text eol=lf` is what makes git write these files with
    LF endings on a Windows drive in the first place. Delete the attribute and the first test
    keeps passing for a while — and then someone commits a CRLF script from Windows, and it
    fails for a reason nobody can see from the rules.
    """
    assert GITATTRIBUTES.exists(), (
        ".gitattributes is gone, so nothing declares the line-ending policy for shell scripts"
    )
    assert rule_present(), (
        f"`.gitattributes` no longer contains the exact line `{REQUIRED_RULE}`.\n\n"
        "The committed-blob check above reads the index and cannot see this: it stays green while "
        "checkouts on a Windows drive keep rewriting these files to CRLF, and the next contributor "
        "who commits from there reintroduces the failure. The justification for keeping this to "
        "`*.sh` — CRLF is fatal to bash and harmless to Python and Node — is in the comment above "
        "the rule; if that reasoning has changed, update both together."
    )


def main() -> int:
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}\n  {exc}")
            else:
                print(f"ok   {name}")
    print(f"\n{len(tracked_shell_scripts())} tracked .sh file(s) checked.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
