"""Get lesson handler for MisakaNet MCP server."""
from __future__ import annotations

from .._config import REPO_ROOT


def handle_get_lesson(args: dict) -> dict:
    """Get a lesson by path or ID."""
    path_or_id = args.get("path", args.get("id", ""))
    if not path_or_id:
        return {
            "error": "path or id is required",
            "hint": (
                'Try: {"path": "lessons/core/welcome.md"}'
                ' or {"id": "welcome"}'
            ),
            "examples": [
                '{"path": "lessons/core/async-python.md"}',
                '{"id": "async-python"}',
            ],
            "guidance": (
                "Provide a lesson path"
                " (e.g. 'lessons/core/auto-merge-ci-pipeline.md')"
                " or lesson ID. Use misakanet_search first to"
                " discover available lessons."
            ),
            "voice": "failure-warning",
        }

    # Helper: check if path is within allowed lessons directory
    def _is_allowed_lesson_path(p):
        resolved = p.resolve()
        lessons_dir = (REPO_ROOT / "lessons").resolve()
        return resolved.is_relative_to(lessons_dir) and resolved.suffix == ".md"

    # Try direct path first (with traversal protection)
    lesson_path = (REPO_ROOT / path_or_id).resolve()
    if (
        lesson_path.is_relative_to(REPO_ROOT.resolve())
        and _is_allowed_lesson_path(lesson_path)
    ):
        if lesson_path.exists():
            content = lesson_path.read_text(
                encoding="utf-8", errors="replace"
            )
            return {
                "path": str(lesson_path.relative_to(REPO_ROOT)),
                "content": content[:5000],
                "voice": "connect-success",
            }

    # Fallback: try searching by ID across the canonical (deduped) lesson set
    # (audit T2.5) — mirrors/translations are reachable via explicit path above.
    from misakanet.lesson_index import canonical_lessons

    for candidate in canonical_lessons(REPO_ROOT / "lessons"):
        if candidate.stem == path_or_id and _is_allowed_lesson_path(candidate):
            lesson_path = candidate
            break

    if not lesson_path.exists() or not _is_allowed_lesson_path(lesson_path):
        return {
            "error": f"Lesson not found: {path_or_id}",
            "hint": (
                "Use misakanet_search to find available lessons by keyword"
            ),
            "suggestion": (
                'Try searching with: {"query": "'
                + path_or_id.replace("-", " ")
                + '"}'
            ),
            "guidance": (
                "Use misakanet_search with a related keyword to discover"
                " available lessons."
            ),
            "voice": "failure-warning",
        }

    content = lesson_path.read_text(encoding="utf-8", errors="replace")
    return {
        "path": str(lesson_path.relative_to(REPO_ROOT)),
        "content": content[:5000],  # Truncate for MCP context window
        "voice": "connect-success",
    }
