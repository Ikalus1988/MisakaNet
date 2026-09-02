"""MCP Resources for MisakaNet server."""
from __future__ import annotations

import json

from ._config import REPO_ROOT

RESOURCES = [
    {
        "uri": "misaka://lessons/index",
        "name": "Lessons Index",
        "description": "Browse all published lessons (core + contrib) with metadata",
        "mimeType": "application/json",
    },
    {
        "uri": "misaka://protocol/overview",
        "name": "Protocol Overview",
        "description": (
            "failure-memory protocol configuration (trust tiers, rings, scoring)"
        ),
        "mimeType": "application/json",
    },
    {
        "uri": "misaka://docs/readme",
        "name": "README",
        "description": "Project overview, quickstart, and integration guide",
        "mimeType": "text/markdown",
    },
    {
        "uri": "misaka://docs/faq",
        "name": "Troubleshooting FAQ",
        "description": "Common issues and solutions for MisakaNet users",
        "mimeType": "text/markdown",
    },
    {
        "uri": "misaka://docs/changelog",
        "name": "Changelog",
        "description": "Latest release notes and version history",
        "mimeType": "text/markdown",
    },
    {
        "uri": "misakanet://lessons/{id}",
        "name": "Lesson by ID",
        "description": "Full lesson content and metadata by lesson ID",
        "mimeType": "application/json",
    },
    {
        "uri": "misakanet://domains",
        "name": "Domain List",
        "description": "List all knowledge domains with lesson counts",
        "mimeType": "application/json",
    },
]


def handle_resources_list() -> list:
    """Return available resources."""
    return RESOURCES


def handle_resources_read(uri: str) -> dict:
    """Read a resource by URI."""
    if uri == "misaka://lessons/index":
        lessons = []
        for subdir in ["core", "contrib"]:
            d = REPO_ROOT / "lessons" / subdir
            if d.exists():
                for f in sorted(d.glob("*.md")):
                    lessons.append({
                        "id": f.stem,
                        "path": str(f.relative_to(REPO_ROOT)),
                        "category": subdir,
                    })
        return {"lessons": lessons, "count": len(lessons)}

    elif uri == "misaka://protocol/overview":
        p = REPO_ROOT / "misaka-protocol.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return {"error": "misaka-protocol.json not found"}

    elif uri == "misaka://docs/readme":
        p = REPO_ROOT / "README.md"
        if p.exists():
            return {
                "content": p.read_text(
                    encoding="utf-8", errors="replace"
                )[:8000]
            }
        return {"error": "README.md not found"}

    elif uri == "misaka://docs/faq":
        p = REPO_ROOT / "docs" / "troubleshooting.md"
        if p.exists():
            return {
                "content": p.read_text(
                    encoding="utf-8", errors="replace"
                )[:8000]
            }
        return {"error": "troubleshooting.md not found"}

    elif uri == "misaka://docs/changelog":
        p = REPO_ROOT / "CHANGELOG.md"
        if p.exists():
            return {
                "content": p.read_text(
                    encoding="utf-8", errors="replace"
                )[:8000]
            }
        return {"error": "CHANGELOG.md not found"}

    elif uri.startswith("misakanet://lessons/"):
        lesson_id = uri.replace("misakanet://lessons/", "")
        for subdir in ["core", "contrib", "draft", "en"]:
            d = REPO_ROOT / "lessons" / subdir
            if d.exists():
                for f in d.glob("*.md"):
                    if f.stem == lesson_id:
                        content_text = f.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        return {
                            "id": f.stem,
                            "path": str(f.relative_to(REPO_ROOT)),
                            "title": (
                                content_text.split("\n")[0]
                                .replace("# ", "")
                                .strip()
                            ),
                            "domain": subdir,
                            "content": content_text[:8000],
                            "word_count": len(content_text.split()),
                        }
        return {"error": f"Lesson not found: {lesson_id}"}

    elif uri == "misakanet://domains":
        from collections import Counter

        domain_counts = Counter()
        for subdir in ["core", "contrib", "draft", "en"]:
            d = REPO_ROOT / "lessons" / subdir
            if d.exists():
                for f in d.glob("*.md"):
                    content_text = f.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    domain = subdir
                    if "domain:" in content_text[:500]:
                        for line in content_text[:500].split("\n"):
                            if line.strip().startswith("domain:"):
                                domain = line.split(":", 1)[1].strip()
                    domain_counts[domain] += 1
        return [
            {"name": d, "lesson_count": c}
            for d, c in sorted(domain_counts.items())
        ]

    return {"error": f"Unknown resource: {uri}"}
