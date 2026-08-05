"""
Subscription Manager - v3.0 订阅匹配系统
节点按领域订阅，Hub 精准推送而非广播
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class Subscription:
    """节点订阅"""
    id: int
    agent_id: str
    domain: str
    created_at: str
    active: bool = True


class SubscriptionManager:
    """
    订阅管理器
    - 节点订阅特定领域
    - 推送时匹配订阅者而非广播
    """

    def __init__(self, db_path: str = "./storage/subscriptions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化订阅数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                UNIQUE(agent_id, domain)
            )
        """)
        conn.commit()
        conn.close()

    def subscribe(self, agent_id: str, domain: str) -> bool:
        """订阅领域"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO subscriptions (agent_id, domain, created_at, active)
                VALUES (?, ?, ?, 1)
            """, (agent_id, domain, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            print(f"[Subscription] {agent_id} 订阅了 {domain}")
            return True
        except Exception as e:
            conn.close()
            return False

    def unsubscribe(self, agent_id: str, domain: str) -> bool:
        """取消订阅"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE subscriptions SET active = 0 WHERE agent_id = ? AND domain = ?
        """, (agent_id, domain))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_subscribers(self, domain: str) -> list[str]:
        """获取某领域的所有订阅者"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT agent_id FROM subscriptions
            WHERE domain = ? AND active = 1
        """, (domain,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_subscriptions(self, agent_id: str) -> list[str]:
        """获取某节点的所有订阅领域"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT domain FROM subscriptions
            WHERE agent_id = ? AND active = 1
        """, (agent_id,))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def get_all_subscriptions(self) -> list[Subscription]:
        """获取所有订阅记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.cursor()
        cursor.execute("""
            SELECT id, agent_id, domain, created_at, active FROM subscriptions
            WHERE active = 1 ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            Subscription(id=row[0], agent_id=row[1], domain=row[2],
                        created_at=row[3], active=bool(row[4]))
            for row in rows
        ]

    def match_subscribers(self, skill_domain: str) -> list[str]:
        """
        匹配订阅者
        支持通配符 * (全部订阅)
        """
        subscribers = self.get_subscribers(skill_domain)
        # 也加入通配订阅者
        wildcard_subscribers = self.get_subscribers("*")
        return list(set(subscribers + wildcard_subscribers))

    def stats(self) -> dict:
        """获取订阅统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM subscriptions WHERE active = 1
        """)
        total = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(DISTINCT agent_id) FROM subscriptions WHERE active = 1
        """)
        agents = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(DISTINCT domain) FROM subscriptions WHERE active = 1
        """)
        domains = cursor.fetchone()[0]
        conn.close()
        return {"total": total, "agents": agents, "domains": domains}
