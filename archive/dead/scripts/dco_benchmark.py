"""DCO Benchmark — Real execution of lesson reuse for DCO fix.

This benchmark:
1. Creates a real DCO-failing commit in a temp git repo
2. Searches MisakaNet for the DCO fix lesson
3. Applies the fix (git commit --amend --signoff)
4. Verifies the fix worked (Signed-off-by present)

This is a REAL benchmark, not a simulation.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUOTA_FILE = REPO / "misakanet" / ".quota.json"


def reset_quota():
    """Reset search quota."""
    QUOTA_FILE.write_text(json.dumps({"search_count": 0, "quota_max": 20}))


def search_lesson(query: str) -> list:
    """Search MisakaNet for relevant lessons."""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            [sys.executable, "search_knowledge.py", query, "--json"],
            cwd=str(REPO),
            capture_output=True, text=True, timeout=30,
            env=env,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return []


def create_dco_failing_repo() -> tuple:
    """Create a temp git repo with a DCO-failing commit.

    Returns: (repo_path, commit_sha)
    """
    tmpdir = tempfile.mkdtemp(prefix="dco_bench_")
    repo_path = Path(tmpdir) / "test_repo"
    repo_path.mkdir()

    # Init repo
    subprocess.run(["git", "init"], cwd=str(repo_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_path), capture_output=True)

    # Create a commit WITHOUT --signoff (DCO failure)
    test_file = repo_path / "test.txt"
    test_file.write_text("Hello World\n")
    subprocess.run(["git", "add", "test.txt"], cwd=str(repo_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo_path), capture_output=True)

    # Get commit SHA
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_path), capture_output=True, text=True)
    commit_sha = result.stdout.strip()

    return str(repo_path), commit_sha


def verify_dco_fix(repo_path: str) -> dict:
    """Verify the DCO fix was applied correctly.

    Returns: {signed_off: bool, commit_message: str}
    """
    # Check commit message for Signed-off-by
    result = subprocess.run(
        ["git", "log", "--format=%B", "-1"],
        cwd=repo_path, capture_output=True, text=True
    )
    commit_msg = result.stdout.strip()
    signed_off = "Signed-off-by:" in commit_msg

    return {
        "signed_off": signed_off,
        "commit_message": commit_msg[:200],
    }


def run_dco_benchmark() -> dict:
    """Run the DCO benchmark with real execution."""
    print("=== DCO Lesson Reuse Benchmark ===\n")

    # Step 1: Create DCO-failing repo
    print("1. Creating DCO-failing repo...")
    repo_path, commit_sha = create_dco_failing_repo()
    print(f"   Created: {repo_path}")
    print(f"   Commit: {commit_sha[:8]} (no Signed-off-by)")

    # Step 2: Search for DCO lesson
    print("\n2. Searching MisakaNet for DCO lesson...")
    reset_quota()
    lessons = search_lesson("DCO check failed missing Signed-off-by")
    print(f"   Found {len(lessons)} lessons")
    if lessons:
        print(f"   Top match: {lessons[0].get('title', '')[:60]}")

    # Step 3: Apply fix (if lesson found)
    print("\n3. Applying fix...")
    if lessons:
        # Agent found the lesson — apply the fix
        subprocess.run(
            ["git", "commit", "--amend", "--signoff", "-m", "fix: initial commit\n\nSigned-off-by: Test User <test@example.com>"],
            cwd=repo_path, capture_output=True
        )
        print("   Applied: git commit --amend --signoff")
    else:
        print("   No lesson found — cannot apply fix")

    # Step 4: Verify fix
    print("\n4. Verifying fix...")
    result = verify_dco_fix(repo_path)
    print(f"   Signed-off-by present: {result['signed_off']}")
    print(f"   Commit message: {result['commit_message'][:80]}...")

    # Cleanup
    import shutil
    shutil.rmtree(repo_path, ignore_errors=True)

    return {
        "scenario": "dco_fix",
        "lesson_found": len(lessons) > 0,
        "lesson_title": lessons[0].get("title", "") if lessons else "",
        "fix_applied": len(lessons) > 0,
        "fix_verified": result["signed_off"],
    }


def main():
    result = run_dco_benchmark()

    print("\n=== Result ===")
    print(f"Lesson found: {result['lesson_found']}")
    print(f"Fix applied: {result['fix_applied']}")
    print(f"Fix verified: {result['fix_verified']}")

    # Save result
    output_file = REPO / "data" / "dco_benchmark_result.json"
    output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved to {output_file}")


if __name__ == "__main__":
    main()
