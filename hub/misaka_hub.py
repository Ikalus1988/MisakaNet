"""
MisakaHub — 轻量同步调度器 + 知识图谱 + 仲裁管理

不再是"中心协调节点"，而是可选的"图书馆管理员":
- 定时 git pull/push 同步
- 知识图谱构建
- 冲突时创建 GitHub Issue（取代飞书卡片）
- 可选通知通道（Discord/Slack/Email）
"""
import asyncio
import json
import yaml
import os
import re
from pathlib import Path

# Storage
from hub.storage.knowledge_graph import KnowledgeGraph

# Orchestrator
from hub.orchestrator.skill_indexer import SkillIndexer
from hub.orchestrator.arbitration_queue import ArbitrationQueue
from hub.orchestrator.confidence import ConfidenceModel
from hub.orchestrator.subscription import SubscriptionManager

# Sync
from hub.sync.sync_scheduler import SyncScheduler

# Notifiers
from hub.sync.notifier import DiscordNotifier, SlackNotifier, EmailNotifier

# Master
from hub.master.token_manager import TokenManager, AuditLogger
from hub.master.master_api import MasterAPI

# Federation
from hub.federation.registry import FederationRegistry, PeerNode
from hub.federation.sync_protocol import SyncProtocol


class MisakaHub:
    """
    轻量 Hub — 只做三件事：
    1. 定时同步各节点知识
    2. 检测知识冲突，创建 GitHub Issue
    3. 可选通知（Discord/Slack/Email）
    """

    def __init__(self, config_path: str = "./hub/config.yaml"):
        self.config = self._load_config(config_path)

        # 知识图谱
        kg_config = self.config["storage"]["graph"]
        kg_path = kg_config.get("persist_path", "./hub/storage/knowledge_graph/graph.gpickle")
        self.knowledge_graph = KnowledgeGraph(persist_path=kg_path)

        # 技能索引
        self.skill_indexer = SkillIndexer(graph_path=kg_path)

        # 仲裁队列
        self.arbitration_queue = ArbitrationQueue()
        self.confidence_model = ConfidenceModel()
        self.subscription_manager = SubscriptionManager()

        # 同步调度器（核心功能）
        sync_config = self.config.get("sync", {})
        self.sync_scheduler = SyncScheduler(
            interval_minutes=sync_config.get("interval_minutes", 30)
        )

        # 通知通道（可选配置）
        self.notifiers = []
        notifier_config = self.config.get("notifier", {})
        for channel, cls in [("discord", DiscordNotifier), ("slack", SlackNotifier)]:
            url = notifier_config.get(channel, {}).get("webhook_url", "")
            if url:
                self.notifiers.append(cls(url))
        if os.environ.get("EMAIL_SMTP_HOST"):
            self.notifiers.append(EmailNotifier())

        channel_names = [c.__class__.__name__ for c in self.notifiers]
        print(f"  🔔 通知通道: {' + '.join(channel_names) if channel_names else '未配置'}")

        # Master 模式（可选）
        master_config = self.config.get("master", {})
        self.master_api = None
        if master_config.get("keyring_service"):
            self.token_manager = TokenManager(
                keyring_service=master_config["keyring_service"],
                ttl_hours=master_config.get("token_ttl_hours", 24)
            )
            self.audit_logger = AuditLogger(
                retention_days=master_config.get("audit_log_days", 90)
            )
            self.master_api = MasterAPI(
                token_manager=self.token_manager,
                audit_logger=self.audit_logger,
                hub_controller=self
            )

        self.sync_scheduler.add_callback(self._on_sync_cycle)

        # Federation sync (cross-repo lesson sync)
        self.federation_registry = None
        self.federation_sync = None
        federation_config_path = Path(config_path).parent / "federation" / "config.yaml"
        if federation_config_path.exists():
            fed_config = yaml.safe_load(federation_config_path.read_text()) or {}
            registry_path = Path(config_path).parent / "federation" / "registry.json"
            self.federation_registry = FederationRegistry(str(registry_path))
            if fed_config.get("local_node_id"):
                self.federation_registry.local_node_id = fed_config["local_node_id"]
            for peer_data in fed_config.get("peers", []):
                self.federation_registry.add_peer(PeerNode.from_dict(peer_data))
            lessons_dir = Path(config_path).parent.parent / "lessons"
            staging_dir = Path(config_path).parent / "federation" / "staging"
            self.federation_sync = SyncProtocol(
                registry=self.federation_registry,
                lessons_dir=lessons_dir,
                staging_dir=staging_dir,
                sync_interval_minutes=fed_config.get("sync_interval_minutes", 15),
            )
            print(f"  🌐 Federation: {self.federation_registry.peer_count()} peers configured")

    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            raw = f.read()

        def _replace_env(match):
            var = match.group(1)
            return os.environ.get(var, "")
        raw = re.sub(r'\$\{([^}]+)\}', _replace_env, raw)
        return yaml.safe_load(raw)

    async def _on_sync_cycle(self, sync_version: int):
        print(f"[Hub] Sync cycle {sync_version} triggered")
        self._rebuild_skill_index()

        # Run federation sync if configured
        if self.federation_sync:
            for peer in self.federation_registry.active_peers():
                if self.federation_sync.needs_sync(peer):
                    try:
                        result = self.federation_sync.sync_peer(peer)
                        synced = result.get("added", 0) + result.get("updated", 0)
                        if synced:
                            print(f"  🌐 Federation: synced {synced} lessons from {peer.node_id}")
                    except Exception as e:
                        print(f"  ⚠️ Federation sync failed ({peer.node_id}): {e}")

        skill_count = len(self.knowledge_graph.get_all_skills())
        self._notify_all("notify_sync_ready", agent_id="hub", skill_count=skill_count)

    def _rebuild_skill_index(self):
        skills = self.knowledge_graph.get_all_skills()
        for skill in skills:
            self.skill_indexer.register_skill(skill)

    def _notify_all(self, method: str, *args, **kwargs):
        for n in self.notifiers:
            try:
                getattr(n, method)(*args, **kwargs)
            except Exception as e:
                print(f"  ⚠️ 通知失败 ({n.__class__.__name__}): {e}")

    # ── 冲突 → GitHub Issue ──

    def _create_conflict_issue(self, case_id: str, skill_name: str, versions: list) -> str | None:
        body_lines = [
            f"## ⚖️ 知识冲突: {skill_name}",
            "",
            f"**案例 ID**: `{case_id}`",
            f"**冲突版本数**: {len(versions)}",
            "",
            "### 各版本对比",
            "",
        ]
        for i, v in enumerate(versions):
            desc = v.get("description", "(无描述)")[:300]
            src = v.get("source", "unknown")
            body_lines.append(f"#### v{i+1} — 来源: {src}")
            body_lines.append("")
            body_lines.append(desc)
            body_lines.append("")

        body_lines.extend([
            "### 仲裁操作",
            "",
            "请评审各版本后，在 Issue 评论中说明选择哪个版本：",
            "- `@ 选择 v1` — 确认版本 1",
            "- `@ 选择 v2` — 确认版本 2",
            "- `@ 合并` — 两个版本整合",
            "",
            "---",
            "*由 MisakaNet Hub 自动创建*",
        ])

        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print(f"  ⚠️ GITHUB_TOKEN 未设置，无法创建 Issue")
            return None

        import urllib.request
        url = "https://api.github.com/repos/Ikalus1988/MisakaNet/issues"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        data = json.dumps({
            "title": f"[冲突] {skill_name} — {len(versions)} 个版本",
            "body": "\n".join(body_lines),
            "labels": ["conflict", "arbitration"],
        }).encode()
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                issue = json.loads(resp.read().decode())
                print(f"  ✅ 冲突 Issue 已创建: {issue['html_url']}")
                return issue["html_url"]
        except Exception as e:
            print(f"  ❌ 创建 Issue 失败: {e}")
            return None

    def resolve_arbitration(self, case_id: str, winner_id: str, note: str = ""):
        self.arbitration_queue.resolve_case(case_id, winner_id)
        print(f"[Hub] 仲裁已解决: {case_id} → winner: {winner_id}")

    # ── 生命周期 ──

    async def start(self):
        print(f"\n{'='*40}")
        print(f"  MisakaHub 启动")
        print(f"{'='*40}")
        self.sync_scheduler.start()
        print(f"[Hub] 就绪 (同步间隔: {self.sync_scheduler.interval_minutes} 分钟)")
        print()

    async def stop(self):
        self.sync_scheduler.stop()
        print("[Hub] 已停止")

    def status(self) -> dict:
        skill_count = len(self.knowledge_graph.get_all_skills())
        pending = len(self.arbitration_queue.get_pending_cases())
        status_data = {
            "hub_name": self.config.get("hub", {}).get("name", "misaka-hub"),
            "version": self.config.get("hub", {}).get("protocol_version", "1.0"),
            "skills": skill_count,
            "pending_conflicts": pending,
            "notifiers": [n.__class__.__name__ for n in self.notifiers],
        }
        if self.federation_registry:
            status_data["federation_peers"] = self.federation_registry.peer_count()
            status_data["federation_local_node"] = self.federation_registry.local_node_id
        return status_data


async def main():
    hub = MisakaHub(config_path="./config.yaml")
    try:
        await hub.start()
        while True:
            await asyncio.sleep(3600)
            print(f"[Hub] 状态: {hub.status()}")
    except KeyboardInterrupt:
        await hub.stop()


if __name__ == "__main__":
    asyncio.run(main())
