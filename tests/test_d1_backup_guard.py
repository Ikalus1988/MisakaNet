#!/usr/bin/env python3
"""The D1 backup must refuse to archive a dump that is empty, truncated, or schema-only.

`d1-backup.yml` exists because a backup nobody verifies is a belief, not a safety net: the failure
that matters is not "the export command failed" (that is loud) but "a plausible-looking file was
archived every week for months and nobody opened one". So the step asserts three coarse properties —
the file has size, it carries INSERT statements, and it mentions the `lessons` table — and *fails the
job* when they do not hold.

This runs the step's own shell with a stub `wrangler` on PATH, which is what keeps the assertions
honest: the stub can be told to produce a good dump, an empty one, or a schema-only one, and the test
checks the guard's verdict on each. A guard that only runs when a human is watching is the thing this
file is here to prevent.

The stub PATH also carries a **BSD `stat`**, on every platform, because that is how this file went
red on the `macos-latest` legs for weeks: the step sized the dump with GNU's `stat -c%s`, macOS
rejects that spelling, and `set -e` then killed the step before any assertion ran — its stdout was
the `ls -l` line and nothing else, so the guard never gave a verdict at all. Five tests failed there
while every ubuntu leg stayed green. Binding the BSD dialect locally keeps that class of mistake
from reaching CI in the first place.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from posix_shell import require_posix_shell  # a real POSIX shell, or a skip

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "d1-backup.yml"


def export_script() -> str:
    """The `run:` body of the export step, exactly as CI executes it."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["export"]["steps"]:
        if (step.get("name") or "").startswith("Export the database"):
            return step["run"]
    raise AssertionError(f"no export step in {WORKFLOW.name} — fix this pin with the step")


GOOD_DUMP = (
    'CREATE TABLE "lessons" (\n  "id" text primary key,\n  "content_md" text\n);\n'
    + "".join(f'INSERT INTO "lessons" VALUES (\'lesson-{i}\', \'body {i}\');\n' for i in range(400))
    + "x" * 500_000
)
SCHEMA_ONLY_DUMP = 'CREATE TABLE "lessons" (\n  "id" text primary key\n);\n' + "x" * 600_000
EMPTY_DUMP = ""


def write_stub(bindir: Path, dump: str) -> None:
    """A `wrangler` that writes `dump` wherever `--output` points, and a no-op `npm`."""
    (bindir / "wrangler").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [ "$1" = "d1" ] && [ "$2" = "export" ]; then\n'
        '  for arg in "$@"; do case "$arg" in --output=*) out="${arg#--output=}";; --output) out="";; esac; done\n'
        '  if [ -z "${out:-}" ]; then out="${@: -1}"; fi\n'
        '  cat > "$out" <<\'DUMP\'\n'
        f"{dump}"
        "\nDUMP\n"
        "  exit 0\n"
        "fi\n"
        'echo "stub wrangler: $*"\n'
    )
    (bindir / "wrangler").chmod((bindir / "wrangler").stat().st_mode | stat.S_IEXEC)
    (bindir / "npm").write_text("#!/usr/bin/env bash\nexit 0\n")
    (bindir / "npm").chmod((bindir / "npm").stat().st_mode | stat.S_IEXEC)
    # BSD `stat`, deliberately — see the module docstring. `-c` does not exist there and the size is
    # `-f%z`, so a step that reintroduces the GNU spelling fails here instead of only on macOS.
    (bindir / "stat").write_text(
        "#!/usr/bin/env bash\n"
        'case "${1:-}" in\n'
        "  -f%z) shift ;;\n"
        '  -f) [ "${2:-}" = "%z" ] && shift 2 ;;\n'
        '  *) echo "stat: illegal option -- ${1#-}" >&2; exit 1 ;;\n'
        "esac\n"
        'wc -c < "$1" | tr -d "[:space:]"\n'
    )
    (bindir / "stat").chmod((bindir / "stat").stat().st_mode | stat.S_IEXEC)


def run_export(tmp_path: Path, dump: str) -> subprocess.CompletedProcess:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    write_stub(bindir, dump)
    output = tmp_path / "gh_output"
    output.write_text("")
    return subprocess.run(
        [require_posix_shell(), "-c", export_script()],
        cwd=REPO,
        capture_output=True, text=True,
        env={
            "PATH": f"{bindir}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "GITHUB_OUTPUT": str(output),
            "CLOUDFLARE_API_TOKEN": "stub",
        },
    )


def test_a_real_dump_is_accepted_and_its_numbers_reported(tmp_path):
    proc = run_export(tmp_path, GOOD_DUMP)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "refusing to archive" not in proc.stdout
    # The counts are what a reader of a weekly run has to be able to check at a glance — and each
    # label has to say what it counts: an earlier version printed a combined CREATE+INSERT tally as
    # "lessons CREATE TABLE", which read as a table count and was 401.
    assert re.search(r"INSERT statements=400", proc.stdout), proc.stdout
    assert re.search(r"CREATE TABLE=1", proc.stdout), proc.stdout
    assert re.search(r"naming the lessons table=401", proc.stdout), proc.stdout


def test_an_empty_dump_is_refused(tmp_path):
    """`wrangler d1 export` succeeding is not evidence that it wrote anything."""
    proc = run_export(tmp_path, EMPTY_DUMP)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "::error::the dump looks wrong" in proc.stdout, proc.stdout


def test_a_truncated_dump_is_refused(tmp_path):
    """The realistic accident: the run is killed mid-export and the file looks fine by name."""
    proc = run_export(tmp_path, "CREATE TABLE \"lessons\" (\n" + "x" * 1000)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "::error::the dump looks wrong" in proc.stdout, proc.stdout


def test_a_schema_only_dump_is_refused(tmp_path):
    """A dump with the schema and no rows restores an empty corpus — and passes a size check alone."""
    proc = run_export(tmp_path, SCHEMA_ONLY_DUMP)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "::error::the dump looks wrong" in proc.stdout, proc.stdout


def test_a_dump_without_the_lessons_table_is_refused(tmp_path):
    proc = run_export(tmp_path, "CREATE TABLE \"other\" (id text);\n"
                      + "".join(f"INSERT INTO other VALUES ('{i}');\n" for i in range(400))
                      + "x" * 500_000)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "::error::the dump looks wrong" in proc.stdout, proc.stdout


@pytest.mark.parametrize("name", ["d1 info", "d1 time-travel info"])
def test_the_backend_and_bookmark_are_printed_for_the_record(tmp_path, name):
    """Time Travel needs the `production` storage backend, so the run states which one this is."""
    script = export_script()
    assert name in script, f"{name} dropped out of the backup step; the dump is then the only restore path"
