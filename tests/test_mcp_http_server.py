"""Exercise the HTTP CLI against the installed MCP SDK over a real loopback socket."""

import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from mcp import Client

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_http_cli_serves_tools_resources_and_prompts_on_requested_port(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    log_path = tmp_path / "http-server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "scripts/mcp_http_server.py",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                assert process.poll() is None, log_path.read_text()
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise AssertionError(f"HTTP server did not start: {log_path.read_text()}")

            async def exercise() -> None:
                async with Client(
                    f"http://127.0.0.1:{port}/mcp",
                    read_timeout_seconds=5,
                ) as client:
                    tools = await client.list_tools()
                    assert {tool.name for tool in tools.tools} == {
                        "misakanet_search",
                        "misakanet_get_lesson",
                        "misakanet_submit_usage",
                        "misakanet_submit_intake",
                        "misakanet_usage_status",
                        "misakanet_register",
                    }
                    result = await client.call_tool("misakanet_search", {"query": ""})
                    assert not result.is_error
                    assert json.loads(result.content[0].text)["error"] == "query is required"
                    resources = await client.list_resources()
                    assert {resource.uri for resource in resources.resources} == {
                        "misaka://lessons/index",
                        "misaka://protocol/overview",
                        "misaka://docs/readme",
                    }
                    prompts = await client.list_prompts()
                    assert {prompt.name for prompt in prompts.prompts} == {
                        "search_lesson",
                        "triage_failure",
                    }

            asyncio.run(exercise())
        finally:
            process.terminate()
            process.wait(timeout=5)
