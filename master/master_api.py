"""
Master API — Hub 管理 API
供 master_cli.py 调用，控制 Hub 状态
"""
import json
import os
from datetime import datetime
from typing import Optional

from storage.knowledge_graph import KnowledgeGraph


class MasterAPI:
    """Master API — 管理 Hub 的核心操作"""

    def __init__(self, hub):
        self.hub = hub
        self.audit_logger = getattr(hub, 'audit_logger', None)

    def _a2a_available(self) -> bool:
        """检查 A2A server 是否可用（当前为死代码，始终返回 False）"""
        return False

    def require_master(self, token: str) -> bool:
        """验证 master token"""
        return self.hub.token_manager.validate_token(token)

    def get_status(self, token: str) -> dict:
        """获取 Hub 状态"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        status = {
            "agents": [],
            "hub": self.hub.get_status()
        }

        # A2A 已废弃 — Agent 注册走 GitHub Issues
        # 原代码: for agent_id, agent in self.hub.a2a_server.agents.items():

        if self.audit_logger:
            self.audit_logger.log("VIEW_STATUS", token, {"agent_count": 0})
        return status

    def add_agent(self, token: str, agent_config: dict) -> dict:
        """Add a new agent to the network (A2A 已废弃，走 GitHub Issues)"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        agent_id = agent_config.get("id")
        if not agent_id:
            return {"error": "Missing agent_id"}

        # A2A 已废弃 — 原代码: self.hub.a2a_server.register_agent(agent_card)
        # 新 Agent 注册通过 GitHub Issues + queue_lesson.py

        if self.audit_logger:
            self.audit_logger.log("ADD_AGENT", token, {"agent_id": agent_id})
        return {"status": "added (A2A disabled)", "agent_id": agent_id}

    def remove_agent(self, token: str, agent_id: str) -> dict:
        """Remove an agent from the network (A2A 已废弃)"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        # A2A 已废弃
        if self.audit_logger:
            self.audit_logger.log("REMOVE_AGENT", token, {"agent_id": agent_id})
        return {"status": "removed (A2A disabled)", "agent_id": agent_id}

    def trigger_sync(self, token: str,
                     target_agent_ids: Optional[list] = None) -> dict:
        """Manually trigger sync"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        import asyncio
        asyncio.create_task(self.hub.sync_scheduler.trigger_manual_sync())

        if self.audit_logger:
            self.audit_logger.log("TRIGGER_SYNC", token,
                                  {"targets": target_agent_ids or "all"})
        return {"status": "sync_triggered"}

    def list_skills(self, token: str) -> dict:
        """List all skills in the network"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        skills = self.hub.skill_indexer.get_all_skills()
        if self.audit_logger:
            self.audit_logger.log("LIST_SKILLS", token, {"count": len(skills)})
        return {"skills": skills, "count": len(skills)}

    def remove_skill(self, token: str, skill_id: str) -> dict:
        """Remove a skill from the network"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        # Remove from indexer
        self.hub.skill_indexer.unregister_skill(skill_id)

        # Remove from vector store (if initialized) — DEAD CODE
        # 原代码: if hasattr(self.hub, 'vector_store') and self.hub.vector_store:

        # Remove from graph
        try:
            self.hub.knowledge_graph.graph.remove_node(skill_id)
            self.hub.knowledge_graph.save()
        except Exception:
            pass

        if self.audit_logger:
            self.audit_logger.log("REMOVE_SKILL", token, {"skill_id": skill_id})
        return {"status": "removed", "skill_id": skill_id}
