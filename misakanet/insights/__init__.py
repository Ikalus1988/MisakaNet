"""
Insights module — aggregate analytics for MisakaNet.

Public: GET /api/insights/demand-board
Private: GET /api/insights/demand-map (requires maintainer key)
"""
from __future__ import annotations

import json
import hashlib
import hmac
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Task family whitelist (from #591)
TASK_FAMILIES = [
    "github-auth",
    "npm-publish",
    "cloudflare-worker",
    "mcp-registry",
    "glama-release",
    "python-env",
    "database-lock",
    "crawler-block",
    "agent-tooling",
    "unclassified",
]


def classify_task_family(query: str, lesson_id: str = "") -> str:
    """Simple keyword-based classifier for task families."""
    q = (query + " " + lesson_id).lower()

    keywords = {
        "github-auth": ["github", "auth", "token", "oauth", "git credential"],
        "npm-publish": ["npm", "publish", "package", "node"],
        "cloudflare-worker": ["cloudflare", "worker", "wrangler", "cf"],
        "mcp-registry": ["mcp", "registry", "server", "tool"],
        "glama-release": ["glama", "release", "gateway"],
        "python-env": ["python", "pip", "venv", "conda", "pyenv", "virtualenv"],
        "database-lock": ["database", "deadlock", "sql", "mysql", "postgres", "transaction"],
        "crawler-block": ["crawl", "scrape", "403", "429", "bot detect"],
        "agent-tooling": ["agent", "langchain", "skill plugin", "tool call"],
    }

    for family, terms in keywords.items():
        if any(t in q for t in terms):
            return family

    return "unclassified"


class DemandBoard:
    """Aggregate unsolved failure families into task-family counts."""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("./data/insights")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.intake_file = self.data_dir / "intake.jsonl"
        self.feedback_file = self.data_dir / "feedback.jsonl"

    def _read_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def _append_jsonl(self, path: Path, record: dict) -> None:
        with open(path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def record_intake(self, source: str, message: str, context: Optional[dict] = None) -> None:
        """Record an intake event (from /api/intake)."""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "message": message[:500],
            "context": context or {},
        }
        self._append_jsonl(self.intake_file, record)

    def record_feedback(
        self, query: str, lesson_id: str, feedback: str, ts: Optional[str] = None
    ) -> None:
        """Record a search feedback event."""
        record = {
            "ts": ts or datetime.now(timezone.utc).isoformat(),
            "query": query[:200],
            "lesson_id": lesson_id[:200],
            "feedback": feedback,
        }
        self._append_jsonl(self.feedback_file, record)

    def get_demand_board(self, window_days: int = 30) -> dict:
        """
        Build the public demand board.

        Returns aggregate-only JSON with no raw queries or PII.
        """
        cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)
        cutoff_30d = datetime.now(timezone.utc) - timedelta(days=window_days)

        family_counts_7d: dict[str, int] = defaultdict(int)
        family_counts_30d: dict[str, int] = defaultdict(int)
        family_last_seen: dict[str, str] = {}

        # Process feedback records (irrelevant / too_basic = unsolved)
        for rec in self._read_jsonl(self.feedback_file):
            try:
                ts = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue

            feedback = rec.get("feedback", "")
            if feedback not in ("irrelevant", "too_basic"):
                continue

            family = classify_task_family(rec.get("query", ""), rec.get("lesson_id", ""))
            if ts >= cutoff_30d:
                family_counts_30d[family] += 1
                if ts >= cutoff_7d:
                    family_counts_7d[family] += 1

                last = family_last_seen.get(family, "")
                if not last or ts.isoformat() > last:
                    family_last_seen[family] = ts.strftime("%Y-%m-%d")

        # Process intake records
        for rec in self._read_jsonl(self.intake_file):
            try:
                ts = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue

            family = classify_task_family(rec.get("message", ""))
            if ts >= cutoff_30d:
                family_counts_30d[family] += 1
                if ts >= cutoff_7d:
                    family_counts_7d[family] += 1

                last = family_last_seen.get(family, "")
                if not last or ts.isoformat() > last:
                    family_last_seen[family] = ts.strftime("%Y-%m-%d")

        # Build summary, sorted by 30d count descending
        summary = []
        for family in sorted(family_counts_30d, key=lambda f: family_counts_30d[f], reverse=True):
            summary.append(
                {
                    "taskFamily": family,
                    "unsolved7d": family_counts_7d.get(family, 0),
                    "unsolved30d": family_counts_30d[family],
                    "lastSeen": family_last_seen.get(family, ""),
                    "actionUrl": (
                        "https://github.com/Ikalus1988/MisakaNet/issues/new"
                        "?template=lesson-feedback.yml"
                    ),
                }
            )

        return {
            "success": True,
            "available": len(summary) > 0,
            "windowDays": window_days,
            "summary": summary,
            "meta": {
                "r_level": "R1_descriptive",
                "privacy": "aggregate-only",
                "raw_query": False,
                "pii": False,
            },
        }

    def get_demand_map(self, maintainer_key: str) -> dict:
        """
        Build the private/maintainer demand map.

        Requires valid maintainer key for access.
        """
        if not self._verify_maintainer_key(maintainer_key):
            return {"error": "Invalid maintainer key"}

        cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)
        buckets: dict[tuple, dict] = {}

        # Process feedback
        for rec in self._read_jsonl(self.feedback_file):
            try:
                ts = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue

            if ts < cutoff_30d:
                continue

            feedback = rec.get("feedback", "")
            if feedback not in ("irrelevant", "too_basic"):
                continue

            family = classify_task_family(rec.get("query", ""), rec.get("lesson_id", ""))
            day = ts.strftime("%Y-%m-%d")
            reason = f"feedback:{feedback}"
            key = (family, day, reason)

            if key not in buckets:
                buckets[key] = {"unsolvedCount": 0, "distinctSources": set()}
            buckets[key]["unsolvedCount"] += 1
            buckets[key]["distinctSources"].add(rec.get("lesson_id", ""))

        # Process intake
        for rec in self._read_jsonl(self.intake_file):
            try:
                ts = datetime.fromisoformat(rec["ts"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                continue

            if ts < cutoff_30d:
                continue

            family = classify_task_family(rec.get("message", ""))
            day = ts.strftime("%Y-%m-%d")
            reason = rec.get("source", "intake")
            key = (family, day, reason)

            if key not in buckets:
                buckets[key] = {"unsolvedCount": 0, "distinctSources": set()}
            buckets[key]["unsolvedCount"] += 1
            buckets[key]["distinctSources"].add(rec.get("message", "")[:50])

        result_buckets = []
        for (family, day, reason), data in sorted(buckets.items()):
            result_buckets.append(
                {
                    "taskFamily": family,
                    "bucketDay": day,
                    "unsolvedReason": reason,
                    "unsolvedCount": data["unsolvedCount"],
                    "distinctSourceCount": len(data["distinctSources"]),
                }
            )

        return {"buckets": result_buckets}

    @staticmethod
    def _verify_maintainer_key(key: str) -> bool:
        expected = os.environ.get("MAINTAINER_KEY", "")
        if not expected:
            return False
        return hmac.compare_digest(key, expected)


# Module-level singleton for Cloudflare Worker compatibility
_demand_board: Optional[DemandBoard] = None


def get_demand_board() -> DemandBoard:
    global _demand_board
    if _demand_board is None:
        _demand_board = DemandBoard()
    return _demand_board
