#!/usr/bin/env python3
"""One-shot Cloudflare MCP OAuth authorization — no more multi-round fumbling.

Encapsulates every lesson from 2026-09-09/10 (lessons/contrib/
cloudflare-observability-mcp-oauth-separate-domain.md and
mcporter-cloudflare-oauth-endpoint-scope-wsl-callback.md):

  * Every CF MCP product has its OWN OAuth authorization server
    (<host>/.well-known/oauth-authorization-server). Discover, never assume
    mcp.cloudflare.com.
  * Explicit dynamic client registration (DCR) on that domain — mcporter's
    implicit DCR silently produced invalid client_ids.
  * No `scope` parameter (CF discovery has no scopes_supported).
  * WSL trap: browser callback to 127.0.0.1 never reaches WSL — this tool prints
    the URL, you authorize, then PASTE the address-bar URL back (code extracted
    automatically, state verified).
  * Token exchange needs a browser User-Agent or CF WAF returns 403/1010.
  * state.txt must be a JSON string literal for mcporter compatibility.

Usage:
  python3 scripts/cf_mcp_auth.py --server cloudflare-observability
  python3 scripts/cf_mcp_auth.py --server cloudflare-observability --reset
  python3 scripts/cf_mcp_auth.py --server cloudflare-observability --refresh
  python3 scripts/cf_mcp_auth.py --server cloudflare-observability --verify

Exit code 0 = authorized & verified (initialize round-trip OK).
"""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCPORTER_JSON = os.path.join(REPO_ROOT, ".tools", "mcporter.json")
DEFAULT_CACHE_ROOT = os.path.join(REPO_ROOT, ".tools", "mcporter-tokens")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def server_config(name: str) -> dict:
    cfg = json.load(open(MCPORTER_JSON))
    servers = cfg.get("mcpServers", {})
    if name not in servers:
        sys.exit(f"Unknown server '{name}'. Known: {', '.join(sorted(servers))}")
    s = servers[name]
    base = s["baseUrl"].rstrip("/")
    if not base.endswith("/mcp"):
        sys.exit(f"baseUrl must end with /mcp: {base}")
    host = urllib.parse.urlsplit(base).netloc
    token_dir = s.get("tokenCacheDir") or os.path.join(DEFAULT_CACHE_ROOT, name)
    return {"name": name, "host": host, "mcp_url": base,
            "dir": os.path.expanduser(token_dir),
            "origin_url": base[: -len("/mcp")]}


def http(method: str, url: str, data=None, headers=None, timeout: int = 40) -> dict:
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", UA)
    if data is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            raw = r.read()
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"_raw": raw.decode("utf-8", "replace")[:500]}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        sys.exit(f"HTTP {e.code} from {url}: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error to {url}: {e.reason}")


def discover(s: dict) -> dict:
    url = f"https://{s['host']}/.well-known/oauth-authorization-server"
    d = http("GET", url)
    need = ("authorization_endpoint", "token_endpoint", "registration_endpoint")
    for k in need:
        if k not in d:
            sys.exit(f"Discovery at {url} missing '{k}': {json.dumps(d)[:300]}")
    return d


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def register_client(s: dict, discovery: dict, redirect_uri: str) -> dict:
    payload = {
        "redirect_uris": [redirect_uri],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "client_name": f"misakanet-cli-{s['name']}",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(discovery["registration_endpoint"], data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"DCR HTTP {e.code}: {e.read().decode('utf-8','replace')[:500]}")


def save_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def load_json(path: str):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", required=True, help="mcporter server name (e.g. cloudflare-observability)")
    ap.add_argument("--reset", action="store_true", help="Clear cached client/tokens and re-authorize")
    ap.add_argument("--refresh", action="store_true", help="Refresh existing access_token (no browser)")
    ap.add_argument("--verify", action="store_true", help="Verify stored token with an MCP initialize call")
    args = ap.parse_args()

    s = server_config(args.server)
    os.makedirs(s["dir"], exist_ok=True)
    client_path = os.path.join(s["dir"], "client.json")
    verifier_path = os.path.join(s["dir"], "code_verifier.txt")
    state_path = os.path.join(s["dir"], "state.txt")
    tokens_path = os.path.join(s["dir"], "tokens.json")

    # ── --verify ────────────────────────────────────────────────
    if args.verify:
        tokens = load_json(tokens_path)
        if not tokens or not tokens.get("access_token"):
            sys.exit("No tokens.json — run authorization first.")
        info = mcp_initialize(s, tokens["access_token"])
        print(f"[ok] token valid — server: {info}")
        return

    # ── --refresh ───────────────────────────────────────────────
    if args.refresh:
        tokens = load_json(tokens_path)
        if not tokens or not tokens.get("refresh_token"):
            sys.exit("No refresh_token — run authorization first.")
        client = load_json(client_path)
        d = exchange_token(s, "refresh_token", {
            "refresh_token": tokens["refresh_token"],
            "client_id": client["client_id"],
        })
        d["expires_at"] = int(time.time()) + int(d.get("expires_in", 3600))
        save_json(tokens_path, d)
        info = mcp_initialize(s, d["access_token"])
        print(f"[ok] refreshed — access_token valid until +{d.get('expires_in')}s — {info}")
        return

    # ── authorization ───────────────────────────────────────────
    discovery = discover(s)
    print(f"[1/5] OAuth discovery: {s['host']} (issuer {discovery.get('issuer')})")

    if args.reset:
        for p in (client_path, verifier_path, state_path, tokens_path):
            if os.path.exists(p):
                os.remove(p)

    redirect_uri = "http://127.0.0.1:40399/callback"  # fixed loopback (DCR-declared)
    client = load_json(client_path)
    if not client or args.reset:
        print(f"[2/5] Dynamic client registration on {discovery['registration_endpoint']} …")
        client = register_client(s, discovery, redirect_uri)
        save_json(client_path, client)
        print(f"      client_id: {client.get('client_id')}")
    else:
        print(f"[2/5] Reusing registered client {client.get('client_id')}")

    verifier = secrets.token_urlsafe(48)
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    state = json.dumps(secrets.token_urlsafe(16))  # JSON string literal (mcporter compat)
    open(verifier_path, "w").write(verifier)
    open(state_path, "w").write(state)

    params = {
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": client.get("redirect_uris", [redirect_uri])[0],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": json.loads(state),
    }
    auth_url = discovery["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)
    print(f"[3/5] Open this URL in your browser and click Allow:")
    print()
    print("      " + auth_url)
    print()
    print("      The redirect to 127.0.0.1 will fail (WSL trap) — that is EXPECTED.")
    print("      Copy the FULL address-bar URL and paste it below:")
    cb = input("      callback URL> ").strip()
    m = re.search(r"[?&]code=([^&]+)", cb)
    if not m:
        sys.exit("No code= found in the pasted URL.")
    code = urllib.parse.unquote(m.group(1))
    sm = re.search(r"[?&]state=([^&]+)", cb)
    if sm and urllib.parse.unquote(sm.group(1)) != json.loads(state):
        sys.exit("State mismatch — pasted URL is from a different session; re-run.")

    print("[4/5] Exchanging authorization code for tokens …")
    d = exchange_token(s, "authorization_code", {
        "code": code,
        "redirect_uri": client.get("redirect_uris", [redirect_uri])[0],
        "client_id": client["client_id"],
        "code_verifier": verifier,
    })
    d["expires_at"] = int(time.time()) + int(d.get("expires_in", 3600))
    save_json(tokens_path, d)
    # keep client/verifier/state consistent on disk for mcporter
    save_json(client_path, client)

    print("[5/5] Verifying with an MCP initialize round-trip …")
    info = mcp_initialize(s, d["access_token"])
    print(f"[ok] AUTHORIZED — {info}")
    print(f"     tokens: {tokens_path}")
    print("     refresh later with: python3 scripts/cf_mcp_auth.py --server %s --refresh" % s["name"])


def exchange_token(s: dict, grant: str, fields: dict) -> dict:
    discovery = discover(s)
    body = urllib.parse.urlencode({"grant_type": grant, **fields}).encode()
    return http("POST", discovery["token_endpoint"], data=body)


def mcp_initialize(s: dict, access_token: str) -> str:
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "misakanet-cf-cli", "version": "1.0"}},
    }
    req = urllib.request.Request(s["mcp_url"], data=json.dumps(payload).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        sys.exit(f"MCP initialize HTTP {e.code}: {e.read().decode('utf-8','replace')[:400]}")
    for line in raw.splitlines():
        if line.startswith("data: "):
            d = json.loads(line[6:])
            if "error" in d:
                sys.exit(f"MCP error: {json.dumps(d['error'])[:300]}")
            si = d.get("result", {}).get("serverInfo", {})
            return f"{si.get('name')} {si.get('version')} — token ACCEPTED"
    sys.exit(f"MCP initialize returned no data. Raw: {raw[:300]}")


if __name__ == "__main__":
    main()
