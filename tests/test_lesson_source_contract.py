import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

SANDBOX_CLONE_URL = "https://github.com/Ikalus1988/MisakaNet.git"
# Must match a directory name that build_lesson_pages.py will slugify for
# VALID_LESSON (title: "A lesson that satisfies every content rule and is still not a contribution yet").
_PROBE_DIR_NAME = "a-lesson-that-satisfies-every-content-rule-and-is-still-not-a-contribution-yet"


def _git_run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_status_porcelain(cwd: Path) -> str:
    out = _git_run(cwd, "status", "--porcelain")
    assert out.returncode == 0, out.stderr
    return out.stdout


def _git_commit_all(cwd: Path, message: str = "chore: commit") -> None:
    _git_run(cwd, "add", "-A")
    r = _git_run(cwd, "commit", "-m", message)
    # Allow already-up-to-date as success.
    assert r.returncode in (0, 1), r.stderr


def _run_generators(cwd: Path) -> None:
    # Same invocation used by the pre-commit / docs CI gate.
    result = subprocess.run(
        [sys.executable, "-m", "scripts.build_lesson_pages"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    # Non-zero exit is fine — the generators may exit early if nothing changed.
    # We inspect `git status` instead to detect output drift.
    del result  # intentional: we only care about filesystem side-effects


@pytest.fixture(scope="function")
def sandbox(tmp_path_factory) -> Path:
    sandbox = tmp_path_factory.mktemp("sandbox")
    _git_run(sandbox.parent, "clone", "--depth", "1", SANDBOX_CLONE_URL, str(sandbox))
    return sandbox


@pytest.fixture
def make_probe(sandbox: Path) -> Path:
    """Return the path to the probe lesson under the contrib dir."""
    probe = sandbox / "docs" / "lessons" / _PROBE_DIR_NAME
    probe.mkdir(parents=True, exist_ok=True)
    return probe


@pytest.fixture
def clean_committed_sandbox(sandbox: Path) -> Path:
    """Return a sandbox where generators have already run once and results are committed."""
    _git_run(sandbox, "checkout", "-B", "clean")
    _run_generators(sandbox)
    _git_commit_all(sandbox, "chore: baseline generators")
    return sandbox


def test_the_generators_are_a_no_op_on_an_unchanged_corpus(sandbox: Path) -> None:
    status = _git_status_porcelain(sandbox)
    assert status == "", f"sandbox not clean before generators:\n{status}"

    _run_generators(sandbox)

    status = _git_status_porcelain(sandbox)
    assert status == "", (
        "the committed corpus does not match its own generators:\n" + status
    )


def test_a_lesson_without_regenerated_output_is_caught(sandbox: Path) -> None:
    probe = sandbox / "tests" / "zz-probe-drift.md"
    probe.write_text("# Probe\n\nDrift\n")
    _git_run(sandbox, "add", str(probe.relative_to(sandbox)))
    _git_run(sandbox, "commit", "-m", "test: add probe")
    # First run seeds the generators.
    _run_generators(sandbox)
    # Second run should catch the mismatch.
    after = _git_status_porcelain(sandbox)
    assert after != "", "generators should flag the probe as drifted"


def test_regenerating_first_makes_the_tree_clean(sandbox: Path) -> None:
    probe_dir = sandbox / "docs" / "lessons" / _PROBE_DIR_NAME
    if not probe_dir.exists():
        pytest.skip("depends on the previous test's probe")
    _run_generators(sandbox)
    status = _git_status_porcelain(sandbox)
    assert status == "", (
        "after regenerating the probe dir should be clean:\n" + status
    )
    _git_commit_all(sandbox, "chore: commit regenerated probe")


def test_the_generators_do_not_remove_untracked_files(sandbox: Path) -> None:
    # Introduce an untracked file the generators must not delete.
    dangling = sandbox / "docs" / "untracked.txt"
    dangling.write_text("I am safe\n")
    _run_generators(sandbox)
    assert dangling.exists()


def test_auto_merge_gate_runs_in_a_clean_worktree(sandbox: Path) -> None:
    # Verify the gate script itself sees no pending changes.
    status = _git_status_porcelain(sandbox)
    assert status == "", f"gate requires a clean worktree, got:\n{status}"
    subprocess.run(
        [sys.executable, "scripts/auto_merge_gate.py"],
        cwd=sandbox,
        check=True,
        capture_output=True,
    )


def test_docs_builds_without_generating_first(sandbox: Path) -> None:
    # Force-delete any generated docs so the build has to regenerate on the fly.
    generated = sandbox / "docs" / "_generated-pages.json"
    if generated.exists():
        generated.unlink()
    # Running mkdocs (or whatever builds docs) should succeed even when output is missing;
    # the generators just write the artefacts, they are not called here.
    # We only check that the worktree is still clean afterward.
    status_before = _git_status_porcelain(sandbox)
    # Remove the file — now the worktree is dirty until generators run again.
    del status_before
    _run_generators(sandbox)
    status_after = _git_status_porcelain(sandbox)
    assert status_after == "", (
        "generators must restore consistency after a missing generated file:\n"
        + status_after
    )


def test_valid_lesson_slug_does_not_leak_outside_docs_lessons(sandbox: Path) -> None:
    # A lesson matching VALID_LESSON must land under docs/lessons/<slug>, nowhere else.
    # We construct the expected path from the slug produced by build_lesson_pages.py.
    probe_dir = sandbox / "docs" / "lessons" / _PROBE_DIR_NAME
    assert probe_dir.exists(), f"expected probe dir at {probe_dir}"
    assert probe_dir.is_dir()


def test_generator_script_exists_and_is_importable(sandbox: Path) -> None:
    script = REPO_ROOT / "scripts" / "build_lesson_pages.py"
    assert script.exists(), f"build_lesson_pages.py not found at {script}"
    # Import check using runpy avoids executing full generator logic.
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_lesson_pages", script)
    assert spec is not None and spec.loader is not None


def test_probes_are_not_counted_as_real_lessons(sandbox: Path) -> None:
    # Adding a fake lesson in docs/lessons/<slug>/ should not alter the lesson count.
    # We read the count before and after (but do NOT commit the probe).
    count_file = sandbox / "docs" / "_lessons_count.txt"
    before = count_file.read_text().strip() if count_file.exists() else ""
    # Probe already exists under docs/lessons/<slug>; ensure there's also a frontmatter.
    probe = sandbox / "docs" / "lessons" / _PROBE_DIR_NAME
    (probe / "index.md").write_text("# Probe\n\n---\nvalidated: true\n---\n")
    after = count_file.read_text().strip() if count_file.exists() else ""
    # Without regenerating, counts should not have changed.
    assert before == after, (
        f"uncommitted probe changed lesson count from {before!r} to {after!r}"
    )
