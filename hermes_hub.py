"""
Hermes Hub - Central Brain for Swarm Memory System
Main entry point for the Hub
"""
import asyncio
import json
import yaml
import os
import re
from pathlib import Path

# Storage
from storage.knowledge_graph import KnowledgeGraph

# Orchestrator
from orchestrator.skill_indexer import SkillIndexer
from orchestrator.arbitration_queue import ArbitrationQueue
from orchestrator.confidence import ConfidenceModel
from orchestrator.subscription import SubscriptionManager

# Sync
from sync.a2a_server import A2AServer
from sync.sync_scheduler import SyncScheduler
from sync.feishu_notifier import FeishuNotifier
from sync.feishu_ws_client import FeishuWSClient

# Master
from master.token_manager import TokenManager, AuditLogger
from master.master_api import MasterAPI


class HermesHub:
    """
    Central Hub for the Swarm Memory System.
    Coordinates knowledge graph, sync, and Master mode.
    """

    def __init__(self, config_path: str = "./config.yaml"):
        # Load configuration
        self.config = self._load_config(config_path)

        # Initialize storage
        kg_config = self.config["storage"]["graph"]
        kg_path = kg_config.get("persist_path", "./storage/knowledge_graph/graph.gpickle")
        self.knowledge_graph = KnowledgeGraph(persist_path=kg_path)

        # SkillIndexer with graph integration
        self.skill_indexer = SkillIndexer(graph_path=kg_path)

        # Arbitration (v3.0)
        self.arbitration_queue = ArbitrationQueue()
        self.confidence_model = ConfidenceModel()

        # Subscription (v3.0)
        self.subscription_manager = SubscriptionManager()

        # Initialize sync
        sync_config = self.config["sync"]
        self.a2a_server = A2AServer(
            host=self.config["a2a"]["server"]["host"],
            port=self.config["a2a"]["server"]["port"]
        )
        # 注入订阅管理器
        self.a2a_server.set_subscription_manager(self.subscription_manager)
        self.a2a_server.set_hub_controller(self)

        self.sync_scheduler = SyncScheduler(
            interval_minutes=sync_config["interval_minutes"]
        )

        # Feishu WS Client (长连接)
        feishu_config = self.config.get("feishu", {})
        self.feishu_app_id = feishu_config.get("app_id", "")
        self.feishu_app_secret = feishu_config.get("app_secret", "")
        self.feishu_ws_client = None
        if self.feishu_app_id and self.feishu_app_secret:
            self.feishu_ws_client = FeishuWSClient(
                self.feishu_app_id,
                self.feishu_app_secret
            )
            self._register_feishu_callbacks()

        # Feishu Notifier (备用 webhook)
        self.feishu_webhook = feishu_config.get("webhook_url", "")
        self.feishu_notifier = FeishuNotifier(self.feishu_webhook)

        # Initialize Master mode
        master_config = self.config["master"]
        self.token_manager = TokenManager(
            keyring_service=master_config["keyring_service"],
            ttl_hours=master_config["token_ttl_hours"]
        )
        self.audit_logger = AuditLogger(
            retention_days=master_config["audit_log_days"]
        )
        self.master_api = MasterAPI(
            token_manager=self.token_manager,
            audit_logger=self.audit_logger,
            hub_controller=self
        )

        # Register sync callback
        self.sync_scheduler.add_callback(self._on_sync_cycle)

    def _register_feishu_callbacks(self):
        """注册飞书回调处理器"""
        if not self.feishu_ws_client:
            return

        def handle_feishu_message(event: dict):
            """处理飞书消息"""
            try:
                message = event.get("message", {})
                content = json.loads(message.get("content", "{}"))
                text = content.get("text", "").strip()

                # 解析仲裁回复: "选择 v1" 或 "保留 xxx"
                if text.startswith("选择 "):
                    version_id = text.replace("选择 ", "").strip()
                    self._handle_arbitration_reply(version_id)
                elif text.startswith("保留 "):
                    skill_id = text.replace("保留 ", "").strip()
                    self._handle_arbitration_reply(skill_id)
            except Exception as e:
                print(f"[Hub] 飞书消息处理异常: {e}")

        def handle_card_action(event: dict):
            """处理卡片按钮点击"""
            try:
                action_value = event.get("action_value", {})
                if isinstance(action_value, str):
                    action_value = json.loads(action_value)
                if action_value.get("action") == "arbitrate":
                    case_id = action_value.get("case_id")
                    winner_id = action_value.get("winner_id")
                    if case_id and winner_id:
                        self.resolve_arbitration(case_id, winner_id, "用户点击卡片按钮仲裁")
            except Exception as e:
                print(f"[Hub] 卡片动作处理异常: {e}")

        self.feishu_ws_client.register_callback("message", handle_feishu_message)
        self.feishu_ws_client.register_callback("card_action", handle_card_action)

    def _handle_arbitration_reply(self, version_id: str):
        """处理仲裁回复"""
        pending = self.arbitration_queue.get_pending_cases()
        if not pending:
            return

        # 找到包含该版本的待仲裁案例
        for case in pending:
            for version in case.versions:
                if version.get("id") == version_id:
                    self.resolve_arbitration(case.id, version_id, "用户通过飞书仲裁")
                    return

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML, resolving ${ENV_VAR} placeholders"""
        with open(config_path, 'r') as f:
            raw = f.read()
        # Resolve ${ENV_VAR} placeholders before YAML parse
        def _replace_env(match):
            var = match.group(1)
            return os.environ.get(var, "")
        raw = re.sub(r'\$\{([^}]+)\}', _replace_env, raw)
        return yaml.safe_load(raw)

    async def _on_sync_cycle(self, sync_version: int):
        """Callback for each sync cycle"""
        print(f"[Hub] Sync cycle {sync_version} triggered")

        # Build skill index
        self._rebuild_skill_index()

        # A2A broadcast 已标记为 dead code（无注册的 agent）
        # 恢复时取消下面注释
        # from sync.a2a_server import create_sync_ready_message
        # delta = self.skill_indexer.get_delta_since(sync_version - 1)
        # message = create_sync_ready_message(
        #     hub_id="hermes-hub",
        #     version=sync_version,
        #     delta=[s["id"] for s in delta]
        # )
        # await self.a2a_server.broadcast(message)

    def _rebuild_skill_index(self):
        """Rebuild skill index from graph"""
        skills = self.knowledge_graph.get_all_skills()
        for skill in skills:
            self.skill_indexer.register_skill(skill)

    async def process_manifest(self, manifest: dict) -> dict:
        """
        Process an incoming skill manifest from an agent.
        register_skill handles dedup and graph update internally.
        """
        agent_id = manifest.get("agent_id", "unknown")
        results = {
            "agent_id": agent_id,
            "processed": 0,
            "merged": 0,
            "linked": 0,
            "added": 0,
            "errors": []
        }

        for skill in manifest.get("skills", []):
            try:
                result = self.skill_indexer.register_skill(skill)
                action = result.get("action", "added")
                if action == "added":
                    results["added"] += 1
                elif action == "merged":
                    results["merged"] += 1
                elif action == "linked":
                    results["linked"] += 1
                results["processed"] += 1
            except Exception as e:
                results["errors"].append({
                    "skill_id": skill.get("id"),
                    "error": str(e)
                })

        self.skill_indexer.increment_sync_version()
        return results

    def get_status(self) -> dict:
        """Get Hub status"""
        idx_stats = self.skill_indexer.stats()
        return {
            "hub_name": self.config["hub"]["name"],
            "version": self.config["hub"]["protocol_version"],
            "storage": {
                "skills": idx_stats["total_skills"],
                "tools": idx_stats["total_tools"],
                "users": idx_stats["total_users"],
                "graph_nodes": idx_stats.get("graph_nodes", 0),
                "graph_edges": idx_stats.get("graph_edges", 0)
            },
            "sync_scheduler": self.sync_scheduler.get_status(),
            "agents_registered": len(self.a2a_server.agents),
            "master_tokens_active": len(self.token_manager._tokens),
            "arbitration": self.arbitration_queue.stats(),
            "subscriptions": self.subscription_manager.stats()
        }

    def resolve_arbitration(self, case_id: str, winner_id: str, notes: str = "") -> dict:
        """
        处理仲裁结果回写
        用户仲裁后调用此方法
        """
        case = self.arbitration_queue.get_case(case_id)
        if not case:
            return {"status": "error", "message": f"案例 {case_id} 不存在"}

        if case.status != "pending":
            return {"status": "error", "message": f"案例 {case_id} 状态为 {case.status}，无需处理"}

        # 解决仲裁案例
        self.arbitration_queue.resolve_case(case_id, winner_id, notes)

        # 更新胜出版本的置信度
        for version in case.versions:
            if version.get("id") == winner_id:
                version["winner"] = True
                version["confidence"] = self.confidence_model.calc_confidence(version)
            else:
                version["winner"] = False

        # 找到胜出版本并更新 skill_index
        winner = next((v for v in case.versions if v.get("id") == winner_id), None)
        if winner:
            self.skill_indexer.register_skill(winner)
            print(f"[Hub] ✅ 仲裁完成: {case.skill_name} 胜出版本: {winner_id}")

        # 更新权威度
        loser_ids = [v.get("id") for v in case.versions if v.get("id") != winner_id]
        self.confidence_model.update_after_arbitration(winner_id, loser_ids)

        return {
            "status": "resolved",
            "case_id": case_id,
            "winner_id": winner_id,
            "skill_name": case.skill_name
        }

    async def start(self):
        """Start the Hub"""
        print("=" * 50)
        print("Hermes Hub v2.0 - Starting...")
        print("=" * 50)

        # A2A Server 已标记为 dead code（当前架构用 GitHub Issues 异步通信）
        # 启动语句已移除，保留构造代码供后续激活参考
        # await self.a2a_server.start()

        # Start sync scheduler
        await self.sync_scheduler.start()

        # Start Feishu WS client (if initialized)
        if self.feishu_ws_client is not None:
            self.feishu_ws_client.start()
            print("[Hub] Feishu WS 长连接已启动")

        print("=" * 50)
        print("Hermes Hub is running!")
        print(f"Status: {self.get_status()}")
        print("=" * 50)

    async def stop(self):
        """Stop the Hub"""
        await self.sync_scheduler.stop()
        if self.feishu_ws_client is not None:
            self.feishu_ws_client.stop()
        print("Hermes Hub stopped.")


async def main():
    """Main entry point"""
    hub = HermesHub(config_path="./config.yaml")
    try:
        await hub.start()
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await hub.stop()


if __name__ == "__main__":
    asyncio.run(main())
