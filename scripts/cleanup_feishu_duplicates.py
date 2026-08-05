#!/usr/bin/env python3
"""scripts/cleanup_feishu_duplicates.py — Resolve #552 near-duplicate lessons"""
from pathlib import Path
import json, shutil

ROOT = Path(__file__).parent.parent

def cleanup():
    duplicate = ROOT / "lessons/contrib/feishu-bot-setup-complete.md"
    canonical = ROOT / "lessons/contrib/cc-connect-feishu-setup-complete.md"
    archive_dir = ROOT / "lessons/_archive"
    
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # The duplicate is already a meta-document acknowledging the situation.
    # Action: archive it, keep the substantive cc-connect version.
    if duplicate.exists():
        shutil.move(str(duplicate), str(archive_dir / "feishu-bot-setup-complete.md"))
        print(f"ARCHIVED: {duplicate.name} -> _archive/")
    
    # Verify canonical exists
    if canonical.exists():
        print(f"KEPT: {canonical.name} (canonical)")
    
    # Also archive the duplicate in docs/lessons/
    for dup2 in ROOT.glob("docs/lessons/*feishu-bot*"):
        dest = archive_dir / dup2.name
        if not dest.exists():
            shutil.move(str(dup2), str(dest))
            print(f"ARCHIVED: {dup2.name} -> _archive/")

    print("CLEANUP COMPLETE")

if __name__ == "__main__":
    cleanup()
