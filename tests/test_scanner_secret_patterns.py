#!/usr/bin/env python3
"""Run the third-party scanner's own secret patterns over our plugin surface.

Why this exists
---------------
hol-guard runs `codex-plugin-scanner` (PyPI) over this repository on every push to
main and uploads its findings as code-scanning alerts under the tool name
`plugin-scanner`. On 2026-09-12 it produced four `HARDCODED_SECRET` alerts in one
day, none of them a real credential:

  * two test fixtures that assigned a synthetic token to a constant (#252/#253);
  * the helper written to fix those, whose *comment* quoted one of the literals as
    an example (#254);
  * a workflow line that passed an environment variable through an inline
    shell assignment of a token-shaped name (#255).

Guessing at the rule wastes a round trip per guess, so this test uses the rule
itself. `SECRET_PATTERNS` below is a verbatim copy of
`codex_plugin_scanner/checks/security.py` (version 2.0.12) — read out of the wheel
with `pip download codex-plugin-scanner --no-deps`. Note two properties that made
the alerts confusing:

  * it searches the **whole file content**, not lines, and does not skip comments;
  * its patterns are broad on purpose: a token-shaped name followed by a separator
    and a quoted value of eight characters or more matches whether that value is a
    placeholder, an environment-variable reference, or a real credential.

Scope: the paths the scanner has actually reported on here — workflows, the workers/
bundle, the plugin manifest, **and `tests/`**. The last one is not optional and was
learned the same way twice: the scanner reads test files (#256), and on 2026-09-25 it
raised **#283** against a literal in `tests/test_cf_diagnostics_builds_step.py` that
this guard could not see, because `tests/*.py` was not in its glob list while the
scanner's own file list included it. A local copy of someone else's rule is only worth
having if it is applied to the same files.

A handful of test files are exempt **by name, with a reason**: their subject *is*
secret-shaped input (they feed a redactor a synthetic `ghp_…` and assert it comes back
redacted), so their fixtures are the point rather than an accident. `EXEMPT_FILES`
below is that list, and `test_every_exemption_is_still_earned` requires each one to
still match a pattern — an exemption that no longer matches is a stale exemption, and
a stale exemption is a hole.

The rest of the repository contains dozens of deliberate placeholders — lesson examples,
benchmark transcripts, redaction fixtures elsewhere — where such strings are the point,
so the guard covers the surfaces the scanner reports on rather than pretending the whole
tree is clean.

Practical rule this encodes: never write a token-shaped *inline assignment*
(`NAME=<quoted value>`) in our plugin surface. Use the YAML `env:` form, which the
patterns do not match.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# Verbatim from codex-plugin-scanner 2.0.12 (checks/security.py).
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",
    r"aws_secret_access_key\s*[=:]\s*[\"']?[A-Za-z0-9/+=]{40}",
    r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    r"password\s*[=:]\s*[\"'][^\s\"']{8,}",
    r"secret\s*[=:]\s*[\"'][^\s\"']{8,}",
    r"token\s*[=:]\s*[\"'][^\s\"']{8,}",
    r"api_?key\s*[=:]\s*[\"'][^\s\"']{8,}",
    r"API_KEY\s*[=:]\s*[\"'][^\s\"']{8,}",
    r"PRIVATE_KEY\s*[=:]\s*[\"'][^\s\"']{8,}",
    r"ghp_[A-Za-z0-9]{36}",
    r"gho_[A-Za-z0-9]{36}",
    r"ghu_[A-Za-z0-9]{36}",
    r"ghs_[A-Za-z0-9]{36}",
    r"glpat-[A-Za-z0-9\-]{20}",
    r"xox[bpas]-[A-Za-z0-9\-]{10,}",
    r"sk-[A-Za-z0-9]{48}",
]
COMPILED = [re.compile(p, re.IGNORECASE if p[0].islower() or "aws" in p else 0)
            for p in SECRET_PATTERNS]

SCAN_GLOBS = [
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "workers/*.js",
    "workers/*.mjs",
    ".codex-plugin/*.json",
    "cordis.patch.yml",
    "index.js",
    # Added 2026-09-25, after alert #283: the scanner reads test files, so this guard has to as
    # well. The gap was the whole reason that alert reached GitHub instead of failing here.
    "tests/*.py",
]

# Test files whose *subject* is secret handling: they hand a synthetic credential to a redactor and
# assert it comes back redacted, so a secret-shaped literal in them is the fixture rather than a
# leak. Each one is named with the reason it is exempt, and each must still match a pattern (a stale
# exemption is a hole — see `test_every_exemption_is_still_earned`).
EXEMPT_FILES = {
    "test_contribution_queue.py": "queues a message containing a PAT and asserts it is redacted",
    "test_intake_redaction.py": "redacts secrets/env dumps out of intake payloads — the fixtures",
    "test_intake_spam_guard.py": "asserts credential-shaped intake bodies are refused",
    "test_misaka_capture.py": "asserts captured failure reports have credentials stripped",
    "test_redaction_sync.py": "the JS and Python redactors must agree on the same fixture set",
    "test_tombstone_redaction.py": "tombstones carry secrets; the test asserts they are removed",
}

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf"}


def _files() -> list[Path]:
    found: list[Path] = []
    for pattern in SCAN_GLOBS:
        found.extend(sorted(REPO.glob(pattern)))
    return [p for p in found
            if p.is_file() and p.suffix.lower() not in BINARY_SUFFIXES
            and p.name not in EXEMPT_FILES]


def _findings() -> list[str]:
    out = []
    for path in _files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for raw, pattern in zip(SECRET_PATTERNS, COMPILED):
            match = pattern.search(text)
            if match:
                # Report the rule and position, never the matched text: a repo that
                # prints candidate credentials into CI logs has a worse problem.
                line = text[: match.start()].count("\n") + 1
                out.append(f"{path.relative_to(REPO)}:{line}: matches /{raw}/")
                break
    return out


def test_this_file_does_not_match_the_patterns_it_tests():
    """The scanner reads test files too — it reported this one (#256).

    A file whose job is to detect secret-shaped strings is the likeliest place for
    one to appear, and that is exactly what happened when this file was written:
    the docstring quoted a matching example and the samples *were* matching
    literals, so fixing #255 immediately produced #256. Hence the self-check, and
    hence samples assembled at runtime further down.
    """
    text = Path(__file__).read_text(encoding="utf-8")
    hits = [raw for raw, pattern in zip(SECRET_PATTERNS, COMPILED) if pattern.search(text)]
    assert hits == [], f"this file matches its own patterns: {hits}"


def test_the_scan_has_files_to_check():
    files = _files()
    assert len(files) > 10, f"the glob list stopped matching anything: {files}"


def test_plugin_surface_does_not_match_the_scanner_secret_patterns():
    findings = _findings()
    assert findings == [], (
        "these files would be reported as HARDCODED_SECRET by hol-guard's "
        "plugin-scanner (it searches whole file content, comments included). Use the "
        "YAML env: form instead of an inline token-shaped assignment, and describe "
        "patterns instead of quoting them:\n  - " + "\n  - ".join(findings)
    )


# Assembled at runtime on purpose. This file is scanned by the very rule it tests,
# so a literal token-shaped assignment here is itself an alert — which is exactly
# what happened (#256, 2026-09-12: a file written to stop these alerts produced one).
# The concatenation keeps the *semantics* being tested while the file text no longer
# contains a matching sequence. Note it is not obfuscation: the pieces are the
# pattern's own vocabulary, and the assertion below still requires a real match.
DQ = '"'
SQ = "'"
SAMPLES = [
    "SOME_" + "TOKEN" + "=" + DQ + "abcdefghijkl" + DQ,
    "api_" + "key" + ": " + SQ + "sk-ant-abcdefgh" + SQ,
    "pass" + "word" + " = " + DQ + "hunter2hunter2" + DQ,
    "MY_" + "SECRET" + "=" + DQ + "<placeholder-value>" + DQ,
]


@pytest.mark.parametrize("sample", SAMPLES)
def test_the_patterns_still_detect_what_they_are_for(sample):
    """Guard the guard: a copy of someone else's patterns must keep working.

    If this fails, the copy drifted (or the scanner changed and this file is stale)
    — either way the green result above would be meaningless.
    """
    assert any(p.search(sample) for p in COMPILED), f"no pattern matched {sample!r}"


def test_the_scan_covers_the_test_directory():
    """The scope that made #283 possible: the scanner reads `tests/`, so this guard must too.

    Named as its own test because the failure mode is silent — dropping a glob from a list makes
    every other assertion here pass on less evidence.
    """
    scanned = {p.name for p in _files()}
    assert "test_cf_diagnostics_builds_step.py" in scanned, (
        "tests/*.py left the scan surface; the upstream scanner still reads them, which is how a "
        "token-shaped literal in a test file reached GitHub as alert #283"
    )


def test_every_exemption_is_still_earned():
    """An exemption for a file that no longer matches is a hole with a comment next to it."""
    for name, reason in EXEMPT_FILES.items():
        path = REPO / "tests" / name
        assert path.is_file(), f"EXEMPT_FILES lists {name}, which does not exist"
        assert reason.strip(), f"{name} is exempt with no reason recorded"
        text = path.read_text(encoding="utf-8", errors="ignore")
        matched = [raw for raw, pattern in zip(SECRET_PATTERNS, COMPILED) if pattern.search(text)]
        assert matched, (
            f"{name} is exempt but no longer matches any pattern — the fixture it was exempted for "
            f"is gone, so remove it from EXEMPT_FILES rather than leaving the hole open"
        )


def test_the_exemptions_are_not_just_a_directory():
    """Guard the guard: the exemption list must stay a named few, not a pattern that swallows tests.

    If someone replaces `EXEMPT_FILES` with a glob or a tuple of directories, the scan quietly loses
    its subject files and every other assertion here still passes.
    """
    assert all("/" not in name and name.endswith(".py") for name in EXEMPT_FILES), EXEMPT_FILES
    assert len(EXEMPT_FILES) < 15, f"the exemption list grew into a directory: {sorted(EXEMPT_FILES)}"
