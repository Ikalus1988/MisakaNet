"""Pull-only answer/receipt inbox for anonymous MCP clients.

Only a problem digest and the caller's stable client/node key are retained.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from typing import Any


def _digest(problem: str) -> str:
    return hashlib.sha256(problem.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IntakeResult:
    answered: bool
    answer: str | None
    problem_key: str
    client_id: str
    pull_instruction: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "answered": self.answered,
            "answer": self.answer,
            "problem_key": self.problem_key,
            "client_id": self.client_id,
            "pull_instruction": self.pull_instruction,
        }


class Inbox:
    """SQLite-backed implementation of submit and pull operations.

    ``client_id`` is caller supplied and must be stable. ``agent_type`` is
    deliberately not accepted as an identity key.
    """

    def __init__(self, database: str = ":memory:") -> None:
        self.db = sqlite3.connect(database)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL, problem_key TEXT NOT NULL,
            status TEXT NOT NULL, answer TEXT, issue TEXT, lesson TEXT,
            evidence_level TEXT NOT NULL DEFAULT 'unverified',
            UNIQUE(client_id, problem_key, status)
        )""")
        self.db.commit()

    def submit_intake(self, problem: str, client_id: str) -> dict[str, Any]:
        if not problem.strip():
            raise ValueError("problem must not be empty")
        if not client_id.strip():
            raise ValueError("client_id must not be empty")
        key = _digest(problem)
        row = self.db.execute(
            "SELECT answer FROM events WHERE client_id=? AND problem_key=? AND status='answered'",
            (client_id, key),
        ).fetchone()
        result = IntakeResult(bool(row), row["answer"] if row else None, key, client_id,
            f"This is pull-only: call misakanet_me_events with client_id={client_id!r} "
            f"and problem_key={key!r} later to retrieve an answer or receipt.")
        if not row:
            self.db.execute("INSERT OR IGNORE INTO events(client_id, problem_key, status) VALUES(?,?, 'pending')",
                            (client_id, key))
            self.db.commit()
        return result.as_dict()

    def record_answer(self, client_id: str, problem: str | None = None,
                      problem_key: str | None = None, *, answer: str,
                      issue: str | None = None, lesson: str | None = None,
                      evidence_level: str = "reported") -> None:
        key = problem_key or (_digest(problem) if problem is not None else None)
        if not key:
            raise ValueError("problem_key or problem is required")
        self.db.execute("DELETE FROM events WHERE client_id=? AND problem_key=? AND status='pending'",
                        (client_id, key))
        self.db.execute("INSERT OR REPLACE INTO events(client_id, problem_key, status, answer, issue, lesson, evidence_level) VALUES(?,?, 'answered',?,?,?,?)",
                        (client_id, key, answer, issue, lesson, evidence_level))
        self.db.commit()

    def record_resolution(self, client_id: str, problem_key: str, *, issue: str,
                          lesson: str, evidence_level: str = "reported") -> None:
        self.db.execute("INSERT OR REPLACE INTO events(client_id, problem_key, status, issue, lesson, evidence_level) VALUES(?,?, 'resolved',?,?,?)",
                        (client_id, problem_key, issue, lesson, evidence_level))
        self.db.commit()

    def me_events(self, client_id: str, problem_key: str | None = None) -> dict[str, Any]:
        params: list[Any] = [client_id]
        query = "SELECT * FROM events WHERE client_id=? AND status IN ('answered','resolved')"
        if problem_key:
            query += " AND problem_key=?"
            params.append(problem_key)
        rows = self.db.execute(query + " ORDER BY id", params).fetchall()
        events = []
        for r in rows:
            item = {"problem_key": r["problem_key"], "evidence_level": r["evidence_level"]}
            if r["status"] == "answered":
                item.update(answered=True, answer=r["answer"], issue=r["issue"], lesson=r["lesson"])
            else:
                item.update(resolved=True, issue=r["issue"], lesson=r["lesson"])
            events.append(item)
        return {"client_id": client_id, "events": events,
                "status": "available" if events else "no_answer_yet",
                "message": "No answer yet; this pull-only inbox has no matching answer or receipt." if not events else None}
