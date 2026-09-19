"""`misakanet "<error text>"` — the CLI an *installed* package can actually run.

`pyproject.toml` used to declare `misakanet = "search_knowledge:main"`, a module that is not in the
wheel, so the command exited with `ModuleNotFoundError` (2026-09-18 review, 意见 1; #1821). This module
lives in the package and searches the **remote** endpoint, because the in-package engine needs a repo
checkout for its corpus — a wheel has no `lessons/`.

    misakanet "database is locked"          # search by the error text you actually see
    misakanet --top 3 --json "ECONNREFUSED"
    MISAKANET_TOKEN=mcp_… misakanet "…"     # a token lifts the anonymous limits
    MISAKANET_CLIENT_ID=<stable-id> …       # keeps one client's history together (not a credential)

Argparse rather than a hand-rolled `sys.argv` walk: 意见 4 of the same review asked for it, and a new
entry point is the cheap place to start.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from misakanet.remote import RemoteError, search

EXIT_OK = 0
EXIT_NO_MATCH = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="misakanet",
        description="Search MisakaNet failure lessons by the error text you are looking at.",
        epilog="Reading needs no account. A token (env MISAKANET_TOKEN) lifts the anonymous limits and "
               "unlocks the write tools; MISAKANET_CLIENT_ID is a self-declared pseudonym, not a credential.",
    )
    parser.add_argument("query", help="the most distinctive fragment of the error text")
    parser.add_argument("--top", type=int, default=5, help="how many lessons to show (default 5)")
    parser.add_argument("--json", action="store_true", help="print the endpoint's payload as JSON")
    parser.add_argument("--token", default=os.environ.get("MISAKANET_TOKEN", ""),
                        help="Bearer token (defaults to $MISAKANET_TOKEN)")
    parser.add_argument("--client-id", default=os.environ.get("MISAKANET_CLIENT_ID", ""),
                        help="stable pseudonym for this client (defaults to $MISAKANET_CLIENT_ID)")
    parser.add_argument("--endpoint", default=os.environ.get("MISAKANET_ENDPOINT", ""),
                        help="override the endpoint (defaults to $MISAKANET_ENDPOINT or misakanet.org/mcp)")
    return parser


def _results(payload: dict) -> list:
    for key in ("results", "lessons", "matches"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = search(args.query, top=args.top, token=args.token, client_id=args.client_id,
                         endpoint_url=args.endpoint)
    except RemoteError as exc:
        # An unreachable endpoint is not "no results": say which one it was, and keep the exit code
        # distinct so a script can tell the difference (same 0/1/2 discipline as the installer).
        print(f"misakanet: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    results = _results(payload)
    if not results:
        kind = payload.get("no_match") or payload.get("kind") or "no_match"
        print(f"no matching lesson ({kind})", file=sys.stderr)
        if not args.json:
            print("→ if this is a gap worth recording, submit it: "
                  "misakanet_submit_intake(kind=\"missing_lesson\"|\"question\")", file=sys.stderr)
        return EXIT_NO_MATCH

    if not args.json:
        for index, item in enumerate(results, 1):
            title = item.get("title") or item.get("id") or "(untitled)"
            path = item.get("path") or item.get("id") or ""
            score = item.get("score")
            suffix = f"  [{score:.3f}]" if isinstance(score, (int, float)) else ""
            print(f"{index}. {title}{suffix}")
            if path:
                print(f"   {path}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
