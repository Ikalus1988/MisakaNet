#!/usr/bin/env python3
"""hub/analytics/failure_map.py — Privacy-preserving unsolved failure map (closes #788)

Aggregates crash tombstones and search miss data into anonymized failure families.
Never exposes raw queries, prompts, logs, or secrets. Only anonymized counts.
"""
import json
import hashlib
import time
from pathlib import Path
from collections import defaultdict

FAILURE_MAP_FILE = Path(__file__).parent / "failure_map.json"
TOMBSTONE_DIR = Path(__file__).parent.parent / "data" / "tombstones"

class FailureMap:
    def __init__(self):
        self.families = defaultdict(lambda: {"unsolved_count": 0, "reasons": set(), "last_seen": None})
        self._load()

    def _load(self):
        if FAILURE_MAP_FILE.exists():
            data = json.loads(FAILURE_MAP_FILE.read_text())
            for k, v in data.items():
                self.families[k]["unsolved_count"] = v.get("unsolved_count", 0)
                self.families[k]["reasons"] = set(v.get("reasons", []))
                self.families[k]["last_seen"] = v.get("last_seen")

    def _save(self):
        out = {}
        for family, info in self.families.items():
            out[family] = {
                "unsolved_count": info["unsolved_count"],
                "reasons": sorted(info["reasons"]),
                "last_seen": info["last_seen"]
            }
        FAILURE_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        FAILURE_MAP_FILE.write_text(json.dumps(out, indent=2))

    def _classify(self, error_message):
        """Classify an error message into a failure family — anonymized, no raw logs."""
        msg = (error_message or "").lower()
        families = {
            "sqlite-database-locked": ["sqlite", "database locked", "database is locked"],
            "pip-install-timeout": ["pip install", "timeout", "connection refused"],
            "github-token-401": ["401", "bad credentials", "token", "unauthorized"],
            "mcp-path-error": ["mcp", "server path", "command not found"],
            "windows-encoding-gbk": ["gbk", "codec can't decode", "chardetect", "encoding"],
            "import-error": ["modulenotfound", "importerror", "cannot import"],
            "json-schema-validation": ["json schema", "validation", "does not match"],
            "cloudflare-deploy": ["cloudflare", "deploy failed", "pages"],
            "git-merge-conflict": ["merge conflict", "conflict", "unmerged"],
            "network-timeout": ["timeout", "econnrefused", "econnreset", "network"],
            "out-of-memory": ["out of memory", "cannot allocate", "memoryerror"],
            "node-version-mismatch": ["node version", "nvm", "engines"],
            "docker-build-failure": ["docker", "build failed", "cannot build"],
        }
        for family, keywords in families.items():
            if any(kw in msg for kw in keywords):
                return family
        return "unknown"

    def ingest_tombstone(self, error_message, reason="crash", node_id=None):
        """Ingest a crash tombstone — stores only anonymized family counts."""
        family = self._classify(error_message)
        self.families[family]["unsolved_count"] += 1
        self.families[family]["reasons"].add(reason)
        self.families[family]["last_seen"] = time.strftime("%Y-%m-%d")
        self._save()
        return {"family": family, "action": "aggregated"}

    def ingest_search_miss(self, query_family, count=1):
        """Ingest a search miss (no matching lesson found)."""
        family = self._classify(query_family)
        self.families[family]["unsolved_count"] += count
        self.families[family]["reasons"].add("no_match")
        self.families[family]["last_seen"] = time.strftime("%Y-%m-%d")
        self._save()

    def get_map(self, domain=None, min_count=0):
        """Get the failure map — sorted by unsolved count, privacy-preserving."""
        results = []
        for family, info in self.families.items():
            if info["unsolved_count"] < min_count:
                continue
            if domain and domain not in family:
                continue
            results.append({
                "task_family": family,
                "unsolved_count": info["unsolved_count"],
                "reasons": sorted(info["reasons"]),
                "last_seen": info["last_seen"]
            })
        results.sort(key=lambda x: x["unsolved_count"], reverse=True)
        return results

    def get_summary(self):
        """Privacy-preserving summary — no individual data exposed."""
        all_families = self.get_map()
        return {
            "total_failure_families": len(all_families),
            "total_unsolved": sum(f["unsolved_count"] for f in all_families),
            "top_families": all_families[:10],
            "has_unknown": any(f["task_family"] == "unknown" for f in all_families),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

# CLI
if __name__ == "__main__":
    import sys
    fm = FailureMap()

    if len(sys.argv) < 2:
        summary = fm.get_summary()
        print(json.dumps(summary, indent=2))
    elif sys.argv[1] == "ingest":
        error = sys.argv[2] if len(sys.argv) > 2 else "unknown error"
        result = fm.ingest_tombstone(error)
        print(json.dumps(result))
    elif sys.argv[1] == "list":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        results = fm.get_map(domain=domain)
        print(json.dumps(results, indent=2))
    elif sys.argv[1] == "search-miss":
        query = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        fm.ingest_search_miss(query)
        print(json.dumps({"status": "recorded"}))
