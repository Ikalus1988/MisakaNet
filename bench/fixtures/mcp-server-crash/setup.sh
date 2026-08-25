#!/bin/bash
# MCP Server Crash Fixture Setup
# Creates an invalid JSON input that crashes an MCP server

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${FIXTURE_DIR}/work"

# Clean up any previous run
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"

# Create a minimal MCP server that crashes on invalid JSON
cat > mcp_server.py << 'EOF'
#!/usr/bin/env python3
"""Minimal MCP server that crashes on invalid JSON input."""

import json
import sys

def handle_request(request_json: str) -> dict:
    """Parse and handle a JSON-RPC request."""
    # This will raise JSONDecodeError on invalid JSON
    request = json.loads(request_json)
    
    # Simulate processing
    method = request.get("method", "")
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {"tools": []}
        }
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "error": {"code": -32601, "message": "Method not found"}
    }

if __name__ == "__main__":
    # Read request from stdin
    request_data = sys.stdin.read()
    try:
        response = handle_request(request_data)
        print(json.dumps(response))
    except json.JSONDecodeError as e:
        # Crash with error
        print(f"FATAL: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
EOF

chmod +x mcp_server.py

# Create invalid JSON input (missing closing brace)
cat > invalid_request.json << 'EOF'
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "id": 1
EOF

# Create valid JSON input for comparison
cat > valid_request.json << 'EOF'
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "id": 1
}
EOF

echo "Setup complete. Running: cat invalid_request.json | python mcp_server.py will crash."
