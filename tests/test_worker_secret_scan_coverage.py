#!/usr/bin/env python3
"""The credential gate has to *reach* the source, not merely run.

Two defects, the same shape, found by #2684:

* It globbed `workers/**/*.js` while `workers/` holds 69 `.mjs` files against 5 `.js` ones, so a
  blocking required check was reading six percent of the worker tree and reporting a clean bill of
  health. It was already merged as #2731; these tests are what keep that fixed.
* The scope was `workers/` alone, so a credential in a workflow or a maintenance script was never
  read at all. Measured before widening (`.github/` 94 files, `scripts/` 161 files, **0 findings**),
  and `packages/`/`tests/` measured at 15 — all deliberate redaction fixtures, which need an
  allowlist that does not exist yet, so they are still out.

The existing tests in `test_published_secrets_scan.py` cover the *prose* gate's patterns and the CI
wiring. Neither belongs here: this is about which files get collected. The real tree cannot answer
that on its own — it is clean under every scope — so collection is asserted against temporary trees.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import check_worker_secrets as scan_module  # noqa: E402
from scripts.check_worker_secrets import (  # noqa: E402
    SCAN_TARGETS,
    UnreadableScanTarget,
    scan_credential_patterns,
    secret_scan_files,
)

# A GitHub PAT shape, spelled out rather than copied from a real leak. `check_worker_secrets.py`
# reports file/line/kind and never the matched text, so a literal here would be inert either way —
# but keeping it obviously synthetic means it can never be mistaken for a credential to rotate.
FAKE_PAT = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _probe(directory: Path, name: str) -> Path:
    path = directory / name
    path.write_text(f'const key = "{FAKE_PAT}";\n', encoding="utf-8")
    return path


def _in_repo_tree():
    """A scratch directory inside the repository.

    `scan_credential_patterns` labels its findings with `filepath.relative_to(REPO)` and raises
    outside it, so a probe under `tmp_path` cannot be scanned. The context manager removes it even
    if an assertion fails.
    """
    return tempfile.TemporaryDirectory(dir=REPO, prefix=".secret-scan-probe-")


# ── the original regression: `.mjs` was invisible ────────────────────────────────────────────────

def test_the_scan_reaches_dot_mjs():
    with _in_repo_tree() as scratch:
        workers = Path(scratch) / "workers"
        workers.mkdir()
        probe = _probe(workers, "handler.mjs")

        found = {p.name for p in secret_scan_files(Path(scratch))}
        assert "handler.mjs" in found, f"`.mjs` is not collected at all: {found}"

        hits = [
            hit
            for path in secret_scan_files(Path(scratch))
            for hit in scan_credential_patterns(path)
        ]
        assert hits, f"a credential in {probe.name} was collected but not flagged"
        assert any(probe.name in str(hit.get("file", "")) for hit in hits), hits


def test_dot_js_is_still_reached(tmp_path):
    """Both extensions, so a future edit cannot trade one for the other."""
    (tmp_path / "workers").mkdir()
    _probe(tmp_path / "workers", "legacy.js")

    found = {p.name for p in secret_scan_files(tmp_path)}
    assert found == {"legacy.js"}, found


# ── the widened scope ───────────────────────────────────────────────────────────────────────────

def test_a_credential_in_a_workflow_is_found():
    """The workflow that runs the gate, scanned by the gate."""
    with _in_repo_tree() as scratch:
        workflows = Path(scratch) / ".github" / "workflows"
        workflows.mkdir(parents=True)
        probe = _probe(workflows, "release.yml")

        hits = [
            hit
            for path in secret_scan_files(Path(scratch))
            for hit in scan_credential_patterns(path)
        ]
        assert hits, "a credential in a workflow file was not detected"
        assert any(probe.name in str(hit.get("file", "")) for hit in hits), hits


def test_a_credential_in_a_maintenance_script_is_found():
    with _in_repo_tree() as scratch:
        scripts = Path(scratch) / "scripts"
        scripts.mkdir(parents=True)
        probe = _probe(scripts, "publish.py")

        hits = [
            hit
            for path in secret_scan_files(Path(scratch))
            for hit in scan_credential_patterns(path)
        ]
        assert hits, "a credential in a maintenance script was not detected"
        assert any(probe.name in str(hit.get("file", "")) for hit in hits), hits


def test_the_secrets_expression_is_not_a_credential():
    """Why `.github/` is in scope at all.

    The objection that kept this directory out was that workflows legitimately contain
    `${{ secrets.X }}` and a naive scanner would go red on every PR. This pins the reason that
    worry was wrong, so a future pattern change cannot reintroduce it unnoticed.
    """
    with _in_repo_tree() as scratch:
        workflows = Path(scratch) / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ok.yml").write_text(
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - run: gh auth login\n"
            "        env:\n"
            "          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}\n"
            "          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}\n",
            encoding="utf-8",
        )
        (workflows / "env-block.yml").write_text(
            "        env:\n          TOKEN: ${{ secrets.DEPLOY_TOKEN }}\n",
            encoding="utf-8",
        )

        hits = [
            hit
            for path in secret_scan_files(Path(scratch))
            for hit in scan_credential_patterns(path)
        ]
        assert hits == [], f"a secrets expression was read as a credential: {hits}"


def test_packages_and_tests_are_still_out_of_scope():
    """They hold 15 findings, all deliberate redaction fixtures. They come back with the allowlist
    that says so, and until then a test pins that they are still out — otherwise a well-meaning
    'just add one more directory' turns the gate red on `main`."""
    for excluded in ("packages", "tests"):
        assert excluded not in {rel for rel, _ in SCAN_TARGETS}, SCAN_TARGETS


# ── the scan must not be able to read nothing and still pass ────────────────────────────────────

def test_the_scan_reads_a_plausible_number_of_files():
    """The failure mode of both defects was a scan that read almost nothing and reported success.

    A table typo, a renamed directory or a checkout that omits a scope would all produce zero files
    and a green gate. This is the backstop for that. The tree yields 332 today — workers 79,
    `.github` 95, `scripts` 158 — so 280 sits below any single-scope loss: dropping `.github` gives
    237, dropping `scripts` gives 174, dropping `.mjs` gives 262. It does **not** catch losing the
    five `.js` files, and it is not meant to: `test_dot_js_is_still_reached` covers that case
    precisely. A floor that tried to catch everything would only be a number that breaks whenever
    the tree grows.
    """
    files = secret_scan_files()
    assert len(files) > 280, (
        f"the scan is reading only {len(files)} files, against 332 when measured: "
        f"{[str(f) for f in files[:10]]}"
    )


def test_compiled_bytecode_is_not_collected():
    """`scripts/` holds 144 `.pyc` files once anything has been run; bytecode embeds string
    constants, so reading it is slow and noisy without adding coverage.

    Asserted against a tree that *has* one. This was originally written against the real tree, where
    the check passed for the wrong reason: a clean checkout has no `.pyc` at all, because they are
    gitignored, so it asserted nothing. That is the same defect as the gate itself — a test that
    reports coverage it was not measuring.
    """
    with _in_repo_tree() as scratch:
        scripts = Path(scratch) / "scripts" / "__pycache__"
        scripts.mkdir(parents=True)
        (scripts / "thing.cpython-312.pyc").write_bytes(b"\x00\x0f\r\n not really bytecode")
        (Path(scratch) / "scripts" / "real.py").write_text("# source\n", encoding="utf-8")

        found = {p.name for p in secret_scan_files(Path(scratch))}
        assert found == {"real.py"}, f"compiled bytecode is being collected: {sorted(found)}"


def test_the_real_tree_is_clean():
    """The widened scope adds 253 newly-read files. This is the check that they are all clean, so
    the widening cannot leave the gate permanently red — a permanently red gate gets muted, and the
    original defect returns with company."""
    hits = [
        hit
        for path in secret_scan_files()
        for hit in scan_credential_patterns(path)
    ]
    assert hits == [], (
        "the widened scan reads files it did not read before, and something there is flagged: "
        + "; ".join(f"{h.get('file')}:{h.get('line')} {h.get('type')}" for h in hits)
    )


# ── a file the scan could not read is not a file with nothing in it (#2940) ─────────────────────

def test_a_directory_named_like_a_source_is_not_reported_as_clean(tmp_path):
    """`rglob` really does hand the scanner directories whose name ends in `.js`.

    Checked rather than assumed: on a temporary tree, `rglob("*.js")` yields a subdirectory named
    `weird.js`. So this is a shape the scanner meets in production, not a contrived one.
    """
    workers = tmp_path / "workers"
    workers.mkdir()
    impostor = workers / "looks_like_source.js"
    impostor.mkdir()

    assert impostor in set(secret_scan_files(tmp_path)), (
        "the collector no longer yields this shape, so this test would pass for the wrong reason"
    )
    with pytest.raises(UnreadableScanTarget):
        scan_credential_patterns(impostor)


def test_a_dangling_symlink_is_not_reported_as_clean(tmp_path):
    """The other shape `rglob` yields, and the one that does not depend on file permissions.

    The case that opened #2940 was a `chmod 000` file, but that one cannot be exercised as root —
    root reads it, the scan succeeds, and the assertion would pass without testing anything. A
    broken symlink raises for every uid, so this covers the same handler without that hole.
    """
    workers = tmp_path / "workers"
    workers.mkdir()
    dangling = workers / "dangling.js"
    dangling.symlink_to(workers / "gone.js")

    assert dangling in set(secret_scan_files(tmp_path))
    with pytest.raises(UnreadableScanTarget):
        scan_credential_patterns(dangling)


def test_a_chmod_000_probe_is_not_used_because_it_cannot_fail_reliably():
    """The report that opened #2940 used a `chmod 000` file. It is not asserted here, and the
    reason is worth keeping.

    There are two ways that probe tests nothing, and this repository sits on both:

    * as root the read succeeds anyway — permission bits are advisory;
    * on a Windows/DrvFs mount (this checkout is `/mnt/c`) they are ignored outright, so `chmod
      000` leaves the file readable.

    Measured here: after `probe.chmod(0o000)` the scan still returned its finding, so the probe
    would have gone green while proving nothing. The two tests above cover the same
    `except OSError` handler with shapes that fail to read on every uid and every filesystem — a
    directory, and a broken symlink.
    """


def test_the_audit_refuses_to_certify_a_tree_it_could_not_read(tmp_path, monkeypatch, capsys):
    """End to end: the exit code is non-zero and the clean bill of health is withheld.

    Both halves matter. A non-zero exit with the success line still printed teaches a reader that
    the line is decorative; the line is the gate's actual claim, and it must not survive a scan
    that did not happen.
    """
    workers = tmp_path / "workers"
    workers.mkdir()
    (workers / "readable.js").write_text("const answer = 42;\n", encoding="utf-8")
    (workers / "unreadable.js").mkdir()

    monkeypatch.setattr(scan_module, "REPO", tmp_path)
    exit_code = scan_module.main()
    out = capsys.readouterr().out

    assert exit_code != 0, f"an unreadable scan target left the audit green:\n{out}"
    assert "No hardcoded secrets found" not in out, (
        "it still certified a tree containing a file it never read:\n" + out
    )
    assert "unreadable.js" in out, f"the unreadable path is not named, so it cannot be fixed:\n{out}"


def test_a_readable_clean_tree_still_receives_its_clean_bill_of_health(
    tmp_path, monkeypatch, capsys
):
    """The other direction. Without this the new rule could be satisfied by never passing, which is
    the same failure wearing a green hat."""
    workers = tmp_path / "workers"
    workers.mkdir()
    (workers / "readable.js").write_text("const answer = 42;\n", encoding="utf-8")

    monkeypatch.setattr(scan_module, "REPO", tmp_path)
    exit_code = scan_module.main()
    out = capsys.readouterr().out

    assert exit_code == 0, out
    assert "No hardcoded secrets found" in out, out
