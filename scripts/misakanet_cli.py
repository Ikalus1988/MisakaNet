#!/usr/bin/env python3
"""MisakaNet CLI — doctor, smoke, validate commands.

Minimal verification commands for harness integration.

Usage:
    python3 scripts/misakanet_cli.py doctor    # Health check
    python3 scripts/misakanet_cli.py smoke     # Minimal search test
    python3 scripts/misakanet_cli.py validate  # Config + index + tools check

Exit codes:
    0 = healthy / pass
    1 = degraded / fail
    2 = broken / critical error

Output: JSON (machine-readable for harness consumption)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))
VERSION = "2.17.0"


# ── doctor ────────────────────────────────────────────────────────

def cmd_doctor() -> dict:
    """Health check: data files, search engine, lessons directory."""
    checks = []

    # Check data/lessons.json
    lessons_json = REPO_ROOT / "data" / "lessons.json"
    if lessons_json.exists():
        try:
            data = json.loads(lessons_json.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, list) else 0
            checks.append({"name": "lessons.json", "status": "ok", "count": count})
        except Exception as e:
            checks.append({"name": "lessons.json", "status": "error", "error": str(e)})
    else:
        checks.append({"name": "lessons.json", "status": "missing"})

    # Check data/sag.db
    sag_db = REPO_ROOT / "data" / "sag.db"
    checks.append({
        "name": "sag.db",
        "status": "ok" if sag_db.exists() else "missing",
    })

    # Check lessons/ directory
    lessons_dir = REPO_ROOT / "lessons"
    if lessons_dir.exists():
        md_count = len(list(lessons_dir.rglob("*.md")))
        checks.append({"name": "lessons/", "status": "ok" if md_count > 0 else "empty", "count": md_count})
    else:
        checks.append({"name": "lessons/", "status": "missing"})

    # Check search engine
    engine = "none"
    try:
        from misakanet.search.engine import LESSONS
        engine = "bm25"
    except ImportError:
        pass
    if engine == "none" and sag_db.exists():
        engine = "sag-lite"
    checks.append({"name": "search_engine", "status": engine})

    # Overall
    failures = [c for c in checks if c["status"] in ("missing", "empty", "error")]
    overall = "healthy" if not failures else "degraded"

    return {
        "command": "doctor",
        "version": VERSION,
        "overall": overall,
        "checks": checks,
    }


# ── smoke ─────────────────────────────────────────────────────────

def cmd_smoke() -> dict:
    """Minimal smoke test: search + lesson fetch."""
    results = {}
    start = time.time()

    # Test 1: Search
    try:
        from mcp_server import handle_search
        search_result = handle_search({"query": "DCO", "top": 3})
        has_results = "results" in search_result and len(search_result.get("results", [])) > 0
        results["search"] = {
            "status": "ok" if has_results else "empty",
            "result_count": len(search_result.get("results", [])),
            "source": search_result.get("source", "unknown"),
        }
    except Exception as e:
        results["search"] = {"status": "fail", "error": str(e)}

    # Test 2: Get lesson (find one that exists)
    if results["search"].get("status") == "ok" and results["search"]["result_count"] > 0:
        try:
            from mcp_server import handle_get_lesson
            # Try each result until we find one that exists
            for item in search_result["results"]:
                lesson_path = item.get("path", "")
                if not lesson_path:
                    continue
                lesson_result = handle_get_lesson({"path": lesson_path})
                if "content" in lesson_result and lesson_result["content"]:
                    results["get_lesson"] = {
                        "status": "ok",
                        "content_length": len(lesson_result["content"]),
                        "path": lesson_path,
                    }
                    break
            else:
                results["get_lesson"] = {"status": "skip", "reason": "no valid lesson found"}
        except Exception as e:
            results["get_lesson"] = {"status": "fail", "error": str(e)}
    else:
        results["get_lesson"] = {"status": "skip", "reason": "search failed or empty"}

    elapsed = time.time() - start
    all_ok = all(r.get("status") in ("ok", "skip") for r in results.values())

    return {
        "command": "smoke",
        "version": VERSION,
        "overall": "pass" if all_ok else "fail",
        "elapsed_ms": round(elapsed * 1000),
        "tests": results,
    }


# ── validate ──────────────────────────────────────────────────────

def cmd_validate() -> dict:
    """Validate config, index, and tool availability."""
    checks = []

    # Check MCP server is importable
    try:
        from mcp_server import TOOLS, handle_search, handle_get_lesson
        checks.append({
            "name": "mcp_server",
            "status": "ok",
            "tool_count": len(TOOLS),
            "tools": [t["name"] for t in TOOLS],
        })
    except Exception as e:
        checks.append({"name": "mcp_server", "status": "fail", "error": str(e)})

    # Check adapter is importable
    try:
        from mcp_deepseek_adapter import TOOLS as ADAPTER_TOOLS
        checks.append({
            "name": "deepseek_adapter",
            "status": "ok",
            "tool_count": len(ADAPTER_TOOLS),
            "tools": [t["name"] for t in ADAPTER_TOOLS],
        })
    except Exception as e:
        checks.append({"name": "deepseek_adapter", "status": "fail", "error": str(e)})

    # Check SKILL.md exists
    skill_md = REPO_ROOT / "SKILL.md"
    checks.append({
        "name": "SKILL.md",
        "status": "ok" if skill_md.exists() else "missing",
    })

    # Check pyproject.toml version
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        import re
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            checks.append({
                "name": "pyproject.version",
                "status": "ok",
                "value": match.group(1),
            })
        else:
            checks.append({"name": "pyproject.version", "status": "missing"})
    else:
        checks.append({"name": "pyproject.toml", "status": "missing"})

    # Overall
    failures = [c for c in checks if c["status"] in ("fail", "missing")]
    overall = "pass" if not failures else "fail"

    return {
        "command": "validate",
        "version": VERSION,
        "overall": overall,
        "checks": checks,
    }


# ── CLI ───────────────────────────────────────────────────────────

COMMANDS = {
    "doctor": cmd_doctor,
    "smoke": cmd_smoke,
    "validate": cmd_validate,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(json.dumps({
            "error": "usage: misakanet_cli.py <doctor|smoke|validate>",
            "commands": list(COMMANDS.keys()),
        }))
        sys.exit(2)

    command = sys.argv[1]
    result = COMMANDS[command]()

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Exit code based on overall status
    overall = result.get("overall", "")
    if overall in ("healthy", "pass"):
        sys.exit(0)
    elif overall in ("degraded", "fail"):
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
