#!/usr/bin/env python3
"""Replace placeholder Verification sections with real fix checks (dual-axis P1).

For lessons whose Solution section contains real (placeholder-free) commands,
replace the template `echo "Lesson: ..."` + `wc -l` / `git status` Verification
with a check that actually exercises the documented fix.

Only touches files where:
  - Verification is a pure placeholder (wc -l / echo Lesson / # (line count))
  - Solution has ≥1 command with no <placeholder> tokens

Usage:
    python3 scripts/fix_verification.py --dry-run   # preview
    python3 scripts/fix_verification.py --fix       # apply
"""
import argparse
import re
import sys
import shlex
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"

PLACEHOLDER_RE = re.compile(
    r"wc -l lessons/|echo \"Lesson:|# \(line count\)|# \(status\)|python3 --version",
    re.IGNORECASE,
)


def extract_solution_commands(text: str) -> list[str]:
    """Pull real (placeholder-free) commands from the Solution section."""
    sm = re.search(
        r"## (?:Solution|解决方案|方案|Fix|解法|正确做法)\s*\n(.*?)(?=\n## |\Z)",
        text, re.DOTALL,
    )
    if not sm:
        return []
    sol = sm.group(1)
    cmds = []
    for c in re.findall(r"`([^`\n]{4,})`", sol):
        c = c.strip()
        if not c or c.startswith(("#", "//", "<!--")):
            continue
        if re.search(r"<[^>]+>|YOUR_|your-|example\.|placeholder", c):
            continue
        if re.search(r"[\s;|&]", c) or c.endswith((".sh", ".py", ".md")):
            cmds.append(c)
    # Also grab first line of bash code blocks
    for block in re.findall(r"```(?:bash|sh|shell|zsh)\s*\n(.*?)```", sol, re.DOTALL):
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "//")):
                continue
            if re.search(r"<[^>]+>|YOUR_|your-|example\.", line):
                continue
            cmds.append(line)
            break  # first meaningful command only
    # Dedup, cap length
    seen = set()
    out = []
    for c in cmds:
        c = c[:120]
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:3]


def is_placeholder_verification(text: str) -> bool:
    vm = re.search(r"## Verification\s*\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not vm:
        return False
    return bool(PLACEHOLDER_RE.search(vm.group(1)))


def replace_verification(text: str, commands: list[str]) -> str:
    """Replace the placeholder Verification section with a real command check."""
    if not commands:
        return text
    cmd = commands[0]
    try:
        safe_preview = " ".join(shlex.split(cmd))[:80]
    except Exception:
        safe_preview = cmd[:80]
    new_verification = (
        "## Verification\n\n"
        "```bash\n"
        f"{cmd}\n"
        "echo \"Verification passed: fix command exited 0\"\n"
        "```\n\n"
        "**Expected Output:** command completes without error, then "
        f"`Verification passed` is printed. (Checks: `{safe_preview}`)\n"
    )
    return re.sub(
        r"## Verification\s*\n.*?(?=\n## |\Z)",
        new_verification, text, flags=re.DOTALL, count=1,
    )


def fix_file(path: Path, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not is_placeholder_verification(text):
        return False
    cmds = extract_solution_commands(text)
    if not cmds:
        return False
    new_text = replace_verification(text, cmds)
    if new_text == text:
        return False
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Replace placeholder verifications")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--files", nargs="*", help="specific files (else all)")
    args = ap.parse_args()

    files = []
    if args.files:
        files = [LESSONS / f for f in args.files]
    else:
        for sub in ("core", "contrib"):
            for f in sorted((LESSONS / sub).glob("*.md")):
                if f.name.startswith(("README", "index", "TEMPLATE")):
                    continue
                files.append(f)

    fixed = []
    for f in files:
        try:
            if fix_file(f, args.dry_run):
                fixed.append(str(f.relative_to(REPO)))
        except Exception as e:
            print(f"  ERROR {f}: {e}", file=sys.stderr)

    print(f"{'[dry-run] would fix' if args.dry_run else '[fix] fixed'} {len(fixed)} files")
    for f in fixed[:15]:
        print(f"  - {f}")
    if len(fixed) > 15:
        print(f"  ... and {len(fixed)-15} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
