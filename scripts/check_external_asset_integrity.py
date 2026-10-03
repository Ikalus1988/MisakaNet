#!/usr/bin/env python3
"""Do the bytes we pinned still hash to what we declared?

    python3 scripts/check_external_asset_integrity.py            # every registered asset
    python3 scripts/check_external_asset_integrity.py --id dompurify
    python3 scripts/check_external_asset_integrity.py --json

**The offline test cannot see this.** `tests/test_external_asset_integrity.py` proves the markup and
`data/external_assets.json` agree with each other — a consistent, wrong pair passes it. What only a
network call can answer is whether the CDN is still serving the bytes that pair describes, which is
the supply-chain case: an asset republished in place, a mirror serving something else, a
compromised CDN. Subresource Integrity turns that into a *blocked script*, so the failure the user
sees is a page that stops sanitising rather than a silent hole — which is the right direction and
still an outage worth knowing about on Monday rather than on Monday afternoon.

Exit `1` on any mismatch, printing the declared hash, the computed one, and the byte length. A
version that 404s is a mismatch too: an unreachable asset is an asset that will not load.

Deliberately *not* a test. A test that reaches the network is a test that goes red when the network
goes away — and this repository has already spent three rounds learning that a gate people cannot
satisfy gets deleted rather than fixed. `external-asset-integrity.yml` runs this weekly and
`workflow_dispatch` runs it on demand.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "data" / "external_assets.json"
TIMEOUT = 60


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["assets"]


def sri_for(payload: bytes) -> str:
    """The `integrity` value for these bytes, in the form the attribute uses."""
    return "sha384-" + base64.b64encode(hashlib.sha384(payload).digest()).decode("ascii")


def fetch(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "misakanet-external-asset-integrity", "Accept": "*/*"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def check(asset: dict) -> dict:
    """One asset, and one honest verdict. Never raises for a network problem."""
    result = {"id": asset["id"], "url": asset["url"], "declared": asset["integrity"]}
    try:
        payload = fetch(asset["url"])
    except urllib.error.HTTPError as error:
        return {**result, "ok": False, "why": f"HTTP {error.code}"}
    except urllib.error.URLError as error:
        return {**result, "ok": False, "why": f"unreachable: {error.reason}"}
    computed = sri_for(payload)
    result["computed"] = computed
    result["bytes"] = len(payload)
    result["ok"] = computed == asset["integrity"]
    if not result["ok"]:
        result["why"] = "the CDN is not serving the bytes we pinned"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", help="check one asset by id")
    parser.add_argument("--json", action="store_true", help="machine-readable")
    args = parser.parse_args(argv)

    assets = load_manifest()
    if args.id:
        assets = [a for a in assets if a["id"] == args.id]
        if not assets:
            print(f"no asset with id {args.id!r} in {MANIFEST.name}", file=sys.stderr)
            return 2

    results = [check(asset) for asset in assets]
    if args.json:
        print(json.dumps(results, indent=2))
        return 0 if all(r["ok"] for r in results) else 1

    failed = [r for r in results if not r["ok"]]
    for result in results:
        if result["ok"]:
            print(f"OK   {result['id']}: {result['computed']} ({result['bytes']} bytes)")
        else:
            print(f"FAIL {result['id']}: {result.get('why')}", file=sys.stderr)
            print(f"     url      {result['url']}", file=sys.stderr)
            print(f"     declared {result['declared']}", file=sys.stderr)
            if "computed" in result:
                print(f"     computed {result['computed']} ({result['bytes']} bytes)",
                      file=sys.stderr)
    print(f"\n{len(results) - len(failed)}/{len(results)} external assets match their pinned hash")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
