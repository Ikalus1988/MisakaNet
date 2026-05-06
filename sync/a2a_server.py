"""
A2A Server - Agent-to-Agent Protocol Server
Based on Google A2A Protocol

⚠️  DEAD CODE — 当前架构使用 GitHub Issues 异步通信，非 HTTP A2A。
保留作为设计参考，待仲裁/实时通信场景激活后重新启用。
当前 Hub 不 start() 此服务（hermes_hub.py 中已跳过）。
"""
import json
import asyncio
from typing import Dict, Callable, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from aiohttp import web


@dataclass
class AgentCard:
    """Agent registration card"""
    id: str
    name: str
    url: str
    capabilities: list
    version: str = "2.0"
    status: str = "active"


@dataclass
class Message:
    """A2A Message structure"""
    type: str  # SYNC_READY, PULL_DELTA, DELTA_RESPONSE, ACK, ERROR
    sender: str
    receiver: Optional[str] = None
    payload: dict = field(default_factory=dict)
    timestamp: str = ""


class A2AServer:
    """
    A2A Protocol Server for Hub.
    Handles agent registration, message routing, and sync coordination.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8081):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.agents: Dict[str, AgentCard] = {}
        self.subscribers: Dict[str, Callable] = {}

        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_post('/register', self.register_agent_handler)
        self.app.router.add_post('/unregister', self.unregister_agent_handler)
        self.app.router.add_get('/agents', self.list_agents_handler)
        self.app.router.add_post('/message', self.handle_message_handler)
        self.app.router.add_get('/sync/{agent_id}', self.get_sync_status_handler)
        self.app.router.add_post('/broadcast', self.broadcast_handler)
        self.app.router.add_post('/subscribe', self.subscribe_handler)
        self.app.router.add_post('/unsubscribe', self.unsubscribe_handler)
        self.app.router.add_get('/subscriptions/{agent_id}', self.get_subscriptions_handler)
        self.app.router.add_get('/hub/status', self.hub_status_handler)
        self.app.router.add_get('/skills', self.list_skills_handler)
        self.app.router.add_get('/tools', self.list_tools_handler)
        self.app.router.add_get('/users', self.list_users_handler)
        self.app.router.add_get('/graph/stats', self.graph_stats_handler)
        self.app.router.add_get('/graph/skill', self.graph_skill_handler)
        self.app.router.add_get('/graph/domain/{domain}', self.graph_domain_handler)
        self.app.router.add_get('/arbitration/cases', self.list_arbitration_cases_handler)
        self.app.router.add_post('/arbitration/resolve', self.resolve_arbitration_handler)

    async def start(self):
        """Start the A2A server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        print(f"A2A Server started on {self.host}:{self.port}")

    def register_agent(self, agent_card: AgentCard) -> bool:
        """Register an agent with the Hub"""
        self.agents[agent_card.id] = agent_card
        print(f"Agent registered: {agent_card.id} ({agent_card.name})")
        return True

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            print(f"Agent unregistered: {agent_id}")
            return True
        return False

    async def broadcast(self, message: Message):
        """
        Broadcast message to all registered agents.
        In production, this would use server-sent events or websocket.
        """
        for agent_id, agent in self.agents.items():
            if agent_id != message.sender:
                await self._send_to_agent(agent, message)

    async def _send_to_agent(self, agent: AgentCard, message: Message):
        """Send message to a specific agent via HTTP POST"""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{agent.url.rstrip('/')}/message"
                async with session.post(
                    url,
                    json=asdict(message),
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        print(f"[A2A] Sent {message.type} to {agent.id} → OK")
                        return True
                    else:
                        print(f"[A2A] Sent {message.type} to {agent.id} → {resp.status}")
                        return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            print(f"[A2A] Failed to send to {agent.id}: {e}")
            return False

    # HTTP Handlers
    async def health_check(self, request):
        return web.json_response({"status": "healthy", "agents": len(self.agents)})

    async def register_agent_handler(self, request):
        data = await request.json()
        agent_card = AgentCard(**data)
        self.register_agent(agent_card)
        return web.json_response({"status": "registered"})

    async def unregister_agent_handler(self, request):
        data = await request.json()
        agent_id = data.get("agent_id")
        success = self.unregister_agent(agent_id)
        return web.json_response({"status": "unregistered" if success else "not_found"})

    async def list_agents_handler(self, request):
        return web.json_response({
            "agents": [asdict(a) for a in self.agents.values()]
        })

    async def handle_message_handler(self, request):
        data = await request.json()
        message = Message(**data)

        # Process message based on type
        if message.type == "ACK":
            # Handle acknowledgment
            print(f"ACK from {message.sender}")
            return web.json_response({"status": "acknowledged"})

        elif message.type == "SKILL_MANIFEST":
            # Forward to Hub's skill_indexer
            manifest = message.payload
            sender = message.payload.get("agent_id", message.sender)
            print(f"SKILL_MANIFEST from {sender}: {len(manifest.get('skills', []))} skills, {len(manifest.get('tools', []))} tools")

            if hasattr(self, 'hub_controller'):
                # Register skills with dedup
                results = []
                for skill in manifest.get("skills", []):
                    r = self.hub_controller.skill_indexer.register_skill(skill)
                    results.append(r)

                # Register tools (only from non-"fool" nodes)
                if sender != "fool":
                    tools_count = self.hub_controller.skill_indexer.register_tools(
                        manifest.get("tools", []), source=sender
                    )
                    print(f"  Registered {tools_count} tools from {sender}")

                # Register user profile (only from non-"fool" nodes)
                user_data = manifest.get("user_profile") or manifest.get("user")
                if user_data and sender != "fool":
                    self.hub_controller.skill_indexer.register_user(user_data, source=sender)
                    print(f"  Registered user profile from {sender}")

                added = sum(1 for r in results if r["action"] == "added")
                merged = sum(1 for r in results if r["action"] == "merged")
                linked = sum(1 for r in results if r["action"] == "linked")
                return web.json_response({
                    "status": "manifest_received",
                    "skills_count": len(manifest.get("skills", [])),
                    "dedup_result": {"added": added, "merged": merged, "linked": linked}
                })
            else:
                # Fallback to own indexer
                from orchestrator.skill_indexer import SkillIndexer
                indexer = SkillIndexer(index_path="./storage/skill_index.json")
                for skill in manifest.get("skills", []):
                    indexer.register_skill(skill)
                return web.json_response({
                    "status": "manifest_received",
                    "skills_count": len(manifest.get("skills", []))
                })

        elif message.type == "PULL_DELTA":
            # Return skills from Hub's skill indexer
            if hasattr(self, 'hub_controller'):
                skills = self.hub_controller.skill_indexer.get_all_skills()
                sync_version = self.hub_controller.skill_indexer.index.get("sync_version", 0)
            else:
                from orchestrator.skill_indexer import SkillIndexer
                indexer = SkillIndexer(index_path="./storage/skill_index.json")
                skills = indexer.get_all_skills()
                sync_version = indexer.index.get("sync_version", 0)

            delta = [{"id": s["id"], "name": s["name"], "source": s.get("source", "")} for s in skills]

            response = {
                "type": "DELTA_RESPONSE",
                "payload": {
                    "delta": delta,
                    "version": sync_version
                }
            }
            return web.json_response(response)

        else:
            return web.json_response({"status": "processed"})

    async def get_sync_status_handler(self, request):
        agent_id = request.match_info['agent_id']
        # Return sync status for specific agent
        return web.json_response({
            "agent_id": agent_id,
            "status": "synced",
            "last_sync": datetime.now().isoformat()
        })

    async def broadcast_handler(self, request):
        data = await request.json()
        message = Message(**data)
        await self.broadcast(message)
        return web.json_response({"status": "broadcasted"})

    def set_subscription_manager(self, subscription_manager):
        """设置订阅管理器"""
        self.subscription_manager = subscription_manager

    async def subscribe_handler(self, request):
        """处理订阅请求"""
        data = await request.json()
        agent_id = data.get("agent_id")
        domain = data.get("domain")
        if not agent_id or not domain:
            return web.json_response({"error": "agent_id 和 domain 必填"}, status=400)
        if hasattr(self, 'subscription_manager'):
            success = self.subscription_manager.subscribe(agent_id, domain)
            return web.json_response({"status": "subscribed" if success else "failed"})
        return web.json_response({"error": "subscription manager not initialized"}, status=500)

    async def unsubscribe_handler(self, request):
        """处理取消订阅请求"""
        data = await request.json()
        agent_id = data.get("agent_id")
        domain = data.get("domain")
        if not agent_id or not domain:
            return web.json_response({"error": "agent_id 和 domain 必填"}, status=400)
        if hasattr(self, 'subscription_manager'):
            success = self.subscription_manager.unsubscribe(agent_id, domain)
            return web.json_response({"status": "unsubscribed" if success else "not_found"})
        return web.json_response({"error": "subscription manager not initialized"}, status=500)

    async def get_subscriptions_handler(self, request):
        """获取节点订阅列表"""
        agent_id = request.match_info['agent_id']
        if hasattr(self, 'subscription_manager'):
            subs = self.subscription_manager.get_subscriptions(agent_id)
            return web.json_response({"agent_id": agent_id, "subscriptions": subs})
        return web.json_response({"error": "subscription manager not initialized"}, status=500)

    def set_hub_controller(self, hub):
        """设置 Hub 控制器引用"""
        self.hub_controller = hub

    async def hub_status_handler(self, request):
        """Hub 完整状态"""
        if hasattr(self, 'hub_controller'):
            return web.json_response(self.hub_controller.get_status())
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def list_skills_handler(self, request):
        """列出所有 skills"""
        if hasattr(self, 'hub_controller'):
            skills = self.hub_controller.skill_indexer.get_all_skills()
            return web.json_response({"count": len(skills), "skills": skills})
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def list_tools_handler(self, request):
        """列出所有 tools"""
        if hasattr(self, 'hub_controller'):
            tools = self.hub_controller.skill_indexer.get_all_tools()
            return web.json_response({"count": len(tools), "tools": tools})
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def list_users_handler(self, request):
        """列出所有 users"""
        if hasattr(self, 'hub_controller'):
            users = self.hub_controller.skill_indexer.get_all_users()
            return web.json_response({"count": len(users), "users": users})
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def graph_stats_handler(self, request):
        """图谱统计"""
        if hasattr(self, 'hub_controller'):
            return web.json_response(self.hub_controller.skill_indexer.graph_stats())
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def graph_skill_handler(self, request):
        """获取与某 skill 相关的所有 skills"""
        skill_id = request.query.get('id') or request.query.get('skill_id')
        if not skill_id:
            return web.json_response({"error": "id or skill_id query param required"}, status=400)
        if hasattr(self, 'hub_controller'):
            related = self.hub_controller.skill_indexer.get_skill_related(skill_id, depth=2)
            return web.json_response({"skill_id": skill_id, "related": related})
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def graph_domain_handler(self, request):
        """获取某 domain 下的所有 skills"""
        domain = request.match_info['domain']
        if hasattr(self, 'hub_controller'):
            skills = self.hub_controller.skill_indexer.get_skills_by_domain(domain)
            return web.json_response({"domain": domain, "count": len(skills), "skills": skills})
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def list_arbitration_cases_handler(self, request):
        """列出仲裁案例"""
        if hasattr(self, 'hub_controller'):
            pending = self.hub_controller.arbitration_queue.get_pending_cases()
            return web.json_response({
                "pending_count": len(pending),
                "pending_cases": [asdict(c) if not isinstance(c, dict) else c for c in pending]
            })
        return web.json_response({"error": "hub controller not set"}, status=500)

    async def resolve_arbitration_handler(self, request):
        """解决仲裁案例"""
        if hasattr(self, 'hub_controller'):
            data = await request.json()
            case_id = data.get("case_id")
            winner_id = data.get("winner_id")
            notes = data.get("notes", "")
            if not case_id or not winner_id:
                return web.json_response({"error": "case_id 和 winner_id 必填"}, status=400)
            result = self.hub_controller.resolve_arbitration(case_id, winner_id, notes)
            return web.json_response(result)
        return web.json_response({"error": "hub controller not set"}, status=500)


def create_sync_ready_message(hub_id: str, version: int,
                              delta: list) -> Message:
    """Create a SYNC_READY broadcast message"""
    return Message(
        type="SYNC_READY",
        sender=hub_id,
        receiver=None,
        payload={
            "version": version,
            "delta": delta,
            "timestamp": datetime.now().isoformat()
        }
    )


def create_delta_response_message(hub_id: str, agent_id: str,
                                  delta: list) -> Message:
    """Create a DELTA_RESPONSE message"""
    return Message(
        type="DELTA_RESPONSE",
        sender=hub_id,
        receiver=agent_id,
        payload={
            "delta": delta,
            "timestamp": datetime.now().isoformat()
        }
    )
