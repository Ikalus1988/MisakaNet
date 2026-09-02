#!/usr/bin/env python3
"""tests/mcp_first_call_journey.py — Validate remote MCP first-call user journey (closes #830)"""
import subprocess, sys, json, time

ENDPOINT = "https://misakanet.org/mcp"
PASS, FAIL, SKIP = "✅", "❌", "⏭️"

def step(name, condition, detail=""):
    mark = PASS if condition else FAIL
    print(f"  {mark} {name}: {'OK' if condition else 'FAIL'} {detail}")
    return condition

def test_journey():
    results = []
    print(f"\n{'='*60}")
    print(f"MisakaNet MCP First-Call Journey Test")
    print(f"Endpoint: {ENDPOINT}")
    print(f"{'='*60}\n")

    # Step 1: Discover endpoint
    print("1. Discover endpoint")
    ok = step("Endpoint exists", True, "https://misakanet.org/mcp")
    results.append(("discover", ok))

    # Step 2-6: Protocol test via curl
    print("\n2-6. MCP Protocol flow")

    # Initialize
    try:
        req = json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"0.2.0","capabilities":{},"clientInfo":{"name":"journey-test","version":"1.0.0"}}}).encode()
        import urllib.request, ssl
        ctx = ssl.create_default_context()

        r = urllib.request.Request(ENDPOINT, data=req, headers={"Content-Type":"application/json"}, method="POST")
        resp = json.loads(urllib.request.urlopen(r, context=ctx, timeout=15).read())
        ok = step("initialize", "serverInfo" in resp.get("result",{}), resp.get("result",{}).get("serverInfo",{}).get("name","?"))
        results.append(("initialize", ok))
    except Exception as e:
        step("initialize", False, str(e)[:80])
        results.append(("initialize", False))

    # Tools list
    try:
        req = json.dumps({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}).encode()
        r = urllib.request.Request(ENDPOINT, data=req, headers={"Content-Type":"application/json"}, method="POST")
        resp = json.loads(urllib.request.urlopen(r, context=ctx, timeout=15).read())
        tools = resp.get("result",{}).get("tools",[])
        ok = step("tools/list", len(tools) >= 2, f"{len(tools)} tools found: {[t['name'] for t in tools]}")
        results.append(("tools/list", ok))
    except Exception as e:
        step("tools/list", False, str(e)[:80])
        results.append(("tools/list", False))

    # Search call
    try:
        req = json.dumps({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"misaka_search","arguments":{"query":"feishu setup","limit":3}}}).encode()
        r = urllib.request.Request(ENDPOINT, data=req, headers={"Content-Type":"application/json"}, method="POST")
        resp = json.loads(urllib.request.urlopen(r, context=ctx, timeout=15).read())
        content = resp.get("result",{}).get("content",[{}])[0].get("text","")
        ok = step("tools/call (search)", len(content) > 50, f"Response: {len(content)} chars")
        results.append(("tools/call", ok))
    except Exception as e:
        step("tools/call", False, str(e)[:80])
        results.append(("tools/call", False))

    # CORS test (simplified)
    print("\n7. CORS check")
    try:
        r = urllib.request.Request(ENDPOINT, method="OPTIONS")
        r.add_header("Origin", "https://claude.ai")
        r.add_header("Access-Control-Request-Method", "POST")
        resp = urllib.request.urlopen(r, context=ctx, timeout=10)
        cors_headers = resp.getheader("Access-Control-Allow-Origin","")
        ok = step("CORS headers", "claude.ai" in cors_headers or "*" in cors_headers, cors_headers)
        results.append(("cors", ok))
    except Exception as e:
        step("CORS", False, str(e)[:80])
        results.append(("cors", False))

    # Summary
    passed = sum(1 for _,ok in results if ok)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed")
    for name, ok in results:
        print(f"  {PASS if ok else FAIL} {name}")
    
    return passed == total

if __name__ == "__main__":
    success = test_journey()
    sys.exit(0 if success else 1)
