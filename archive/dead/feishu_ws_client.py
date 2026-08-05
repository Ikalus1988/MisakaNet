"""
Feishu WebSocket Client - 飞书长连接客户端
使用 WebSocket 接收飞书消息并处理回调
"""
import asyncio
import json
import websocket
import threading
from typing import Callable, Optional


class FeishuWSClient:
    """
    飞书 WebSocket 长连接客户端
    建立持久连接，接收消息并触发回调
    """

    def __init__(self, app_id: str, app_secret: str, verification_token: str = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.ws = None
        self.running = False
        self.callbacks = {}
        self._receive_thread = None

    def register_callback(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        self.callbacks[event_type] = handler

    def _get_websocket_url(self) -> str:
        """获取 WebSocket 连接 URL"""
        return "wss://open.feishu.cn/open-apis/bot/v2/ws"

    def _get_token(self) -> str:
        """获取 tenant_access_token"""
        import requests
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tenant_access_token", "")
        return ""

    def start(self):
        """启动 WebSocket 连接"""
        if self.running:
            return
        self.running = True
        self._receive_thread = threading.Thread(target=self._run_ws, daemon=True)
        self._receive_thread.start()
        print("[FeishuWS] 长连接已启动")

    def _run_ws(self):
        """运行 WebSocket 客户端"""
        while self.running:
            try:
                token = self._get_token()
                if not token:
                    print("[FeishuWS] 获取 token 失败，5秒后重试")
                    threading.Event().wait(5)
                    continue

                ws_url = self._get_websocket_url()

                self.ws = websocket.WebSocketApp(
                    ws_url,
                    header=[f"Authorization: Bearer {token}"],
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open
                )

                self.ws.run_forever(ping_interval=30)
            except Exception as e:
                print(f"[FeishuWS] 连接异常: {e}")

            if self.running:
                print("[FeishuWS] 5秒后重连...")
                threading.Event().wait(5)

    def _on_open(self, ws):
        print("[FeishuWS] WebSocket 连接已建立")

    def _on_message(self, ws, message):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            event = data.get("event", {})
            event_type = event.get("type") or data.get("schema")

            if event_type == "im.message.receive_v1":
                self._handle_message(event)
            elif event_type == "p2p_card_action.trigger":
                self._handle_card_action(event)
            else:
                print(f"[FeishuWS] 收到事件: {event_type}")

        except json.JSONDecodeError:
            print(f"[FeishuWS] 消息解析失败: {message[:100]}")

    def _handle_message(self, event: dict):
        """处理飞书消息"""
        handler = self.callbacks.get("message")
        if handler:
            try:
                handler(event)
            except Exception as e:
                print(f"[FeishuWS] 消息处理异常: {e}")

    def _handle_card_action(self, event: dict):
        """处理卡片点击"""
        handler = self.callbacks.get("card_action")
        if handler:
            try:
                handler(event)
            except Exception as e:
                print(f"[FeishuWS] 卡片处理异常: {e}")

    def _on_error(self, ws, error):
        print(f"[FeishuWS] WebSocket 错误: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print(f"[FeishuWS] 连接关闭: {close_status_code} {close_msg}")

    def stop(self):
        """停止连接"""
        self.running = False
        if self.ws:
            self.ws.close()
        print("[FeishuWS] 长连接已停止")

    def send_text(self, receive_id: str, content: str):
        """发送文本消息"""
        import requests
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json"
        }
        payload = {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": content})
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.status_code == 200
