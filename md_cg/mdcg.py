import json, os, time, logging
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class MdCG:
    """Markdown Cognitive Graph store.

    Architecture note — **read this before hacking files on disk**:
      * ``<root>/<layer>/<id>.md``  — source of truth (node files you may edit)
      * ``<root>/_index.json``     — derived snapshot consumed by every reader
      * ``<root>/_index_log/``     — append-only journal for durability

    The index is a **derived artifact**; the node .md is the single source of
    truth and ``_index.json`` can be rebuilt at any time by ``rebuild_index()``.
    Readers NEVER scan the directory tree on open — they load the snapshot.
    Hand-editing a node file will not be visible until after a rebuild.
    """

    INDEX_NAME = "_index.json"
    LOG_DIR_NAME = "_index_log"

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.index_path = self.root / self.INDEX_NAME
        self.log_path = self.root / self.LOG_DIR_NAME
        self._index: Dict[str, Any] = {}
        self._loaded = False
        self._open_files: set = set()

        self.log_path.mkdir(parents=True, exist_ok=True)
        self._load_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rebuild_index(self) -> int:
        """Rebuild ``_index.json`` from all ``*.md`` nodes on disk.

        Returns the number of nodes re-indexed.  Call this after any manual
        edit/add/delete of node files so that readers see the new state.
        """
        nodes: Dict[str, Any] = {}
        for md_file in self.root.rglob("*.md"):
            # skip our own metadata files
            if md_file.name in (self.INDEX_NAME,):
                continue
            rel = md_file.relative_to(self.root)
            key = str(rel).replace("\\", "/")
            try:
                content = md_file.read_text(encoding="utf-8")
                frontmatter, body = self._split_frontmatter(content)
                nodes[key] = {
                    "path": key,
                    "mtime_ns": md_file.stat().st_mtime_ns,
                    "size": md_file.stat().st_size,
                    "frontmatter": frontmatter,
                    "body": body,
                }
            except Exception as exc:
                logger.warning("Skipped %s: %r", md_file, exc)

        self._write_index(nodes)
        self._index = nodes
        self._loaded = True
        logger.info("Rebuilt index with %d nodes from %s", len(nodes), self.root)
        return len(nodes)

    def get_node(self, key: str) -> Optional[Dict[str, Any]]:
        """Return a node from the in-memory snapshot (the read path)."""
        return self._index.get(key)

    def list_nodes(self, layer: Optional[str] = None) -> List[Dict[str, Any]]:
        """List nodes, optionally filtered by layer prefix."""
        results = []
        for info in self._index.values():
            if layer and not info["path"].startswith(layer + "/"):
                continue
            results.append(info)
        return results

    def close(self) -> None:
        """Flush any pending journal entries and release resources."""
        self._open_files.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_index(self) -> None:
        """Load the snapshot index if it exists; start with an empty dict."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                self._loaded = True
            except Exception:
                logger.warning("Failed to load existing index at %s; starting empty.", self.index_path)
                self._index = {}
                self._loaded = False
        else:
            self._index = {}
            self._loaded = False

    def _write_index(self, nodes: Dict[str, Any]) -> None:
        """Atomically write the snapshot index via a journal entry."""
        tmp = self.index_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(nodes, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp.replace(self.index_path)
        self._persist_log(nodes)

    def _persist_log(self, nodes: Dict[str, Any]) -> None:
        ts = time.time()
        entry = {"ts": ts, "node_count": len(nodes)}
        log_file = self.log_path / f"{int(ts * 1000):013d}.json"
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(entry, f)

    @staticmethod
    def _split_frontmatter(content: str) -> tuple:
        """Parse YAML frontmatter; return (fm_dict, body_str)."""
        if content.startswith("---\n"):
            end = content.find("\n---\n", 4)
            if end != -1:
                fm_raw = content[4:end]
                body = content[end + 5:]
                return MdCG._parse_yaml(fm_raw), body
        return {}, content

    @staticmethod
    def _parse_yaml(text: str) -> Dict[str, Any]:
        """Minimal YAML frontmatter parser (no external dep required)."""
        result: Dict[str, Any] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val.lower() in ("true", "yes"):
                val = True
            elif val.lower() in ("false", "no"):
                val = False
            result[key] = val
        return result

    def __repr__(self) -> str:
        return f"MdCG(root={self.root!r}, nodes={len(self._index)})"
