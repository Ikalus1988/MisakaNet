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
        """Decorator helper to check Master token"""
        return self.token_manager.validate_token(token)

    def get_all_agent_status(self, token: str) -> dict:
        """Get sync status of all agents"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        status = {
            "agents": [],
            "hub": self.hub.get_status()
        }

        # Get agent list from A2A server
        for agent_id, agent in self.hub.a2a_server.agents.items():
            status["agents"].append({
                "id": agent.id,
                "name": agent.name,
                "status": agent.status,
                "last_seen": "unknown"  # Track in production
            })

        self.audit_logger.log("VIEW_STATUS", token, {"agent_count": len(status["agents"])})
        return status

    def add_agent(self, token: str, agent_config: dict) -> dict:
        """Add a new agent to the network"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        agent_id = agent_config.get("id")
        if not agent_id:
            return {"error": "Missing agent_id"}

        # Register with A2A server
        from sync.a2a_server import AgentCard
        agent_card = AgentCard(
            id=agent_id,
            name=agent_config.get("name", agent_id),
            url=agent_config.get("url", ""),
            capabilities=agent_config.get("capabilities", [])
        )

        self.hub.a2a_server.register_agent(agent_card)
        self.audit_logger.log("ADD_AGENT", token, {"agent_id": agent_id})

        return {"status": "added", "agent_id": agent_id}

    def remove_agent(self, token: str, agent_id: str) -> dict:
        """Remove an agent from the network"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        success = self.hub.a2a_server.unregister_agent(agent_id)

        if success:
            self.audit_logger.log("REMOVE_AGENT", token, {"agent_id": agent_id})
            return {"status": "removed", "agent_id": agent_id}
        else:
            return {"error": "Agent not found"}

    def trigger_sync(self, token: str,
                     target_agent_ids: Optional[list] = None) -> dict:
        """Manually trigger sync"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        import asyncio
        asyncio.create_task(self.hub.sync_scheduler.trigger_manual_sync())

        self.audit_logger.log("TRIGGER_SYNC", token,
                              {"targets": target_agent_ids or "all"})
        return {"status": "sync_triggered"}

    def list_skills(self, token: str) -> dict:
        """List all skills in the network"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        skills = self.hub.skill_indexer.get_all_skills()
        self.audit_logger.log("LIST_SKILLS", token, {"count": len(skills)})

        return {"skills": skills, "count": len(skills)}

    def remove_skill(self, token: str, skill_id: str) -> dict:
        """Remove a skill from the network"""
        if not self.require_master(token):
            return {"error": "Invalid token"}

        # Remove from indexer
        self.hub.skill_indexer.unregister_skill(skill_id)

        # Remove from vector store (if initialized)
        if hasattr(self.hub, 'vector_store') and self.hub.vector_store is not None:
            self.hub.vector_store.delete_skill(skill_id)

        # Remove from graph
        try:
            self.hub.knowledge_graph.graph.remove_node(skill_id)
            self.hub.knowledge_graph.save()
        except Exception:
            pass

        self.audit_logger.log("REMOVE_SKILL", token, {"skill_id": skill_id})
        return {"status": "removed", "skill_id": skill_id}
