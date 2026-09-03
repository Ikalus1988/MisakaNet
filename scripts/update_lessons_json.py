#!/usr/bin/env python3
"""Regenerate data/lessons.json from indexed lesson directories.

The public index intentionally keeps a stable, lightweight shape used by the
website and GitHub workflows. It indexes curated/core lessons and contrib
lessons, while excluding archives, drafts, templates, locale docs, and the
top-level lessons/index.md.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from misakanet.evidence import evidence_of, trust_score  # noqa: E402

LESSONS_DIR = REPO / "lessons"
OUTPUT = REPO / "data" / "lessons.json"
INDEXED_DIRS = ("core", "contrib")
# Non-lesson markdown that must never be indexed (mirrors sync_lessons_to_d1.py).
EXCLUDED = {"README.md", "index.md", "TEMPLATE.md", "CONTRIBUTING.md"}


def parse_frontmatter(text: str) -> dict:
    """Parse lesson frontmatter: JSON first, then YAML fallback.

    Older lessons use JSON frontmatter, some with a trailing YAML-ish
    `provenance:` block (081e64d5) — raw_decode extracts only the leading JSON
    object. Newer lessons (2026-08+) use YAML frontmatter, which the public
    index now trusts too (build_worker_index.py already does). Falls back to
    {} when neither parses.
    """
    if not text.startswith("---\n") and not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    raw = text[4:end].strip()
    if raw.startswith("{"):
        try:
            return json.JSONDecoder().raw_decode(raw)[0]
        except (json.JSONDecodeError, ValueError):
            pass
    # YAML fallback — import lazily so the script works without pyyaml
    try:
        import yaml
        fm = yaml.safe_load(raw)
        if isinstance(fm, dict):
            return fm
    except Exception:
        pass
    return {}


def get_preview(content: str, max_chars: int = 2400) -> str:
    """Extract lesson body after frontmatter for inline preview."""
    lines = content.split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    body = '\n'.join(lines[start:]).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + '\n\n[clipped]'
    return body


def get_summary(content: str, max_chars: int = 160) -> str:
    """Extract first meaningful sentence after frontmatter."""
    lines = content.split('\n')
    start = 0
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                start = i + 1
                break
    for line in lines[start:]:
        line = line.strip()
        if not line:
            continue
        if line == "---":
            continue
        if line.startswith("---{") and line.endswith("}---"):
            continue
        if line == "{":
            continue
        if line.startswith("{") and line.endswith("}"):
            continue
        if line.startswith('#') or line.startswith('- **'):
            continue
        if line.startswith("domain:") or line.startswith("title:") or line.startswith("verification:"):
            continue
        if line:
            return line[:max_chars] + ('…' if len(line) > max_chars else '')
    return ''


def main():
    entries = []
    for lesson_dir in INDEXED_DIRS:
        files = sorted((LESSONS_DIR / lesson_dir).glob("*.md"))
        for f in files:
            if f.name.startswith(".") or f.name in EXCLUDED:
                continue
            content = f.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(content)
            # YAML frontmatter may yield non-JSON types (date, etc.) — normalize
            meta = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in meta.items()}
            title = meta.get("title", f.stem)
            domain = meta.get("domain", lesson_dir)
            if isinstance(domain, list):
                domain = domain[0] if domain else lesson_dir
            tags = meta.get("tags", [])
            if not isinstance(tags, list):
                tags = [tags] if tags else []
            status = meta.get("status", "active")
            summary = meta.get("summary", "") or get_summary(content)
            preview = get_preview(content)
            rel_path = f.relative_to(LESSONS_DIR).as_posix()
            # Check for Verification section (badge-only verified semantics)
            verified = bool(re.search(r"##\s*(Verify|Verification)", content, re.IGNORECASE))
            # Evidence level (#786): frontmatter wins when present; legacy
            # lessons that predate the field get a content-inferred level
            # (same inference the intake pipeline uses — queue_lesson.py).
            # The public index carries it so search pages can show E3+/E4
            # counts instead of composite averages.
            raw_level = meta.get("evidence_level")
            if raw_level is not None:
                evidence_level = evidence_of(meta)
                evidence_source = "frontmatter"
            else:
                from scripts.infer_evidence_level import infer_evidence_level
                evidence_level, _ = infer_evidence_level(content)
                evidence_source = "inferred"
            confidence = meta.get("confidence", 0.5)
            if not isinstance(confidence, (int, float)):
                confidence = 0.5
            evidence_refs = meta.get("evidence_refs", [])
            if not isinstance(evidence_refs, list):
                evidence_refs = [evidence_refs] if evidence_refs else []

            entries.append({
                "id": f.stem,
                "title": title,
                "domain": domain,
                "tags": tags,
                "summary": summary,
                "preview": preview,
                "url": f"lessons/{rel_path}",
                "created": meta.get("created", ""),
                "updated": meta.get("updated", ""),
                "triggers": meta.get("triggers", None),
                "validity_period_days": 365,
                "environment_version": "",
                "confidence": confidence,
                "status": status,
                "verified": verified,
                "evidence_level": evidence_level,
                "evidence_source": evidence_source,
                "evidence_refs": evidence_refs,
                # trust = quality(confidence) scaled by evidence (E0 keeps 70%,
                # E4 keeps 100%) — shown on search pages instead of a composite.
                "trust_score": trust_score(confidence, evidence_level),
            })

    OUTPUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK lessons.json updated: {len(entries)} entries")


if __name__ == "__main__":
    main()
