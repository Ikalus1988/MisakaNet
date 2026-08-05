"""通知通道抽象基类 + Discord / Slack 实现。

用法:
    from hub.sync.notifier import DiscordNotifier, SlackNotifier

    notifier = DiscordNotifier("https://discord.com/api/webhooks/...")
    notifier.notify_arbitration_case({"id": "ARB-001", "skill_name": "feishu-api", ...})
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """通知通道抽象基类。所有通道子类必须实现以下方法。"""

    @abstractmethod
    def notify_arbitration_case(self, case: dict) -> bool:
        """发送仲裁案例通知。"""
        ...

    @abstractmethod
    def notify_sync_ready(self, agent_id: str, skill_count: int) -> bool:
        """通知节点同步就绪。"""
        ...

    @abstractmethod
    def send_hook_stats(self, stats: list[dict]) -> bool:
        """发送 hook 统计。"""
        ...

    @abstractmethod
    def notify_agent_registered(self, agent_id: str) -> bool:
        """通知新节点注册。"""
        ...


class _WebhookNotifier(Notifier):
    """基于 webhook 的 notifier 基类，封装 POST 逻辑。"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _post(self, payload: dict, timeout: int = 10) -> bool:
        if not self.webhook_url:
            logger.warning(f"{self.__class__.__name__} webhook 未配置")
            return False
        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(self.webhook_url, data=data,
                          headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=timeout) as resp:
                return resp.status == 200 or resp.status == 204
        except URLError as e:
            logger.error(f"{self.__class__.__name__} 发送失败: {e}")
            return False


class DiscordNotifier(_WebhookNotifier):
    """Discord Webhook 通知通道。"""

    def notify_arbitration_case(self, case: dict) -> bool:
        versions = case.get("versions", [])
        desc = "\n".join(
            f"**v{i+1}** ({v.get('source','?')}): {v.get('description','')[:80]}"
            for i, v in enumerate(versions)
        )
        embed = {
            "title": f"⚖️ 仲裁请求: {case.get('skill_name', 'Unknown')}",
            "description": f"案例 ID: `{case.get('id', '')}`\n\n{desc}" if desc else "",
            "color": 0xE74C3C,
            "timestamp": case.get("created_at", ""),
        }
        payload = {
            "username": "MisakaNet Hub",
            "embeds": [embed],
        }
        return self._post(payload)

    def notify_sync_ready(self, agent_id: str, skill_count: int) -> bool:
        payload = {
            "username": "MisakaNet Hub",
            "embeds": [{
                "title": "🔄 同步就绪",
                "description": f"节点 `{agent_id}` 已就绪，{skill_count} 条 skill",
                "color": 0x2ECC71,
            }],
        }
        return self._post(payload)

    def send_hook_stats(self, stats: list[dict]) -> bool:
        lines = "\n".join(
            f"• `{s.get('hook','?')}`: {s.get('count',0)} 次触发"
            for s in stats[:10]
        )
        payload = {
            "username": "MisakaNet Hub",
            "embeds": [{
                "title": "📊 Hook 统计",
                "description": lines or "(无数据)",
                "color": 0x3498DB,
            }],
        }
        return self._post(payload)

    def notify_agent_registered(self, agent_id: str) -> bool:
        payload = {
            "username": "MisakaNet Hub",
            "embeds": [{
                "title": "🤖 新节点注册",
                "description": f"节点 `{agent_id}` 已加入网络",
                "color": 0x9B59B6,
            }],
        }
        return self._post(payload)


class EmailNotifier(Notifier):
    """SMTP 邮件通知通道。

    依赖: Python stdlib smtplib + email，零额外依赖。

    配置示例:
        EMAIL_SMTP_HOST=smtp.gmail.com
        EMAIL_SMTP_PORT=587
        EMAIL_SENDER=misakanet@example.com
        EMAIL_PASSWORD=your-app-password
        EMAIL_RECIPIENT=admin@example.com
    """

    def __init__(self, smtp_host: str = "", smtp_port: int = 587,
                 sender: str = "", password: str = "", recipient: str = "",
                 use_tls: bool = True):
        import os
        self.smtp_host = smtp_host or os.environ.get("EMAIL_SMTP_HOST", "")
        self.smtp_port = smtp_port or int(os.environ.get("EMAIL_SMTP_PORT", "587"))
        self.sender = sender or os.environ.get("EMAIL_SENDER", "")
        self.password = password or os.environ.get("EMAIL_PASSWORD", "")
        self.recipient = recipient or os.environ.get("EMAIL_RECIPIENT", "")
        self.use_tls = use_tls

    def _send(self, subject: str, body: str) -> bool:
        if not self.smtp_host or not self.sender or not self.recipient:
            logger.warning("EmailNotifier 未完全配置，跳过")
            return False
        try:
            import smtplib
            from email.mime.text import MIMEText
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.sender
            msg["To"] = self.recipient
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as s:
                if self.use_tls:
                    s.starttls()
                if self.password:
                    s.login(self.sender, self.password)
                s.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"EmailNotifier 发送失败: {e}")
            return False

    def notify_arbitration_case(self, case: dict) -> bool:
        versions = case.get("versions", [])
        desc = "\n".join(
            f"v{i+1} ({v.get('source','?')}): {v.get('description','')[:100]}"
            for i, v in enumerate(versions)
        )
        return self._send(
            f"⚖️ 仲裁请求: {case.get('skill_name', 'Unknown')}",
            f"案例 ID: {case.get('id', '')}\n\n候选版本:\n{desc}",
        )

    def notify_sync_ready(self, agent_id: str, skill_count: int) -> bool:
        return self._send(
            f"🔄 MisakaNet 同步就绪",
            f"节点 {agent_id} 已就绪，{skill_count} 条 skill",
        )

    def send_hook_stats(self, stats: list[dict]) -> bool:
        lines = "\n".join(
            f"• {s.get('hook','?')}: {s.get('count',0)} 次触发"
            for s in stats[:10]
        )
        return self._send("📊 Hook 统计", lines or "(无数据)")

    def notify_agent_registered(self, agent_id: str) -> bool:
        return self._send(
            f"🤖 新节点注册",
            f"节点 {agent_id} 已加入 MisakaNet 网络",
        )


class SlackNotifier(_WebhookNotifier):
    """Slack Webhook 通知通道。"""

    def _build_block(self, title: str, body: str, color: str = "#0747A6") -> dict:
        return {
            "attachments": [{
                "color": color,
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": title}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": body}},
                ],
            }],
        }

    def notify_arbitration_case(self, case: dict) -> bool:
        versions = case.get("versions", [])
        desc = "\n".join(
            f"• *v{i+1}* ({v.get('source','?')}): {v.get('description','')[:80]}"
            for i, v in enumerate(versions)
        )
        body = f"案例 ID: `{case.get('id', '')}`\n\n{desc}" if desc else ""
        return self._post(self._build_block(
            f"⚖️ 仲裁请求: {case.get('skill_name', 'Unknown')}", body, "#E74C3C"))

    def notify_sync_ready(self, agent_id: str, skill_count: int) -> bool:
        return self._post(self._build_block(
            "🔄 同步就绪", f"节点 `{agent_id}` 已就绪，{skill_count} 条 skill", "#2ECC71"))

    def send_hook_stats(self, stats: list[dict]) -> bool:
        lines = "\n".join(
            f"• `{s.get('hook','?')}`: {s.get('count',0)} 次触发"
            for s in stats[:10]
        )
        return self._post(self._build_block("📊 Hook 统计", lines or "(无数据)", "#3498DB"))

    def notify_agent_registered(self, agent_id: str) -> bool:
        return self._post(self._build_block(
            "🤖 新节点注册", f"节点 `{agent_id}` 已加入网络", "#9B59B6"))
