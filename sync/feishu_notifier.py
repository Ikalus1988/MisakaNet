"""
Feishu Notifier - 飞书通知模块
当仲裁案例创建时，通过飞书机器人通知用户
"""
import requests
from typing import Optional


class FeishuNotifier:
    """
    飞书通知器
    使用飞书机器人 webhook 发送通知
    """

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def notify_arbitration_case(self, case: dict, feishu_webhook: str = None) -> bool:
        """
        发送仲裁案例通知到飞书（卡片+按钮）
        case: 包含 id, skill_name, versions 等字段
        """
        webhook = feishu_webhook or self.webhook_url
        if not webhook:
            print("[Feishu] 未配置 webhook，跳过通知")
            return False

        versions_text = ""
        buttons = []
        for i, v in enumerate(case.get("versions", [])):
            desc = v.get("description", "")[:50]
            source = v.get("source", "unknown")
            versions_text += f"• **v{i+1}**: {desc}... (来源: {source})\n"
            version_id = v.get("id", f"v{i+1}")
            buttons.append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": f"选择 v{i+1}"},
                "type": "primary",
                "value": {"action": "arbitrate", "case_id": case.get("id", ""), "winner_id": version_id}
            })

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"⚖️ 仲裁请求: {case.get('skill_name', 'Unknown')}"},
                    "template": "red"
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"**案例 ID**: `{case.get('id', '')}`\n\n**候选版本**:\n{versions_text}"
                    },
                    {"tag": "hr"},
                    {
                        "tag": "action",
                        "actions": buttons
                    },
                    {
                        "tag": "markdown",
                        "content": "或回复: `选择 v1` / `保留 xxx`"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": "虫群记忆系统 v3.0"}
                        ]
                    }
                ]
            }
        }

        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"[Feishu] ✅ 仲裁通知已发送: {case.get('id')}")
                return True
            else:
                print(f"[Feishu] ❌ 发送失败: {resp.status_code}")
                return False
        except Exception as e:
            print(f"[Feishu] ❌ 发送异常: {e}")
            return False

    def notify_sync_ready(self, agent_id: str, skill_count: int, feishu_webhook: str = None) -> bool:
        """通知同步就绪"""
        webhook = feishu_webhook or self.webhook_url
        if not webhook:
            return False

        payload = {
            "msg_type": "text",
            "content": {"text": f"🔔 同步就绪: {agent_id} - {skill_count} 个 skills"}
        }

        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def send_hook_stats(self, stats: list[dict], feishu_webhook: str = None) -> bool:
        """发送 Hook 统计数据到飞书"""
        webhook = feishu_webhook or self.webhook_url
        if not webhook:
            print("[Feishu] 未配置 webhook，跳过 hook 统计通知")
            return False

        lines = ["📊 MisakaNet Hook 统计\n"]
        for s in stats:
            node = s.get("node", "?")
            cat_lines = []
            for cat in ["network", "pip", "permission", "disk", "package_conflict", "model_output"]:
                t = s.get("triggers", {}).get(cat, 0)
                h = s.get("hits", {}).get(cat, 0)
                if t > 0:
                    icons = {"network": "🔴", "pip": "🟡", "permission": "🔵", "disk": "🟣",
                             "package_conflict": "🟠", "model_output": "⚪"}
                    cat_lines.append(f"  {icons.get(cat, '⚪')} {cat}  {t}次  lessons 有答案{h}次")
            if cat_lines:
                lines.append(f"节点 {node}:")
                lines.extend(cat_lines)
            else:
                lines.append(f"节点 {node}: 无触发")

        payload = {
            "msg_type": "text",
            "content": {"text": "\n".join(lines)}
        }

        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"[Feishu] Hook stats 已推送 ({len(stats)} 节点)")
            return resp.status_code == 200
        except Exception as e:
            print(f"[Feishu] 推送失败: {e}")
            return False

    def notify_agent_registered(self, agent_id: str, feishu_webhook: str = None) -> bool:
        """通知新节点注册"""
        webhook = feishu_webhook or self.webhook_url
        if not webhook:
            return False

        payload = {
            "msg_type": "text",
            "content": {"text": f"🆕 节点注册: {agent_id}"}
        }

        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
