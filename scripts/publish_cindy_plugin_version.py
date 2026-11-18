#!/usr/bin/env python3
"""Publish the plugin's current versions into the endpoint's KV (`cindy:plugin:latest`).

Why this exists
---------------
The endpoint answers "is the caller behind?" by comparing the version the plugin reports
(`X-MisakaNet-Version`) against **the version the marketplace currently serves** — see
`Ikalus1988/MisakaNet#5185` (endpoint half: `workers/cindy-plugin-version.test.mjs`). The endpoint
can only know that second number if someone tells it, and the only party that knows is whoever
publishes the plugin. So the value is written **once per published plugin version**, from here.

**The value is the marketplace's version, not the repository's.** While a review runs, the
repository's manifest is ahead of the marketplace; writing that number would nag users who are
current. (That is the endpoint's own reasoning, and the reason it has no compiled-in default.)

The value lives in KV rather than in the worker source so that publishing a version does not need
a redeploy: `wrangler kv key put` on the `MISAKANET_KV` binding.

    python scripts/publish_cindy_plugin_version.py            # publish data/cindy-plugin-versions.json
    python scripts/publish_cindy_plugin_version.py --dry-run  # print what would be written
    python scripts/publish_cindy_plugin_version.py --community 1.5.12

**Forgetting to run this is not a defect.** The endpoint then has no version to compare against
and stays silent about versions; the plugin says nothing either (that is the designed behaviour,
not a bug). It only means nobody is told they are behind until the next write.

Files
-----
- `data/cindy-plugin-versions.json` — the source of truth: what each channel's marketplace
  currently serves. `community` is the community-submission channel (1.5.x), `official` the
  platform-signed one (1.6.x, empty until it is published).
- `workers/wrangler.toml` — holds the `MISAKANET_KV` binding this script writes through.

Requires: `wrangler` (npm), the Cloudflare account that owns the endpoint, and an outbound proxy
on 127.0.0.1:7890 (the CF API is not reachable directly from this network).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSIONS_FILE = REPO / "data" / "cindy-plugin-versions.json"
WRANGLER_CONFIG = REPO / "workers" / "wrangler.toml"
KV_KEY = "cindy:plugin:latest"
KV_BINDING = "MISAKANET_KV"
PROXY = "http://127.0.0.1:7890"


def wrangler_command(explicit: str = "") -> list[str]:
    """The wrangler CLI to call.

    The repository's own `node_modules` is what CI uses; on a machine where it was installed on
    POSIX it cannot run on Windows (`workerd-linux-64` vs `workerd-windows-64`), so this script is
    meant to be run on POSIX (WSL counts). `--wrangler` overrides the path.
    """
    if explicit:
        return explicit.split()
    local = REPO / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    if local.exists():
        node = shutil.which("node") or "node"
        return [node, str(local)]
    return ["npx", "wrangler"]


def wrangler_env() -> dict:
    """The environment wrangler needs: the proxy, and the OAuth config when running in WSL.

    On WSL the Windows config directory is not where wrangler looks (`~/.wrangler` inside the
    distro), so point XDG_CONFIG_HOME at the Windows one — that is where the account's OAuth
    token lives.
    """
    env = dict(os.environ)
    env.setdefault("HTTPS_PROXY", PROXY)
    env.setdefault("HTTP_PROXY", PROXY)
    if not env.get("XDG_CONFIG_HOME"):
        windows_config = Path("/mnt/c/Users") if os.path.exists("/mnt/c/Users") else None
        if windows_config is not None:
            for candidate in Path("/mnt/c/Users").glob("*/AppData/Roaming/xdg.config"):
                if (candidate / ".wrangler" / "config" / "default.toml").exists():
                    env["XDG_CONFIG_HOME"] = str(candidate)
                    break
    return env


def load_versions(args: argparse.Namespace) -> dict:
    if args.community or args.official:
        base = json.loads(VERSIONS_FILE.read_text(encoding="utf-8")) if VERSIONS_FILE.exists() else {}
        return {
            "community": args.community or base.get("community", ""),
            "official": args.official or base.get("official", ""),
        }
    if not VERSIONS_FILE.exists():
        print(f"error: {VERSIONS_FILE} does not exist", file=sys.stderr)
        raise SystemExit(2)
    raw = json.loads(VERSIONS_FILE.read_text(encoding="utf-8"))
    # Only the two version lines go into KV. The file's prose (`note`, `updated_at`) is for
    # readers in the repository; the endpoint reads `versions[channel]` and nothing else.
    return {"community": raw.get("community", ""), "official": raw.get("official", "")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--community", help="override the community channel version")
    parser.add_argument("--official", help="override the official channel version")
    parser.add_argument("--dry-run", action="store_true", help="print the value, write nothing")
    parser.add_argument("--wrangler", default="", help="explicit wrangler command (path or command line)")
    args = parser.parse_args(argv)

    versions = load_versions(args)
    if not versions.get("community"):
        print("error: the community channel version must be set", file=sys.stderr)
        return 2
    # The official channel may legitimately be empty (nothing published there yet): the endpoint
    # then stays silent for that channel, which is a correct answer.
    payload = json.dumps(versions, ensure_ascii=False, sort_keys=True)

    if args.dry_run:
        print(f"would write {KV_KEY} = {payload}")
        return 0

    env = wrangler_env()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        handle.write(payload)
        temp_path = handle.name
    try:
        done = subprocess.run(
            wrangler_command(args.wrangler)
            + [
                "kv", "key", "put", KV_KEY,
                "--binding=" + KV_BINDING,
                "--remote",
                "--path", temp_path,
                "--config", str(WRANGLER_CONFIG),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300,
        )
    finally:
        os.unlink(temp_path)
    if done.returncode != 0:
        print("error: wrangler kv key put failed", file=sys.stderr)
        print(done.stdout[-2000:], file=sys.stderr)
        print(done.stderr[-2000:], file=sys.stderr)
        if "workerd" in (done.stderr or "") and "platform" in (done.stderr or ""):
            print(
                "\nhint: this checkout's node_modules holds a POSIX-built wrangler. Run it on POSIX:\n"
                "  wsl -e bash -lc 'cd \"/mnt/c/Users/Eric Jia/MisakaNet\" && python3 scripts/publish_cindy_plugin_version.py'\n"
                "or point --wrangler at a Windows-usable wrangler.",
                file=sys.stderr,
            )
        return 1
    print(f"wrote {KV_KEY} = {payload}")

    # Read it back: a write that silently did nothing is the failure mode this guards against.
    back = subprocess.run(
        wrangler_command(args.wrangler)
        + ["kv", "key", "get", KV_KEY, "--binding=" + KV_BINDING, "--remote",
           "--config", str(WRANGLER_CONFIG)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300,
    )
    if back.returncode != 0:
        print("warning: could not read the value back", file=sys.stderr)
        print(back.stderr[-1500:], file=sys.stderr)
        return 1
    print("read back:", back.stdout.strip()[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
