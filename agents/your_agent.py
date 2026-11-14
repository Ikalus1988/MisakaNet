"""
MisakaNet reference agent (`agents/your_agent.py`) wired with MCP JSON-RPC 2.0
failure-memory support (`https://misakanet.org/mcp`, protocol `2025-06-18`).

Maintains full backward compatibility with `YourAgent(name)`, `run(task, lesson=None)`,
and `get_lesson(result)` while providing production-grade MCP registration,
search-before-write deduplication, intake submission, and lesson creation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

DEFAULT_MCP_URL = "https://misakanet.org/mcp"
MCP_PROTOCOL_VERSION = "2025-06-18"


@dataclass(frozen=True)
class MCPJsonRpcRequest:
    id: int
    tool_name: str
    arguments: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": self.id,
            "method": "tools/call",
            "params": {
                "name": self.tool_name,
                "arguments": self.arguments,
            },
        }


class YourAgent:
    def __init__(
        self,
        name: str,
        mcp_url: str = DEFAULT_MCP_URL,
        version: str = "1.0",
        transport: Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]] | None = None,
    ):
        self.name = name
        self.version = version
        self.mcp_url = mcp_url
        self.lessons: dict[str, Any] = {}
        self.node_id: str | None = None
        self.token: str | None = None
        self._rpc_id = 0
        self._transport = transport or self._default_http_transport

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    @staticmethod
    def _default_http_transport(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    def _call_mcp_tool(self, tool_name: str, arguments: dict[str, Any], require_auth: bool = False) -> dict[str, Any]:
        rpc_req = MCPJsonRpcRequest(id=self._next_id(), tool_name=tool_name, arguments=arguments)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "User-Agent": f"MisakaNet-Agent/{self.name}",
        }
        if require_auth:
            if not self.token:
                raise RuntimeError("MCP tool requires bearer token; call register_mcp() first")
            headers["Authorization"] = f"Bearer {self.token}"
        return self._transport(self.mcp_url, rpc_req.to_payload(), headers)

    def register_mcp(self) -> dict[str, Any]:
        resp = self._call_mcp_tool(
            "misakanet_register",
            {"name": self.name, "version": self.version},
        )
        result = resp.get("result", resp)
        if isinstance(result, dict):
            self.token = result.get("token") or self.token
            self.node_id = result.get("node_id") or self.node_id
        return resp

    def search_mcp(self, query: str, detail: str = "summary", top: int = 5) -> dict[str, Any]:
        resp = self._call_mcp_tool(
            "misakanet_search",
            {"query": query, "detail": detail, "top": top},
        )
        self.lessons[query] = resp
        return resp

    def submit_intake_mcp(self, problem: str, kind: str = "missing_lesson", source: str = "agent") -> dict[str, Any]:
        return self._call_mcp_tool(
            "misakanet_submit_intake",
            {"problem": problem, "kind": kind, "source": source},
        )

    def write_lesson_mcp(
        self,
        title: str,
        problem: str,
        fix: str,
        verification: str,
        domain: str = "general",
    ) -> dict[str, Any]:
        return self._call_mcp_tool(
            "misakanet_write_lesson",
            {
                "title": title,
                "problem": problem,
                "fix": fix,
                "verification": verification,
                "domain": domain,
            },
            require_auth=True,
        )

    def run(self, task: str, lesson: Any = None) -> str:
        if lesson:
            print(f"Running {task} with lesson: {lesson}")
            return "success"
        print(f"Running {task} without any prior knowledge")
        return "failure"

    def get_lesson(self, result: Any) -> str | None:
        if result == "success":
            return f"Lesson learned from {result}"
        if isinstance(result, dict) and result.get("title") and result.get("fix"):
            return f"{result['title']}: {result['fix']}"
        return None


if __name__ == "__main__":
    agent = YourAgent("YourAgent")
    result = agent.run("Task A")
    lesson = agent.get_lesson(result)
    result = agent.run("Task B", lesson=lesson)
    print(f"Final result: {result}")
