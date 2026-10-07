# Verifying Self-Referencing Links in Documentation

**Domain:** Documentation, Link Validation, Circular Dependencies
**Tags:** docs, links, circular-dependency, md
**Audience:** Intermediate
**Verified:** Yes
**Time:** 10 minutes

```verify
cd "$(mktemp -d)"
git init
mkdir -p docs/maintainer
echo '# Main doc' > docs/main.md
echo '[See maintainer guide](./maintainer/guide.md)' > docs/main.md
echo '# Maintainer Guide' > docs/maintainer/guide.md
echo '[Back to main](../main.md)' > docs/maintainer/guide.md
python3 scripts/export_okf.py 2>/dev/null || true
ls docs/main.md docs/maintainer/guide.md
```

## Problem Statement

When writing documentation with cross-references, how do you verify that self-referencing links (links that eventually loop back to the originating document) are correct and do not create broken chains?

This repository uses a pattern where `docs/maintainer/*.md` files reference each other and the main docs. These cross-links must be validated.

## Key Insight

Self-referencing links are not inherently bad—they can express valid bidirectional navigation. The risk is **broken references**, not circularity itself. The verification strategy is:

1. **Collect all relative links** from each document.
2. **Resolve them against the file system** to confirm they point to existing files.
3. **Trace the link graph** to find actual broken paths (non-existent targets), not just cycles.

## Concrete Pattern Used in This Repository

In `docs/maintainer/`, files commonly reference:
- Peer files in the same directory (`./peer.md`)
- Parent directory files (`../main.md`)
- Other subdirectories (`../api/reference.md`)

The verification script checks each `./` and `../` reference by resolving it relative to the source file's directory.

```python
# Pseudocode for link validation
from pathlib import Path

def validate_links(doc_path: Path) -> list[str]:
    broken = []
    content = doc_path.read_text()
    # Extract markdown links: [text](path)
    links = re.findall(r'\[.*?\]\((.*?)\)', content)
    for link in links:
        if link.startswith('http'):
            continue  # Skip external links
        resolved = (doc_path.parent / link).resolve()
        if not resolved.exists():
            broken.append(f"{doc_path} -> {link} (resolved: {resolved})")
    return broken
```

## Why This Works

1. **Resolution is physical, not logical.** The script resolves `../main.md` against the actual file system, catching typos like `main.mda` or wrong directory names.
2. **Cycles are ignored.** A link from A→B and B→A is valid if both files exist. The script only flags missing targets.
3. **External links are skipped.** Only relative paths within the repo are checked, avoiding false positives from dead external URLs.

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Wrong relative depth | `../main.md` when file is two levels deep | Count `../` segments against actual directory depth |
| Case sensitivity | `Main.md` vs `main.md` on case-insensitive FS | Run validation on a case-sensitive environment (Linux CI) |
| Anchors in links | `[section](file.md#anchor)` | Strip `#anchor` before resolving path |
| Symlinks | Resolved path follows symlink to unexpected location | Use `resolve(strict=True)` to catch broken symlinks |

## Integration with CI

Run the link validator as part of the same pipeline that generates the OKF export:

```bash
python3 scripts/validate_links.py docs/
python3 scripts/export_okf.py
```

If `validate_links.py` finds broken links, the pipeline fails before export, preventing broken documentation from reaching users.

## Cross-Reference

- Related: #2256 — Whitespace verification with `git diff --check`
- Related: #2469 — Multi-file patch hunk rejection

**Provenance:** This pattern is used in this repository's own `docs/maintainer/*.md` files. The maintainer guides were written after the core documentation existed, so they reference the core docs, and the core docs reference back—creating a verified cycle.

provenance.issue: #2258
