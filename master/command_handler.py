"""
Master Command Handler - Integration for any agent
Provides /fool unlock capability for all nodes

⚠️  DEAD CODE — 未接入任何实际 agent。Master 权限通过 master_cli.py 实现。
保留作为集成参考。
"""
import asyncio
from typing import Callable, Optional
from master.token_manager import TokenManager, AuditLogger


class MasterCommandHandler:
    """
    Handles Master mode commands for any agent.
    Can be integrated into NodeAgent or used standalone.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.token_manager = TokenManager()
        self.audit_logger = AuditLogger()
        self.current_token: Optional[str] = None
        self._master_callbacks: dict = {}

    def register_master_callback(self, command: str, callback: Callable):
        """
        Register a callback for master commands.

        Args:
            command: "sync_status", "add_agent", "remove_agent", etc.
            callback: async function(token, args) -> dict
        """
        self._master_callbacks[command] = callback

    async def handle_input(self, text: str) -> Optional[dict]:
        """
        Handle user input, return response if command processed.

        Args:
            text: Raw user input

        Returns:
            Response dict if command handled, None otherwise
        """
        text = text.strip()

        if text == "/fool":
            return await self._handle_fool("")

        if text.startswith("/fool "):
            return await self._handle_fool(text[6:])

        if not self.current_token:
            return None

        if text == "/exit":
            return await self._handle_exit()

        if text == "/help":
            return self._get_help()

        # Check if it's a master command
        for cmd, callback in self._master_callbacks.items():
            if text.startswith(f"/{cmd}"):
                args = text[len(cmd)+2:] if len(text) > len(cmd) + 1 else ""
                return await callback(self.current_token, args)

        return None

    async def _handle_fool(self, answer: str) -> dict:
        """Handle /fool unlock"""
        if not answer:
            return {
                "type": "challenge",
                "question": "你的尊名是？",
                "hint": "格式: /fool 贾恒龙"
            }

        # Verify answer
        token = self.token_manager.generate_token(answer)

        if token:
            self.current_token = token
            self.audit_logger.log("MASTER_UNLOCK", self.agent_id, {"success": True})

            return {
                "type": "unlock_success",
                "message": "🎉 Master 模式已激活",
                "token_expires_hours": 24,
                "commands": [
                    "/sync status   - 查看同步状态",
                    "/sync trigger  - 手动触发同步",
                    "/skill list    - 查看所有 skill",
                    "/exit          - 退出"
                ]
            }
        else:
            self.audit_logger.log("MASTER_UNLOCK_FAILED", self.agent_id, {
                "attempt": answer[:10]
            })
            return {
                "type": "unlock_failed",
                "error": "验证失败"
            }

    async def _handle_exit(self) -> dict:
        """Handle /exit"""
        if self.current_token:
            self.token_manager.revoke_token(self.current_token)
            self.audit_logger.log("MASTER_LOGOUT", self.agent_id, {})
            self.current_token = None

        return {
            "type": "logout",
            "message": "已退出 Master 模式"
        }

    def _get_help(self) -> dict:
        """Get help text"""
        return {
            "type": "help",
            "commands": {
                "/fool [答案]": "Master 解锁",
                "/sync status": "查看同步状态",
                "/sync trigger": "手动触发同步",
                "/skill list": "列出 skill",
                "/exit": "退出 Master 模式"
            }
        }

    def is_master_active(self) -> bool:
        """Check if master mode is active"""
        if not self.current_token:
            return False
        return self.token_manager.validate_token(self.current_token)


# Example integration with NodeAgent
async def master_enabled_node_example():
    """
    Example showing how to integrate MasterHandler with NodeAgent.
    """
    from node_agent import NodeAgent
    from master.command_handler import MasterCommandHandler

    # Create node agent
    agent = NodeAgent()

    # Create master handler
    master_handler = MasterCommandHandler(agent_id=agent.config["node"]["id"])

    # Register master callbacks
    async def on_sync_status(token: str, args: str) -> dict:
        return await agent.sync_client.trigger_manual_sync()

    master_handler.register_master_callback("sync status", on_sync_status)
    master_handler.register_master_callback("sync trigger", on_sync_status)

    # In the agent's message handler:
    async def handle_message(text: str) -> dict:
        # Check for master commands first
        result = await master_handler.handle_input(text)
        if result:
            return result

        # Normal message handling
        return {"type": "normal", "response": "processed"}
