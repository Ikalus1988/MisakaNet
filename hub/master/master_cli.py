"""
Master CLI - Master mode command interface
Processes /fool and other master commands

Supports both interactive and non-interactive (script) mode.
"""
import asyncio
import aiohttp
import sys
import os
import argparse
from typing import Optional
import json

from hub.master.token_manager import TokenManager, AuditLogger


# Token cache file for script mode
TOKEN_CACHE = os.path.expanduser("~/.hermes/master_token.cache")


class MasterCLI:
    """
    Master mode command line interface.
    Handles /fool unlock and master commands.
    """

    def __init__(self, hub_url: str = "http://localhost:8081"):
        self.hub_url = hub_url
        self.token_manager = TokenManager()
        self.audit_logger = AuditLogger()
        self.current_token: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Connect to Hub"""
        self._session = aiohttp.ClientSession()

    async def close(self):
        """Close connection"""
        if self._session:
            await self._session.close()

    async def handle_command(self, command: str) -> dict:
        """
        Handle a master command.

        Args:
            command: Full command string (e.g., "/fool", "/sync status")

        Returns:
            Command result dict
        """
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/fool":
            return await self._handle_fool(args)

        elif cmd == "/sync" and self.current_token:
            return await self._handle_sync(args)

        elif cmd == "/agent" and self.current_token:
            return await self._handle_agent(args)

        elif cmd == "/skill" and self.current_token:
            return await self._handle_skill(args)

        elif cmd == "/exit" and self.current_token:
            return await self._handle_exit()

        elif cmd == "/help":
            return self._help()

        elif not self.current_token:
            return {"error": "Master mode not active. Use /fool to unlock."}

        return {"error": f"Unknown command: {cmd}"}

    async def _handle_fool(self, args: str) -> dict:
        """
        Handle /fool - Master unlock challenge.

        Usage: /fool
        Response: "你的尊名是？"
        Answer: (user types their name)
        Correct answer: "贾恒龙"
        """
        if not args:
            # First step - ask the challenge question
            self.audit_logger.log("FOOL_CHALLENGE", "unknown", {})
            return {
                "challenge": True,
                "question": "你的尊名是？",
                "hint": "Type: /fool 贾恒龙"
            }

        # Verify the answer
        secret = args.strip()
        token = self.token_manager.generate_token(secret)

        if token:
            self.current_token = token
            self.audit_logger.log("FOOL_UNLOCK", token, {"success": True})

            return {
                "status": "success",
                "message": "✅ Master 模式已激活",
                "token_expires_in_hours": 24,
                "available_commands": [
                    "/sync status     - 查看所有节点同步进度",
                    "/sync trigger    - 手动触发同步",
                    "/agent list      - 列出所有节点",
                    "/agent add       - 新增节点",
                    "/agent remove    - 删除节点",
                    "/skill list      - 查看全量 skill",
                    "/skill remove    - 删除 skill",
                    "/exit            - 退出 Master 模式"
                ]
            }
        else:
            self.audit_logger.log("FOOL_FAILED", "unknown", {"attempt": secret})
            return {
                "status": "failed",
                "error": "❌ 验证失败，权限拒绝"
            }

    async def _handle_sync(self, args: str) -> dict:
        """Handle /sync commands"""
        if not self._validate_token():
            return {"error": "Invalid or expired token"}

        if args == "status":
            return await self._get_sync_status()
        elif args == "trigger":
            return await self._trigger_sync()
        else:
            return {"error": "Usage: /sync status | trigger"}

    async def _handle_agent(self, args: str) -> dict:
        """Handle /agent commands"""
        if not self._validate_token():
            return {"error": "Invalid or expired token"}

        parts = args.split()
        subcmd = parts[0] if parts else ""

        if subcmd == "list":
            return await self._list_agents()
        elif subcmd == "add" and len(parts) > 1:
            return await self._add_agent(parts[1])
        elif subcmd == "remove" and len(parts) > 1:
            return await self._remove_agent(parts[1])
        else:
            return {"error": "Usage: /agent list | add <id> | remove <id>"}

    async def _handle_skill(self, args: str) -> dict:
        """Handle /skill commands"""
        if not self._validate_token():
            return {"error": "Invalid or expired token"}

        parts = args.split()
        subcmd = parts[0] if parts else ""

        if subcmd == "list":
            return await self._list_skills()
        elif subcmd == "remove" and len(parts) > 1:
            return await self._remove_skill(parts[1])
        else:
            return {"error": "Usage: /skill list | remove <skill_id>"}

    async def _handle_exit(self) -> dict:
        """Handle /exit - logout of master mode"""
        if self.current_token:
            self.token_manager.revoke_token(self.current_token)
            self.audit_logger.log("MASTER_LOGOUT", self.current_token, {})
            self.current_token = None

        return {"status": "logged_out", "message": "已退出 Master 模式"}

    def _validate_token(self) -> bool:
        """Validate current token"""
        if not self.current_token:
            return False
        return self.token_manager.validate_token(self.current_token)

    def _help(self) -> dict:
        """Return help message"""
        return {
            "commands": {
                "/fool [答案]": "Master 解锁（输入 /fool 开始验证）",
                "/sync status": "查看同步状态",
                "/sync trigger": "手动触发同步",
                "/agent list": "列出所有节点",
                "/agent add <id>": "新增节点",
                "/agent remove <id>": "删除节点",
                "/skill list": "列出所有 skill",
                "/skill remove <id>": "删除 skill",
                "/exit": "退出 Master 模式"
            }
        }

    # Hub API calls
    async def _api_get(self, endpoint: str) -> dict:
        """Make GET request to Hub API"""
        if not self._session:
            return {"error": "Not connected"}

        try:
            async with self._session.get(f"{self.hub_url}{endpoint}") as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _api_post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to Hub API"""
        if not self._session:
            return {"error": "Not connected"}

        try:
            async with self._session.post(
                f"{self.hub_url}{endpoint}",
                json=data
            ) as resp:
                return await resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _get_sync_status(self) -> dict:
        """Get sync status of all agents"""
        result = await self._api_get("/agents")
        self.audit_logger.log("VIEW_SYNC_STATUS", self.current_token, {})
        return result

    async def _trigger_sync(self) -> dict:
        """Trigger manual sync"""
        result = await self._api_post("/sync/trigger", {
            "token": self.current_token
        })
        self.audit_logger.log("TRIGGER_SYNC", self.current_token, {})
        return result

    async def _list_agents(self) -> dict:
        """List all registered agents"""
        result = await self._api_get("/agents")
        self.audit_logger.log("LIST_AGENTS", self.current_token, {})
        return result

    async def _add_agent(self, agent_id: str) -> dict:
        """Add a new agent"""
        result = await self._api_post("/register", {
            "id": agent_id,
            "name": agent_id,
            "url": "",
            "capabilities": []
        })
        self.audit_logger.log("ADD_AGENT", self.current_token, {"agent_id": agent_id})
        return result

    async def _remove_agent(self, agent_id: str) -> dict:
        """Remove an agent"""
        result = await self._api_post("/unregister", {
            "agent_id": agent_id
        })
        self.audit_logger.log("REMOVE_AGENT", self.current_token, {"agent_id": agent_id})
        return result

    async def _list_skills(self) -> dict:
        """List all skills"""
        result = await self._api_get("/skills")
        self.audit_logger.log("LIST_SKILLS", self.current_token or "anon", {})
        return result

    async def _remove_skill(self, skill_id: str) -> dict:
        """Remove a skill via Master API"""
        result = await self._api_post("/skills/remove", {
            "token": self.current_token,
            "skill_id": skill_id
        })
        self.audit_logger.log("REMOVE_SKILL", self.current_token, {"skill_id": skill_id})
        return result

    def _cache_token(self, token: str):
        """Cache token to file for script reuse"""
        cache_path = os.path.dirname(TOKEN_CACHE)
        os.makedirs(cache_path, exist_ok=True)
        with open(TOKEN_CACHE, 'w') as f:
            json.dump({"token": token}, f)

    def _load_cached_token(self) -> Optional[str]:
        """Load cached token if valid"""
        try:
            if os.path.exists(TOKEN_CACHE):
                with open(TOKEN_CACHE, 'r') as f:
                    data = json.load(f)
                token = data.get("token", "")
                if token and self.token_manager.validate_token(token):
                    return token
        except Exception:
            pass
        return None


async def run_script_mode(command: str, hub_url: str = "http://localhost:8081") -> dict:
    """
    Run a single command in script mode.
    Handles /fool automatically (uses cached token or authenticates).
    Returns dict result for piping to other commands.
    """
    cli = MasterCLI(hub_url=hub_url)
    await cli.connect()

    try:
        # Try cached token first
        cached = cli._load_cached_token()
        if cached:
            cli.current_token = cached

        result = await cli.handle_command(command)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # Cache token on successful unlock
        if result.get("status") == "success" and cli.current_token:
            cli._cache_token(cli.current_token)

        return result
    finally:
        await cli.close()


async def interactive_mode():
    """Interactive Master CLI"""
    cli = MasterCLI()

    print("=" * 50)
    print("Hermes Master CLI")
    print("=" * 50)
    print("输入 /fool 开始解锁 Master 权限")
    print("输入 /help 查看所有命令")
    print("输入 /exit 退出")
    print("=" * 50)

    await cli.connect()

    try:
        while True:
            try:
                command = input("\n> ").strip()
            except EOFError:
                break

            if not command:
                continue

            if command.lower() in ["exit", "quit", "q"]:
                break

            result = await cli.handle_command(command)
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        await cli.close()


async def script_mode(command: str, hub_url: str):
    """Run a single command, auto-handle /fool with cached token"""
    cli = MasterCLI(hub_url=hub_url)
    await cli.connect()

    try:
        # Try cached token first
        cached = cli._load_cached_token()
        if cached:
            cli.current_token = cached
            print(f"[token] Using cached token", file=sys.stderr)

        result = await cli.handle_command(command)

        # Cache token on successful unlock
        if result.get("status") == "success" and cli.current_token:
            cli._cache_token(cli.current_token)
            print(f"[token] Cached new token", file=sys.stderr)

        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result
    finally:
        await cli.close()


def main():
    parser = argparse.ArgumentParser(
        description="Hermes Master CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--cmd", "-c",
        metavar="COMMAND",
        help="Run a single command (non-interactive/script mode). "
             "Example: --cmd \"/fool 贾恒龙\" or --cmd \"/skill list\""
    )
    parser.add_argument(
        "--hub-url",
        default="http://localhost:8081",
        help="Hub A2A Server URL (default: http://localhost:8081)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output raw JSON (no pretty print)"
    )

    args = parser.parse_args()

    if args.cmd:
        # Script mode
        result = asyncio.run(script_mode(args.cmd, args.hub_url))
        sys.exit(0 if "error" not in result else 1)
    else:
        # Interactive mode
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
