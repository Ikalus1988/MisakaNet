"""
Master API - Master mode command handlers
"""
from typing import Optional
from .token_manager import TokenManager, AuditLogger


class MasterAPI:
    """
    Master mode API for privileged operations.
    Requires valid Master token.
    """

    def __init__(self, token_manager: TokenManager,
                 audit_logger: AuditLogger,
                 hub_controller):
        self.token_manager = token_manager
        self.audit_logger = audit_logger
        self.hub = hub_controller

    def require_master(self, token: str) -> bool:
        return self.token_manager.validate_token(token)

    def get_all_agent_status(self, token: str) -> dict:
        if not self.require_master(token):
            return {"error": "Invalid token"}
        status = {
            "agents": [],
            "hub": self.hub.status(),
        }
        self.audit_logger.log("VIEW_STATUS", token, {"agent_count": 0})
        return status

    def add_agent(self, token: str, agent_config: dict) -> dict:
        if not self.require_master(token):
            return {"error": "Invalid token"}
        agent_id = agent_config.get("id")
        if not agent_id:
            return {"error": "Missing agent_id"}
        self.audit_logger.log("ADD_AGENT", token, {"agent_id": agent_id})
        return {"status": "added", "agent_id": agent_id}

    def remove_agent(self, token: str, agent_id: str) -> dict:
        if not self.require_master(token):
            return {"error": "Invalid token"}
        self.audit_logger.log("REMOVE_AGENT", token, {"agent_id": agent_id})
        return {"status": "removed", "agent_id": agent_id}

    def trigger_sync(self, token: str,
                     target_agent_ids: Optional[list] = None) -> dict:
        if not self.require_master(token):
            return {"error": "Invalid token"}
        import asyncio
        asyncio.create_task(self.hub.sync_scheduler.trigger_manual_sync())
        self.audit_logger.log("TRIGGER_SYNC", token,
                              {"targets": target_agent_ids or "all"})
        return {"status": "sync_triggered"}

    def list_skills(self, token: str) -> dict:
        if not self.require_master(token):
            return {"error": "Invalid token"}
        skills = self.hub.skill_indexer.get_all_skills()
        self.audit_logger.log("LIST_SKILLS", token, {"count": len(skills)})
        return {"skills": skills, "count": len(skills)}

    def remove_skill(self, token: str, skill_id: str) -> dict:
        if not self.require_master(token):
            return {"error": "Invalid token"}
        self.hub.skill_indexer.unregister_skill(skill_id)
        if hasattr(self.hub, 'vector_store') and self.hub.vector_store is not None:
            self.hub.vector_store.delete_skill(skill_id)
        try:
            self.hub.knowledge_graph.graph.remove_node(skill_id)
            self.hub.knowledge_graph.save()
        except Exception:
            import logging
            logging.error(f"[MasterAPI] Failed to remove skill {skill_id} from graph", exc_info=True)
        self.audit_logger.log("REMOVE_SKILL", token, {"skill_id": skill_id})
        return {"status": "removed", "skill_id": skill_id}
