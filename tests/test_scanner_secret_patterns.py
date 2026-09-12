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
  * its patterns are broad on purpose — `token: "<anything 8+ chars>"` matches a
    placeholder as readily as a credential.

Scope: the paths the scanner has actually reported on here (workflows, the
workers/ bundle, the plugin manifest). The rest of the repository contains dozens
of deliberate placeholders — redaction fixtures, lesson examples, benchmark
transcripts — where such strings are the point, so the guard starts where the
plugin listing is judged rather than pretending the whole tree is clean.

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
]

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf"}


def _files() -> list[Path]:
    found: list[Path] = []
    for pattern in SCAN_GLOBS:
        found.extend(sorted(REPO.glob(pattern)))
    return [p for p in found if p.is_file() and p.suffix.lower() not in BINARY_SUFFIXES]


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


@pytest.mark.parametrize("sample", [
    'SOME_TOKEN="abcdefghijkl"',
    "api_key: 'sk-ant-abcdefgh'",
    'password = "hunter2hunter2"',
    'MY_SECRET="<placeholder-value>"',
])
def test_the_patterns_still_detect_what_they_are_for(sample):
    """Guard the guard: a copy of someone else's patterns must keep working.

    If this fails, the copy drifted (or the scanner changed and this file is stale)
    — either way the green result above would be meaningless.
    """
    assert any(p.search(sample) for p in COMPILED), f"no pattern matched {sample!r}"
