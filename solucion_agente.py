import asyncio
import json
import sys
from http import HTTPStatus
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    sys.exit("Error: httpx is required. Install it via: pip install httpx")

MCP_ENDPOINT = "https://misakanet.org/mcp"


class MisakaNetMCPTool:
    def __init__(self, token: str = None, timeout: int = 30):
        self.token = token
        self.timeout = timeout
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"


    def _build_json_rpc_payload(self, method: str, params: dict = None, req_id: int = 1) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method
        } | {"params": params} if params else {}


    def _process_response(self, response: httpx.Response) -> dict:
        if response.status_code == 401 and "misakanet_register" not in response.text:
            raise PermissionError("Required token is missing or invalid. Please call 'misakanet_register'.")
        if response.is_error:
            raise RuntimeResponseError(
                f"Request failed with status {response.status_code}: {response.text}"
            )
            
        content_type = response.headers.get("content-type", "")
        
        if "application/json" in content_type:
            return response.json()
        
        elif "text/event-stream" in content_type:
            return self._parse_sse(response.text)
        else:
            # Fallback to raw text if it looks like JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"result": response.text}


    def _parse_sse(self, text: str) -> dict:
        # Basic SSE parsing to find the first JSON-RPC result
        lines = text.splitlines()
        for line in lines:
            if line.startswith("data: "):
                payload = line[6:]
                if payload and payload != "[DONE]":
                    try:
                        return json.loads(payload)
                    except json.JSONDecodeError:
                        continue
        return {"error": "Failed to parse Server-Sent Events"}


    def register_agent(self, agent_type: str = "claude-code") -> str:
        # Register returns a token. Handle response carefully.
        req_id = 1
        payload = self._build_json_rpc_payload(
            "tools/call", 
            {
                "name": "misakanet_register", 
                "arguments": {"agent_type": agent_type}
            },
            req_id
        )
        
        async def reg_helper():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(MCP_ENDPOINT, json=payload, headers=self._headers)
                data = self._process_response(resp)
                # Usually the token is in result.content or result.token
                return data
        
        result_data = asyncio.run(reg_helper())
        
        # Extract token from the nested JSON structure
        # Standard MCP structure: { "result": { "content": [ { "text": "{\"token\": \"...\"}" } ] } }
        # Or directly in result if adapted.
        try:
            content_list = result_data["result"]["content"]
            if not content_list:
                return ""
            # Find the first text object
            for item in content_list:
                if item.get("type") == "text":
                    text_content = item["text"]
                    # Try to parse the text as JSON to get the token
                    try:
                        parsed = json.loads(text_content)
                        if isinstance(parsed, dict) and "token" in parsed:
                            return parsed["token"]
                    except json.JSONDecodeError:
                        # If not JSON, maybe the text IS the token string
                        return text_content.strip()
        except (KeyError, IndexError, TypeError):
            pass
        return ""


    def update_token(self, token: str):
        self.token = token
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        else:
            self._headers.pop("Authorization", None)


    def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        async def call_helper():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                req_id = 1
                payload = self._build_json_rpc_payload(
                    "tools/call", 
                    {"name": tool_name, "arguments": arguments or {}},
                    req_id
                )
                resp = await client.post(MCP_ENDPOINT, json=payload, headers=self._headers)
                return self._process_response(resp)
            
        return asyncio.run(call_helper())


    def search_lessons(self, query: str) -> list:
        data = self.call_tool("misakanet_search", {"query": query})
        return self._extract_content(data)


    def get_lesson(self, lesson_id: str) -> dict:
        data = self.call_tool("misakanet_get_lesson", {"id": lesson_id})
        return self._extract_content(data)


    def submit_intake(self, agent_type: str = "web", failure_description: str = "", error_log: str = "") -> dict:
        args = {
            "agent_type": agent_type,
            "failure_description": failure_description,
            "error_log": error_log
        }
        data = self.call_tool("misakanet_submit_intake", args)
        return self._extract_content(data)


    def write_lesson(self, title: str, body: str, tags: list = None, error_context: str = "") -> dict:
        args = {
            "title": title,
            "body": body,
            "tags": tags or [],
            "error_context": error_context
        }
        data = self.call_tool("misakanet_write_lesson", args)
        return self._extract_content(data)


    def preflight_check(self, command: str) -> bool:
        data = self.call_tool("misakanet_preflight", {"command": command})
        extracted = self._extract_content(data)
        # Pre-flight returns a risk assessment. 
        # Let's assume if it returns content, it's a success and we can parse status.
        # Specific logic depends on server schema. 
        # Default: return the raw extracted data for the agent to interpret, 
        # or specific boolean if 'safe' is found.
        
        if isinstance(extracted, dict):
            return extracted.get("is_safe", extracted.get("status") == "safe")
        return True


    def list_tools(self) -> list:
        # Tools/list: list available tools
        payload = self._build_json_rpc_payload("tools/list", {}, 1)
        async def list_helper():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(MCP_ENDPOINT, json=payload, headers=self._headers)
                return self._process_response(resp)
        data = asyncio.run(list_helper())
        
        tools = []
        if "result" in data and "tools" in data["result"]:
            tools = data["result"]["tools"]
        elif "tools" in data:
            tools = data["tools"]
        return tools


    def _extract_content(self, data: dict) -> any:
        """Extracts the actual content from MCP tool response structures."""
        if not data:
            return None
        
        # Standard MCP structure: result.content[0].text
        if "result" in data:
            res = data["result"]
            if isinstance(res, dict) and "content" in res:
                content = res["content"]
                # If only one item, return it
                if len(content) == 1:
                    item = content[0]
                    if item.get("type") == "text":
                        text = item["text"]
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return text
                    return item
                return content
            
            # Some servers might put data directly elsewhere
            if "text" in res:
                return res["text"]
            return res
        
        # Direct data
        return data


class RuntimeResponseError(Exception):
    pass


# CLI Implementation
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="MisakaNet MCP Server CLI Client")
    subparsers = parser.add_subparsers(dest="command")

    # register
    p_reg = subparsers.add_parser("register", help="Register agent and get token")
    p_reg.add_argument("--type", default="claude-code", help="Agent type")

    # search
    p_search = subparsers.add_parser("search", help="Search lessons")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--token", required=True, help="Auth token")

    # get
    p_get = sub