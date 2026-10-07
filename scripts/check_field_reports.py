import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO_ROOT / "docs" / "field-reports"


def find_leaks(directory: Path, pattern: str = "/mnt/c/Users/") -> list[tuple[Path, int]]:
    results = []
    for md in sorted(directory.rglob("*.md")):
        lines = md.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            if pattern in line:
                results.append((md, i))
    return results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="Base SHA for diff mode")
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    args = parser.parse_args()

    target_dir = Path(args.dir)
    if not target_dir.is_dir():
        print(f"ERROR: {target_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    leaks = find_leaks(target_dir)

    if args.base:
        import subprocess
        diff_files = subprocess.run(
            ["git", "diff", "--name-only", args.base, "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT
        ).stdout.strip().splitlines()
        leaked_paths = {str(l[0]) for l in leaks}
        changed_md = {f for f in diff_files if f.endswith(".md") and "docs/field-reports/" in f}
        leaks = [l for l in leaks if str(l[0]) in changed_md or str(l[0]) in leaked_paths]

    total_files = len({p for p, _ in leaks}) if leaks else len(list(target_dir.rglob("*.md")))
    gating = len(leaks)
    info = total_files - gating
    legacy = 0

    verdict = "FAIL" if gating else "PASS"
    print(f"# field reports: {target_dir.relative_to(REPO_ROOT)}  ·  {len(list(target_dir.rglob('*.md')))} file(s)  ·  scope: {'strict' if not args.base else 'diff'}")
    print(f"SUMMARY files={total_files} gating={gating} info={info} legacy={legacy} verdict={verdict}")

    for f, lineno in leaks:
        rel = f.relative_to(REPO_ROOT)
        print(f"  LEAK {rel}:{lineno}")

    sys.exit(1 if verdict == "FAIL" else 0)


if __name__ == "__main__":
    main()
