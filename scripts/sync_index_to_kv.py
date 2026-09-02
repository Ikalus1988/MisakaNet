#!/usr/bin/env python3
"""Sync BM25 search index to Worker KV.

This script reads the pre-computed index from a JSON file and
uploads it to the Cloudflare Worker's KV store.

Usage:
    python scripts/sync_index_to_kv.py --index data/worker-index.json

Environment variables:
    SYNC_TOKEN: Authentication token for the sync endpoint
    WORKER_URL: Worker URL (default: https://misakanet.dev)
"""

import argparse
import json
import os
import sys
from pathlib import Path

import urllib.request


def sync_index(index_path: str, worker_url: str, sync_token: str) -> dict:
    """Sync index to Worker KV."""
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    if not index.get("version") or not index.get("terms") or not index.get("docs"):
        raise ValueError("Invalid index format")

    url = f"{worker_url}/api/search-index"
    data = json.dumps(index).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Sync-Token": sync_token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else str(e)
        raise RuntimeError(f"HTTP {e.code}: {error_body}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync BM25 search index to Worker KV"
    )
    parser.add_argument(
        "--index",
        required=True,
        help="Path to index JSON file",
    )
    parser.add_argument(
        "--worker-url",
        default=os.environ.get("WORKER_URL", "https://misakanet.dev"),
        help="Worker URL (default: WORKER_URL env or https://misakanet.dev)",
    )
    parser.add_argument(
        "--sync-token",
        default=os.environ.get("SYNC_TOKEN"),
        help="Sync token (default: SYNC_TOKEN env)",
    )
    args = parser.parse_args()

    if not args.sync_token:
        print("Error: SYNC_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    print(f"Syncing index from {args.index}...")
    result = sync_index(args.index, args.worker_url, args.sync_token)

    print(f"Success! {result['docCount']} documents, {result['termCount']} terms")


if __name__ == "__main__":
    main()
