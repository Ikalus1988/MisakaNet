"""
Arbitration Queue - v3.0 矛盾仲裁队列
当多个节点对同一 Skill 有不同版本时，进入仲裁队列等待用户决策
"""
import json
import sqlite3
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ArbitrationCase:
    """单个仲裁案例"""
    id: str
    skill_id: str
    skill_name: str
    versions: list  # 各节点提交的版本
    status: str  # pending / resolved / expired
    created_at: str
    resolved_at: Optional[str] = None
    winner_id: Optional[str] = None
    notes: Optional[str] = None


class ArbitrationQueue:
    """
    矛盾仲裁队列
    - 检测到冲突版本时创建案例
    - 通过飞书通知用户
    - 用户回复后执行仲裁
    """

    def __init__(self, db_path: str = "./storage/arbitration.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 仲裁数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arbitration_cases (
                id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                skill_name TEXT,
                versions TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                winner_id TEXT,
                notes TEXT
            )
        """)
        conn.commit()
        conn.close()

    def create_case(self, skill_id: str, skill_name: str, versions: list) -> ArbitrationCase:
        """
        创建仲裁案例
        当检测到同一 skill_id 有多个冲突版本时调用
        """
        case_id = f"ARB-{skill_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        case = ArbitrationCase(
            id=case_id,
            skill_id=skill_id,
            skill_name=skill_name,
            versions=versions,
            status="pending",
            created_at=datetime.now().isoformat()
        )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO arbitration_cases
            (id, skill_id, skill_name, versions, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            case.id,
            case.skill_id,
            case.skill_name,
            json.dumps(versions, ensure_ascii=False),
            case.status,
            case.created_at
        ))
        conn.commit()
        conn.close()

        print(f"[Arbitration] 案例创建: {case_id} - {skill_name} ({len(versions)} 个版本)")
        return case

    def get_pending_cases(self) -> list[ArbitrationCase]:
        """获取所有待仲裁案例"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, skill_id, skill_name, versions, status, created_at, resolved_at, winner_id, notes
            FROM arbitration_cases
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()

        cases = []
        for row in rows:
            cases.append(ArbitrationCase(
                id=row[0],
                skill_id=row[1],
                skill_name=row[2],
                versions=json.loads(row[3]),
                status=row[4],
                created_at=row[5],
                resolved_at=row[6],
                winner_id=row[7],
                notes=row[8]
            ))
        return cases

    def resolve_case(self, case_id: str, winner_id: str, notes: str = "") -> bool:
        """
        解决仲裁案例
        winner_id: 用户选择的胜出版本 ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE arbitration_cases
            SET status = 'resolved',
                resolved_at = ?,
                winner_id = ?,
                notes = ?
            WHERE id = ? AND status = 'pending'
        """, (datetime.now().isoformat(), winner_id, notes, case_id))

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        if affected > 0:
            print(f"[Arbitration] 案例已解决: {case_id} - 胜出: {winner_id}")
            return True
        return False

    def get_case(self, case_id: str) -> Optional[ArbitrationCase]:
        """根据 ID 获取案例"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, skill_id, skill_name, versions, status, created_at, resolved_at, winner_id, notes
            FROM arbitration_cases WHERE id = ?
        """, (case_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return ArbitrationCase(
                id=row[0],
                skill_id=row[1],
                skill_name=row[2],
                versions=json.loads(row[3]),
                status=row[4],
                created_at=row[5],
                resolved_at=row[6],
                winner_id=row[7],
                notes=row[8]
            )
        return None

    def format_for_feishu(self, case: ArbitrationCase) -> dict:
        """
        格式化仲裁案例为飞书卡片消息
        返回飞书消息结构
        """
        versions_text = "\n".join([
            f"• **v{i+1}**: {v.get('description', v.get('name', ''))[:50]}... (来源: {v.get('source', 'unknown')})"
            for i, v in enumerate(case.versions)
        ])

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"⚖️ 仲裁请求: {case.skill_name}"},
                    "template": "red"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"**Skill ID**: `{case.skill_id}`\n\n**候选版本**:\n{versions_text}"
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "markdown",
                        "content": "请回复 `选择 [v1/v2/v3]` 或 `保留 [版本ID]` 来仲裁"
                    }
                ]
            }
        }

    def stats(self) -> dict:
        """获取仲裁统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT status, COUNT(*) FROM arbitration_cases GROUP BY status
        """)
        rows = cursor.fetchall()
        conn.close()

        stats = {"pending": 0, "resolved": 0, "expired": 0}
        for status, count in rows:
            stats[status] = count
        return stats
