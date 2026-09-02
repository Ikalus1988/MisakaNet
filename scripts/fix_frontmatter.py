#!/usr/bin/env python3
"""Fix corrupted lesson frontmatter (dual-axis review 2026-08-28).

Repairs 3 systemic damage families found by the review:
  A. Broken `'{"title"':` JSON-injection lines inside YAML frontmatter
     (metadata-normalization artifact) + duplicate second frontmatter block
  B. JSON object + YAML `provenance:` mixed in one --- block
  C. Stray `---{"title":...}---` injection lines in the body

Strategy: parse the first valid frontmatter block, merge any recoverable
fields from the injected JSON, drop `verification: metadata-normalized` and
junk lines, keep provenance (if present) as an HTML comment after the block,
and rewrite the file as a single clean YAML frontmatter + body.

Usage:
    python3 scripts/fix_frontmatter.py --dry-run   # preview
    python3 scripts/fix_frontmatter.py --fix       # apply
"""
import argparse
import json
import re
import sys
import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LESSONS = REPO / "lessons"

# Fields to keep in the rewritten frontmatter (in this order)
KEEP_KEYS = ["title", "domain", "tags", "status", "created", "updated",
             "language", "source", "confidence", "domain_expert",
             "verified_date", "subdomain", "summary"]
# Junk/derived keys to drop
DROP_KEYS = {"verification", "provenance"}
# Keys that must be excluded from the injected-JSON merge (already sourced from YAML)
MERGE_KEYS = {"title", "domain", "tags", "status", "created", "updated",
              "source", "confidence", "domain_expert", "verified_date", "subdomain"}


def extract_json_blob(text: str) -> dict:
    """Try to recover a dict from the corrupted injected JSON (mismatched quotes)."""
    # The pattern looks like: '{"title"': '...", "domain": "marketing", ...}'
    # Fix the broken leading quote: '{"title"' -> {"title"
    m = re.search(r"'?\{[^}]*\}'?", text)
    if not m:
        return {}
    blob = m.group(0)
    blob = re.sub(r"^'", "", blob)
    blob = blob.rstrip("'").rstrip()
    # Normalize broken quotes: key "..." followed by ': value
    blob = re.sub(r'"(\w+)"\s*:', r'"\1":', blob)
    # Some have unmatched trailing quote after value: 'value", ...} -> "value", ...}
    blob = re.sub(r"'([^']*)'", r'"\1"', blob)
    try:
        d = json.loads(blob)
        return d if isinstance(d, dict) else {}
    except Exception:
        # Fallback: regex key: value pairs
        out = {}
        for km in re.finditer(r'"(\w+)"\s*:\s*("(?:[^"\\]|\\.)*"|\[[^\]]*\]|[^\s,}]+)', blob):
            key = km.group(1)
            val = km.group(2)
            try:
                out[key] = json.loads(val)
            except Exception:
                out[key] = val.strip('"')
        return out


def is_junk_line(line: str) -> bool:
    """Detect corrupted injection / metadata-normalized junk lines."""
    s = line.strip()
    if not s:
        return False
    if re.match(r"^'?\{?\s*\"\w+\"\s*':", s):        # '{"title"': ...
        return True
    if s.startswith("'{\"") and "':" in s:            # '{"title"': ...
        return True
    if s == "verification: metadata-normalized":
        return True
    if re.match(r"^---?\{.*?\}---?$", s):             # ---{"title":...}---
        return True
    # Continuation lines of a JSON injection (indented key: value)
    if re.match(r"^\s+\"\w+\":", s) and "'" not in s[:4]:
        return False  # could be legit YAML continuation; be conservative
    return False


def parse_first_frontmatter(text: str):
    """Return (fm_dict, body_start_index) for the first valid --- block.

    Strips corrupted JSON-injection blocks (multi-line `'{"title"': ... }'`)
    and 'verification: metadata-normalized' BEFORE parsing.
    """
    m = re.match(r"^---\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return {}, 0
    raw = m.group(1)
    # Block-level filtering: skip injection blocks and junk lines
    clean_lines = []
    in_injection = False
    for line in raw.splitlines():
        s = line.strip()
        if re.match(r"^'?\{?\s*\"\w+\"\s*':", s) or s.startswith("'{\""):
            in_injection = True
            continue
        if in_injection:
            # continuation until the block ends with }'
            if s.endswith("}'") or (s.endswith("}") and "'" in s):
                in_injection = False
            continue
        if s == "verification: metadata-normalized":
            continue
        if re.match(r"^---?\{.*?\}---?$", s):
            continue
        clean_lines.append(line)
    clean_raw = "\n".join(clean_lines)
    # Try YAML
    try:
        fm = yaml.safe_load(clean_raw)
        if isinstance(fm, dict):
            return fm, m.end()
    except Exception:
        pass
    # Try JSON — if a YAML provenance block trails the JSON object, strip it
    # so json.loads can parse the leading JSON only (raw_decode semantics).
    if clean_raw.strip().startswith("{"):
        try:
            fm = json.JSONDecoder().raw_decode(clean_raw.strip())[0]
            if isinstance(fm, dict):
                return fm, m.end()
        except Exception:
            pass
    return {}, m.end()


def strip_duplicate_frontmatter(text: str) -> str:
    """Remove a duplicate second ---...--- block that appears right after the
    first frontmatter (a metadata-normalization artifact)."""
    m = re.match(r"^---\n.*?\n---\s*\n(---\n.*?\n---\s*\n?)(.*)", text, re.DOTALL)
    if m:
        # Only strip if the second block looks like metadata (contains title/domain)
        second_block = m.group(1)
        if re.search(r"title:|domain:|'?\{\"", second_block):
            return text[: m.start(1)] + m.group(2)
    return text


def fix_file(path: Path, dry_run: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    orig = text

    # Remove duplicate second frontmatter block first
    text = strip_duplicate_frontmatter(text)

    # Extract injected JSON blob (if any) for field recovery
    injected = extract_json_blob(text)
    # Parse first frontmatter (junk lines already filtered inside)
    fm, body_start = parse_first_frontmatter(text)
    if not fm:
        return False  # leave untouched if unparseable

    # Merge recoverable fields from injected JSON (only for missing keys)
    for k in MERGE_KEYS:
        if k not in fm and k in injected:
            fm[k] = injected[k]
    # Normalize
    for k in list(fm.keys()):
        if k in DROP_KEYS:
            del fm[k]
        elif k == "domain" and isinstance(fm[k], list):
            fm[k] = fm[k][0] if fm[k] else "general"
        elif k == "tags" and not isinstance(fm[k], list):
            fm[k] = [fm[k]] if fm[k] else []
        elif k in ("confidence",) and isinstance(fm[k], str):
            try:
                fm[k] = float(fm[k])
            except ValueError:
                pass
    # Ensure required keys
    fm.setdefault("title", path.stem)
    fm.setdefault("status", "published")
    if "domain" not in fm or not fm["domain"]:
        fm["domain"] = "contrib" if "contrib" in str(path) else "core"

    # Order keys: KEEP_KEYS first, then any extras alphabetically
    ordered = {k: fm[k] for k in KEEP_KEYS if k in fm}
    for k in sorted(fm.keys()):
        if k not in ordered:
            ordered[k] = fm[k]

    # Extract provenance block (if inside frontmatter, move to HTML comment)
    provenance_comment = ""
    # Body starts after first frontmatter
    body = text[body_start:]
    # Strip a duplicate second frontmatter block at the top of the body
    dm = re.match(r"^---\n.*?\n---\s*\n?", body, re.DOTALL)
    if dm:
        second_block = dm.group(0)
        if re.search(r"title:|domain:|'?\{\"", second_block):
            body = body[dm.end():]
    # Remove orphan metadata lines between the frontmatter and the first
    # ## heading (a second, non-fenced metadata dump: created:/domain:/
    # title:/verification: metadata-normalized + JSON injection).
    body = re.sub(
        r"^(?:[ \t]*(?:created|updated|domain|source|status|title|subdomain|"
        r"language|confidence|domain_expert|verified_date|verification|tags|provenance)"
        r":[^\n]*\n)+",
        "", body, flags=re.M, count=1,
    )
    # Remove stray multi-line JSON-injection blocks from the body (line-based)
    body_lines = []
    in_injection = False
    for line in body.splitlines():
        s = line.strip()
        if re.match(r"^'?\{?\s*\"\w+\"\s*':", s) or s.startswith("'{\""):
            in_injection = True
            continue
        if in_injection:
            if s.endswith("}'") or (s.endswith("}") and "'" in s):
                in_injection = False
            continue
        if re.match(r"^---?\{.*?\}---?$", s):
            continue
        body_lines.append(line)
    body = "\n".join(body_lines)
    # Find provenance in body (either as HTML comment or YAML-ish block)
    pm = re.search(r"<!-- provenance:[\s\S]*?-->", body)
    if pm:
        provenance_comment = pm.group(0)
    elif "provenance:" in body[:500]:
        pm2 = re.search(r"provenance:[\s\S]*?(?=\n##|\n---|\Z)", body)
        if pm2:
            provenance_comment = "<!-- provenance:\n" + pm2.group(0) + "\n-->"
    # Remove provenance from body if it's a bare YAML block right after frontmatter
    body = re.sub(r"\n*provenance:[\s\S]*?(?=\n##|\n---|\Z)", "", body, count=1)
    body = re.sub(r"\n*<!-- provenance:[\s\S]*?-->", "", body, count=1)

    # Remove stray injection lines from body
    body = re.sub(r"^'?\{.*?\}'?\s*$", "", body, flags=re.M)
    body = re.sub(r"^---\{.*?\}---\s*$", "", body, flags=re.M)

    # Rebuild file
    yaml_fm = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False, default_flow_style=False)
    new_text = "---\n" + yaml_fm.rstrip() + "\n---\n"
    if provenance_comment:
        new_text += "\n" + provenance_comment + "\n"
    new_text += "\n" + body.lstrip("\n")

    if new_text.strip() == orig.strip():
        return False

    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Fix corrupted lesson frontmatter")
    ap.add_argument("--dry-run", action="store_true", help="preview only")
    ap.add_argument("--fix", action="store_true", help="apply fixes")
    ap.add_argument("--files", nargs="*", help="specific files (else all core+contrib)")
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
    for f in fixed[:20]:
        print(f"  - {f}")
    if len(fixed) > 20:
        print(f"  ... and {len(fixed)-20} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
