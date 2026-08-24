#!/usr/bin/env python3
"""Add provenance blocks to lessons that lack them.

Usage:
    python3 scripts/add_provenance.py [--domain contrib|devops] [--dry-run]

Infer provenance from:
- source field in frontmatter
- created date
- Git history (if available)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO_ROOT / "lessons"


def get_git_info(filepath: Path) -> dict | None:
    """Get git history for a file (who merged, when)."""
    try:
        # Get the last commit that modified this file
        result = subprocess.run(
            ["git", "log", "--format=%H|%an|%ae|%aI", "-1", "--", str(filepath)],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|")
            if len(parts) == 4:
                return {
                    "commit": parts[0][:8],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3][:10],
                }
    except Exception:
        pass
    return None


def infer_provenance(frontmatter: dict, git_info: dict | None) -> dict:
    """Infer provenance from frontmatter and git history."""
    source = frontmatter.get("source", "unknown")
    created = frontmatter.get("created", "")

    # Determine source type
    if source in ("practical-experience", "internal"):
        source_type = "internal"
    elif source.startswith("http"):
        source_type = "external-reference"
    elif source == "github-pr":
        source_type = "github-pr"
    else:
        source_type = "unknown"

    # Determine contributor
    contributor = "unknown"
    if git_info:
        contributor = git_info["author"]
    elif source_type == "internal":
        contributor = "MisakaNet Community"

    # Determine merged_at
    merged_at = created
    if git_info:
        merged_at = git_info["date"]

    return {
        "source": source_type,
        "contributor": contributor,
        "merged_at": merged_at,
        "evidence": "post-publication" if source_type == "unknown" else "pr-merged",
    }


def add_provenance_to_file(filepath: Path, dry_run: bool = False) -> bool:
    """Add provenance block to a lesson file. Returns True if modified."""
    content = filepath.read_text(encoding="utf-8")

    # Check if already has provenance
    if "provenance:" in content:
        return False

    created = ""
    source = "unknown"
    new_content = None

    # Format 1: ---\n{JSON}\nprovenance:\n...\n---\nbody
    if content.startswith("---"):
        # Find the first closing ---
        first_close = content.find("---", 3)
        if first_close == -1:
            return False

        frontmatter_text = content[3:first_close]
        rest = content[first_close + 3:]

        # Try JSON parse
        try:
            fm_json = json.loads(frontmatter_text)
            created = fm_json.get("created", "")
            source = fm_json.get("source", "unknown")
        except json.JSONDecodeError:
            # Try YAML-style key: value
            for line in frontmatter_text.strip().split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key == "created":
                        created = value
                    elif key == "source":
                        source = value

        # Get git info
        git_info = get_git_info(filepath)

        # Infer provenance
        provenance = infer_provenance({"source": source, "created": created}, git_info)

        # Build provenance block
        prov_block = f"\nprovenance:\n"
        prov_block += f'  source: "{provenance["source"]}"\n'
        prov_block += f'  contributor: "{provenance["contributor"]}"\n'
        prov_block += f'  merged_at: "{provenance["merged_at"]}"\n'
        prov_block += f'  evidence: "{provenance["evidence"]}"\n'

        new_content = f"---{frontmatter_text}{prov_block}---{rest}"

    # Format 2: {JSON}\n---\nbody or {JSON}\n\n## body
    elif content.startswith("{"):
        try:
            # Try to find --- separator first
            json_end = content.find("\n---")
            if json_end != -1:
                json_text = content[:json_end]
                rest = content[json_end:]
            else:
                # Fall back to multiple newlines (handle \n\n, \n\n\n, etc.)
                import re
                match = re.search(r'\n{2,}', content)
                if not match:
                    return False
                json_end = match.start()
                json_text = content[:json_end]
                rest = content[json_end:]

            fm_json = json.loads(json_text)
            created = fm_json.get("created", "")
            source = fm_json.get("source", "unknown")

            # Get git info
            git_info = get_git_info(filepath)

            # Infer provenance
            provenance = infer_provenance({"source": source, "created": created}, git_info)

            # Add provenance to the JSON object
            fm_json["provenance"] = {
                "source": provenance["source"],
                "contributor": provenance["contributor"],
                "merged_at": provenance["merged_at"],
                "evidence": provenance["evidence"],
            }
            # Preserve original formatting (pretty-printed or single-line)
            if "\n" in json_text:
                new_content = json.dumps(fm_json, ensure_ascii=False, indent=2) + rest
            else:
                new_content = json.dumps(fm_json, ensure_ascii=False) + rest
        except (json.JSONDecodeError, ValueError):
            return False
    else:
        return False

    if new_content is None:
        return False

    if dry_run:
        print(f"  Would add provenance to {filepath.name}: {provenance}")
        return True

    filepath.write_text(new_content, encoding="utf-8")
    print(f"  Added provenance to {filepath.name}: {provenance}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Add provenance to lessons")
    parser.add_argument("--domain", choices=["contrib", "devops", "all"], default="all",
                        help="Domain to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--limit", type=int, default=None, help="Max files to process")
    args = parser.parse_args()

    domains = ["contrib", "devops"] if args.domain == "all" else [args.domain]
    total_modified = 0

    for domain in domains:
        domain_dir = LESSONS_DIR / domain
        if not domain_dir.exists():
            print(f"Skipping {domain}: directory not found")
            continue

        files = sorted(domain_dir.glob("*.md"))
        # Skip non-lesson files
        files = [f for f in files if f.name not in ("README.md", "index.md", "_meta.md")]
        print(f"\nProcessing {domain}: {len(files)} files")

        modified = 0
        for filepath in files:
            if args.limit and modified >= args.limit:
                break
            if add_provenance_to_file(filepath, args.dry_run):
                modified += 1

        total_modified += modified
        action = "Would modify" if args.dry_run else "Modified"
        print(f"  {action} {modified}/{len(files)} files")

    print(f"\nTotal: {total_modified} files {'would be ' if args.dry_run else ''}modified")


if __name__ == "__main__":
    main()
