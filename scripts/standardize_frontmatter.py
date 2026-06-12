#!/usr/bin/env python3
"""
Standardize frontmatter across all lesson files in lessons/ directory.

Canonical format (JSON):
{
  "title": "...",
  "domain": "...",
  "source": "...",
  "status": "published|draft|deprecated",
  "tags": [...],
  "created": "2026-01-01 00:00:00 UTC",
  "updated": "2026-01-01 00:00:00 UTC",
  "subdomain": "...",  # optional
  "confidence": 0.8,   # optional
  "machine": "...",    # optional
  ...
}
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS_DIR = REPO / "lessons"

# Standard fields that should always be present
REQUIRED_FIELDS = ["title", "domain", "source", "status", "tags", "created", "updated"]
OPTIONAL_FIELDS = ["subdomain", "confidence", "machine", "bootstrapped", "author", "original_date", "quality"]

def parse_frontmatter(text: str) -> dict:
    """Parse JSON or YAML frontmatter from a .md file."""
    meta = {}
    
    # Try JSON format first
    m = re.match(r'^---\s*\n?(\{.*?\})\n?---', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try YAML format
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if m:
        raw = m.group(1).strip()
        for line in raw.split('\n'):
            line = line.strip()
            if ':' not in line:
                continue
            key, _, val = line.partition(':')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            
            # Handle array formats
            if val.startswith('[') and val.endswith(']'):
                try:
                    meta[key] = json.loads(val.replace("'", '"'))
                except json.JSONDecodeError:
                    meta[key] = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',') if v.strip()]
            elif val.startswith('- '):
                # YAML list format (multi-line)
                # This is a simplified handler - we'll process multi-line lists below
                meta[key] = [val[2:].strip()]
            else:
                meta[key] = val
        
        # Handle multi-line YAML lists (tags: \n- item1 \n- item2)
        for key in list(meta.keys()):
            if isinstance(meta[key], list) and len(meta[key]) == 1 and meta[key][0].startswith('- '):
                # Re-parse the raw for this key
                items = []
                in_list = False
                for line in raw.split('\n'):
                    line = line.strip()
                    if line == f"{key}:":
                        in_list = True
                        continue
                    if in_list:
                        if line.startswith('- '):
                            items.append(line[2:].strip().strip('"').strip("'"))
                        elif line and not line.startswith('-'):
                            break
                if items:
                    meta[key] = items
    
    return meta


def normalize_frontmatter(meta: dict, filepath: Path) -> dict:
    """Normalize frontmatter to canonical format."""
    normalized = {}
    
    # Title - required
    title = meta.get("title", filepath.stem)
    normalized["title"] = title
    
    # Domain - required
    domain = meta.get("domain", "general")
    if isinstance(domain, list):
        domain = domain[0] if domain else "general"
    normalized["domain"] = domain
    
    # Source - required
    source = meta.get("source", "unknown")
    normalized["source"] = source
    
    # Status - required
    status = meta.get("status", "draft")
    if status not in ["published", "draft", "deprecated"]:
        status = "draft"
    normalized["status"] = status
    
    # Tags - required (array)
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        # Try to parse as JSON array
        try:
            tags = json.loads(tags.replace("'", '"'))
        except json.JSONDecodeError:
            tags = [t.strip().strip('"').strip("'") for t in tags.strip('[]').split(',') if t.strip()]
    elif not isinstance(tags, list):
        tags = [str(tags)] if tags else []
    normalized["tags"] = tags
    
    # Created - required
    created = meta.get("created", "")
    if not created:
        # Try to extract from original_date
        created = meta.get("original_date", "")
    if not created:
        # Default to a reasonable timestamp
        created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    normalized["created"] = created
    
    # Updated - required
    updated = meta.get("updated", "")
    if not updated:
        updated = meta.get("created", "")
    if not updated:
        updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    normalized["updated"] = updated
    
    # Optional fields - preserve if present
    for field in OPTIONAL_FIELDS:
        if field in meta:
            val = meta[field]
            # Clean up confidence if it's a string
            if field == "confidence" and isinstance(val, str):
                try:
                    val = float(val)
                except ValueError:
                    val = 0.7
            normalized[field] = val
    
    # Preserve any other fields not in our known lists
    for key, val in meta.items():
        if key not in REQUIRED_FIELDS and key not in OPTIONAL_FIELDS and key not in normalized:
            normalized[key] = val
    
    return normalized


def rewrite_file(filepath: Path, dry_run: bool = False) -> bool:
    """Rewrite a single file with standardized frontmatter."""
    content = filepath.read_text(encoding="utf-8", errors="replace")
    
    # Check if file has frontmatter
    if not content.startswith("---"):
        print(f"  ⚠️  No frontmatter: {filepath}")
        return False
    
    # Parse existing frontmatter
    meta = parse_frontmatter(content)
    if not meta:
        print(f"  ⚠️  Failed to parse frontmatter: {filepath}")
        return False
    
    # Normalize
    normalized = normalize_frontmatter(meta, filepath)
    
    # Extract body (everything after second ---)
    parts = content.split("---", 2)
    if len(parts) < 3:
        print(f"  ⚠️  Malformed frontmatter: {filepath}")
        return False
    
    body = parts[2]
    
    # Build new content
    new_frontmatter = json.dumps(normalized, ensure_ascii=False)
    new_content = f"---\n{new_frontmatter}\n---\n{body}"
    
    if dry_run:
        print(f"  📝 Would update: {filepath}")
        print(f"     Title: {normalized['title']}")
        print(f"     Domain: {normalized['domain']}")
        print(f"     Status: {normalized['status']}")
        print(f"     Tags: {normalized['tags']}")
        return True
    
    # Write back
    filepath.write_text(new_content, encoding="utf-8")
    print(f"  ✅ Updated: {filepath}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Standardize frontmatter in lessons/")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without writing")
    parser.add_argument("--path", default="lessons", help="Path to lessons directory")
    args = parser.parse_args()
    
    lessons_dir = REPO / args.path
    if not lessons_dir.exists():
        print(f"Directory not found: {lessons_dir}")
        sys.exit(1)
    
    files = sorted(lessons_dir.glob("**/*.md"))
    print(f"Found {len(files)} markdown files")
    
    updated = 0
    skipped = 0
    errors = 0
    
    for f in files:
        if f.name == "index.md" or f.name.startswith("."):
            continue
        try:
            if rewrite_file(f, dry_run=args.dry_run):
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ❌ Error processing {f}: {e}")
            errors += 1
    
    print(f"\nSummary: {updated} updated, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    main()
