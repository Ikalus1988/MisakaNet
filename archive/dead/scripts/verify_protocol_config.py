#!/usr/bin/env python3
"""Validate misaka-protocol.json structure."""
import json, sys
try:
    r = json.load(open("misaka-protocol.json"))
    assert "nodes" in r
    assert "ecosystem" in r
    count = r["nodes"]["current_count"]
    print(f"OK: {count} nodes, config valid")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
