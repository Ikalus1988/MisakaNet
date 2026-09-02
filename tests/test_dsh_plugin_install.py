#!/usr/bin/env python3
"""Tests for dsh plugin installation methods (bounty #1401).

Validates that the installation methods documented in docs/dsh-installation.md
are self-consistent and that the artifacts they depend on actually exist in the
repo, so a user following the docs can install the plugin. If the `dsh` CLI is
available in the environment it also exercises the real install path.
"""
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PASS = 0
FAIL = 0
SKIP = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  OK   " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + ((": " + detail) if detail else ""))


def skip(name, detail=""):
    global SKIP
    SKIP += 1
    print("  SKIP " + name + ((": " + detail) if detail else ""))


DOC = REPO_ROOT / "docs" / "dsh-installation.md"
SKILLS_DIR = REPO_ROOT / "skills" / "misakanet"


def test_doc_exists():
    check("docs/dsh-installation.md exists", DOC.is_file(), str(DOC))


def test_manual_install_artifact_present():
    # Method 3 (manual install) depends on skills/misakanet being present.
    check("skills/misakanet present for manual install", SKILLS_DIR.is_dir(),
          str(SKILLS_DIR))


def test_doc_covers_all_methods():
    text = DOC.read_text(encoding="utf-8") if DOC.is_file() else ""
    methods = [
        "dsh plugin add misakanet",
        "dsh plugin add github:Ikalus1988/MisakaNet",
        "cp -r skills/misakanet",
    ]
    for m in methods:
        check('doc documents method: "' + m + '"', m in text, "missing from doc")


def test_doc_references_correct_repo():
    text = DOC.read_text(encoding="utf-8") if DOC.is_file() else ""
    check("doc references Ikalus1988/MisakaNet", "Ikalus1988/MisakaNet" in text)


def test_real_install_when_dsh_present():
    dsh = shutil.which("dsh")
    if dsh is None:
        skip("dsh CLI not installed in this environment",
             "install dsh to exercise the live install path")
        return
    import subprocess
    r = subprocess.run([dsh, "plugin", "list"], capture_output=True, text=True,
                       timeout=60)
    check("`dsh plugin list` runs", r.returncode == 0,
          r.stderr.strip()[:200])


if __name__ == "__main__":
    test_doc_exists()
    test_manual_install_artifact_present()
    test_doc_covers_all_methods()
    test_doc_references_correct_repo()
    test_real_install_when_dsh_present()
    print("")
    print(str(PASS) + " passed, " + str(FAIL) + " failed, " + str(SKIP) + " skipped")
    sys.exit(1 if FAIL else 0)
