#!/usr/bin/env bash
set -euo pipefail

workdir=${1:?usage: setup.sh WORKDIR}
rm -rf -- "$workdir"
mkdir -p "$workdir"
cat > "$workdir/server.py" <<'PY'
import json
import sys

request = json.loads(sys.stdin.read())
if request.get("jsonrpc") != "2.0":
    raise ValueError("invalid JSON-RPC request")
print(json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": {}}))
PY
printf '%s\n' '{"jsonrpc": "2.0",' > "$workdir/invalid-input.json"
printf '%s\n' '{"jsonrpc": "2.0", "id": 1, "method": "initialize"}' > "$workdir/valid-input.json"
