#!/usr/bin/env python3
"""Two bug classes that shipped twice today, and that no gate in this repository could see.

Why this file exists (2026-09-28)
---------------------------------
PR #2387 fixed three defects that had been sitting on `main`:

* `misakanet/search/embeddings.py` — the dev-fallback path calls `hashlib.sha256` and the module never
  imports `hashlib`, so any dev-mode embedding call raises `NameError`;
* `scripts/sync_lessons_to_d1.py` — the token-authenticated D1 path does `import urllib.error as _ue`
  and then calls `urllib.request.Request`, and `urllib` itself is never bound, so the whole Bearer-token
  path raises `NameError`;
* `misakanet/profile.py` — a function-local `import tempfile` shadows the module-level one (F811).

**Nothing in CI could have caught any of them.** The suite runs the code that *is* exercised, and both
broken paths are the ones tests do not drive (a fallback, a token branch). `mypy` runs in one job with
`continue-on-error: true` and only over `misakanet/` — which is why the `scripts/` member of the pair was
invisible twice over. `pyproject.toml` has configured `ruff` (`select = ["E", "F", "I", "N", "W", "UP"]`)
since before today, but no workflow ever ran it.

So this is the narrow gate, not the style sweep: `F821` (undefined name) and `F811` (redefinition of an
unused name) are the two rules whose violation is a *crash or a silent shadow*, and the repository is
already clean for both — 436 maintained files, zero findings. The broader configured rule set is left to
contributors running `ruff check .` locally, because turning on `E`/`I`/`N`/`UP` repo-wide would be
thousands of findings and a gate nobody could keep green.

`archive/` is excluded in `pyproject.toml`, not here: it is the dead-code graveyard, one of its files does
not even parse, and excluding it in the config means a contributor's `ruff check .` inspects exactly the
files this gate does.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SELECT = "F821,F811"
# The maintained tree, measured 2026-09-28: 459 tracked Python files, 436 of them outside `archive/`.
MIN_FILES = 400


def ruff(*args: str, cwd: Path = REPO) -> subprocess.CompletedProcess[str]:
    """Run `python -m ruff …` — the module entry point, so `sys.executable` decides which ruff."""
    return subprocess.run([sys.executable, "-m", "ruff", *args], cwd=str(cwd),
                          capture_output=True, text=True)


@pytest.fixture(scope="module")
def ruff_available() -> None:
    probe = ruff("--version")
    if probe.returncode != 0:
        pytest.skip(
            "ruff is not installed in this interpreter, so the gate cannot run. CI installs it (see the "
            "test job in `.github/workflows/pr-checks.yml` and `ci-cross-platform.yml`); locally, "
            "`pip install ruff` or `python3 -m pip install --user ruff` enables it."
        )


def test_the_gate_is_scanning_the_maintained_tree(ruff_available: None) -> None:
    """A rule that runs over nothing passes for the wrong reason.

    Also asserts the exclusion is the *configured* one: `archive/` must not appear, and the files it
    excludes must be a minority (if the count collapsed, the gate would be checking almost nothing).
    """
    listed = ruff("check", "--show-files", "--select", SELECT, ".")
    assert listed.returncode == 0, listed.stderr
    files = [line for line in listed.stdout.split() if line.endswith(".py")]
    assert len(files) >= MIN_FILES, (
        f"the gate would inspect only {len(files)} files (expected ≥ {MIN_FILES}) — the path or the "
        "working directory moved, so this test would pass while checking almost nothing"
    )
    archived = [f for f in files if f.startswith("archive/")]
    assert archived == [], f"`archive/` is excluded in pyproject.toml but still scanned: {archived[:3]}"


def test_the_rule_set_is_live(ruff_available: None, tmp_path: Path) -> None:
    """The control: both bug classes must be reported when they are present.

    Without this, a `--select` typo (or a config that disabled the rules) would leave the gate green over
    a broken file — the failure mode this file is about, one level up.
    """
    sample = tmp_path / "shipped_twice.py"
    sample.write_text(
        '"""Two shapes that reached main today."""\n'
        "import os\n"
        "import os  # F811: redefinition of the unused name above\n"
        "\n"
        "\n"
        "def dev_fallback(text):\n"
        "    return hashlib.sha256(text.encode()).digest()   # F821: hashlib is never imported\n",
        encoding="utf-8",
    )
    result = ruff("check", "--select", SELECT, "--no-cache", "--output-format", "concise", str(sample))
    assert result.returncode != 0, f"neither bug class was reported:\n{result.stdout}"
    assert "F821" in result.stdout, f"undefined name not reported:\n{result.stdout}"
    assert "F811" in result.stdout, f"redefinition not reported:\n{result.stdout}"


def test_no_undefined_names_or_shadowed_imports(ruff_available: None) -> None:
    """The gate. Same command as the control, over the repository."""
    result = ruff("check", "--select", SELECT, "--no-cache", "--output-format", "concise", ".")
    assert result.returncode == 0, (
        "ruff found crash-shaped name errors (F821 undefined name / F811 redefinition):\n"
        f"{result.stdout}{result.stderr}\n"
        "Both classes shipped on 2026-09-28 in code no test drives (a dev fallback and a token-auth "
        "branch) — see the module docstring. Fix the finding; if a rule is a false positive for a real "
        "pattern, add a `# noqa: <code>` with the reason next to it rather than widening this gate."
    )
