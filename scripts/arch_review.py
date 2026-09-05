#!/usr/bin/env python3
"""Architecture review script using Aider repo map (Issue #1184).

Generates repo-wide architecture analysis without reading every file.

Usage:
    # Generate architecture report
    python scripts/arch_review.py

    # Focus on specific module
    python scripts/arch_review.py --focus misakanet/server

    # Output as JSON
    python scripts/arch_review.py --json
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

ARCH_QUESTIONS = [
    "Is the MCP server architecture sound? Are there separation of concerns issues?",
    "What's the dependency graph between misakanet/ modules? Any circular deps?",
    "Which scripts/ files should be refactored into misakanet/ package?",
    "Are there security concerns in the intake pipeline?",
    "What lessons are missing for Python packaging, Docker, and CI/CD?",
    "Are there cross-module dependency issues that could cause maintenance problems?",
]


def check_aider_available() -> bool:
    """Check if aider is installed."""
    try:
        result = subprocess.run(
            ["aider", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def generate_repo_map() -> dict:
    """Generate repo map using tree-sitter (if available) or file listing."""
    # Try aider's repo map
    if check_aider_available():
        try:
            result = subprocess.run(
                ["aider", "--repo-map", "--no-git", "--yes", "--message",
                 "List all Python files and their main classes/functions"],
                capture_output=True, text=True, timeout=120,
                cwd=str(REPO_ROOT),
            )
            if result.returncode == 0:
                return {"source": "aider", "map": result.stdout}
        except Exception:
            pass

    # Fallback: file listing with structure
    return {"source": "file-listing", "map": generate_file_listing()}


def generate_file_listing() -> str:
    """Generate simple file listing as fallback."""
    lines = []
    for py_file in sorted(REPO_ROOT.rglob("*.py")):
        if "__pycache__" in str(py_file) or ".git" in str(py_file):
            continue
        rel = py_file.relative_to(REPO_ROOT)
        # Read first few lines for docstring/imports
        try:
            with open(py_file) as f:
                head = f.read(500)
            # Extract first docstring or class/function defs
            defs = []
            for line in head.split("\n"):
                line = line.strip()
                if line.startswith(("class ", "def ", "async def ")):
                    defs.append(line.split("(")[0].split(":")[0])
            if defs:
                lines.append(f"{rel}: {', '.join(defs[:5])}")
            else:
                lines.append(str(rel))
        except Exception:
            lines.append(str(rel))

    return "\n".join(lines)


def analyze_structure() -> dict:
    """Analyze repo structure for architecture insights."""
    analysis = {
        "modules": {},
        "patterns": [],
        "concerns": [],
    }

    # Analyze misakanet/ package
    misakanet_dir = REPO_ROOT / "misakanet"
    if misakanet_dir.exists():
        for subdir in sorted(misakanet_dir.iterdir()):
            if subdir.is_dir() and not subdir.name.startswith("_"):
                py_files = list(subdir.glob("*.py"))
                analysis["modules"][f"misakanet/{subdir.name}"] = {
                    "files": len(py_files),
                    "has_init": (subdir / "__init__.py").exists(),
                }

    # Check for common patterns
    patterns = {
        "has_tests": (REPO_ROOT / "tests").exists(),
        "has_docs": (REPO_ROOT / "docs").exists(),
        "has_ci": (REPO_ROOT / ".github" / "workflows").exists(),
        "has_mcp": (REPO_ROOT / "misakanet" / "server").exists(),
        "has_workers": (REPO_ROOT / "workers").exists(),
        "has_lessons": (REPO_ROOT / "lessons").exists(),
    }
    analysis["patterns"] = [k for k, v in patterns.items() if v]

    # Check for concerns
    concerns = []
    # Large files
    for py_file in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in str(py_file) or ".venv" in str(py_file):
            continue
        try:
            lines = sum(1 for _ in open(py_file))
            if lines > 500:
                concerns.append(f"Large file: {py_file.relative_to(REPO_ROOT)} ({lines} lines)")
        except Exception:
            pass

    # Missing __init__.py
    for subdir in (REPO_ROOT / "misakanet").rglob("*"):
        if subdir.is_dir() and not (subdir / "__init__.py").exists():
            if not subdir.name.startswith(("_", ".")):
                concerns.append(f"Missing __init__.py: {subdir.relative_to(REPO_ROOT)}")

    analysis["concerns"] = concerns[:10]  # Limit

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Architecture review")
    parser.add_argument("--focus", help="Focus on specific module")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--questions", action="store_true", help="Show review questions")
    args = parser.parse_args()

    if args.questions:
        print("\n  Architecture Review Questions:")
        for i, q in enumerate(ARCH_QUESTIONS, 1):
            print(f"  {i}. {q}")
        return

    print("\n  Generating architecture analysis...")
    analysis = analyze_structure()
    repo_map = generate_repo_map()

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": str(REPO_ROOT),
        "analysis": analysis,
        "repo_map_source": repo_map["source"],
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n  Architecture Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  {'='*50}")

        print(f"\n  Modules:")
        for mod, info in analysis["modules"].items():
            init = "✓" if info["has_init"] else "✗"
            print(f"    {mod}: {info['files']} files, __init__.py: {init}")

        print(f"\n  Patterns Present:")
        for p in analysis["patterns"]:
            print(f"    ✓ {p}")

        if analysis["concerns"]:
            print(f"\n  Potential Concerns:")
            for c in analysis["concerns"]:
                print(f"    ⚠ {c}")

        print(f"\n  Repo Map Source: {repo_map['source']}")
        if repo_map["source"] == "file-listing":
            print("  (Install aider-chat for tree-sitter based analysis)")


if __name__ == "__main__":
    main()
