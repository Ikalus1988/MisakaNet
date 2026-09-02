"""Shared configuration and lazy search engine imports for MCP server."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _init_search():
    """Lazy-init search backends. Returns (HAS_SAG, SAG_DB, HAS_BM25, sag_search)."""

    sag_search = None
    SAG_DB = REPO_ROOT / "data" / "sag.db"  # noqa: N806
    HAS_SAG = False  # noqa: N806

    try:
        from scripts.build_sag_index import search as _sag_search
        sag_search = _sag_search
        HAS_SAG = SAG_DB.exists()  # noqa: N806
    except ImportError:
        pass

    HAS_BM25 = False  # noqa: N806
    try:
        from misakanet.search.engine import (  # noqa: F401
            LESSONS,
            _load_docs_cached,
            _search_cached,
        )
        HAS_BM25 = True  # noqa: N806
    except ImportError:
        pass

    return HAS_SAG, SAG_DB, HAS_BM25, sag_search


def get_server_version() -> str:
    """Return the installed or checkout package version for MCP metadata."""
    import re
    from importlib import metadata

    try:
        return metadata.version("misakanet")
    except metadata.PackageNotFoundError:
        pyproject = REPO_ROOT / "pyproject.toml"
        if pyproject.exists():
            match = re.search(
                r'^version\s*=\s*["\']([^"\']+)["\']',
                pyproject.read_text(encoding="utf-8", errors="replace"),
                re.MULTILINE,
            )
            if match:
                return match.group(1)
    return "0.0.0"
