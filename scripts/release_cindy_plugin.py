#!/usr/bin/env python3
"""Prepare a Cindy plugin release: one command instead of five, and it refuses to lie.

Why this exists
---------------
Publishing the community-channel plugin used to be a five-step manual dance, every time:
build the `.cindy` package → sign it with the publisher key → build it again so the package
carries the signature → install it → `prepare` → `submit`. Every step was a chance to ship the
wrong bytes (sign the package, then change the source, and the signature no longer matches), and
the sign step in particular has three arguments that are easy to get wrong.

This script does everything up to the point where the host tools take over, and it refuses to
proceed when anything is inconsistent:

1. the two channels must still differ in exactly three places (the builder's own contract);
2. the version being released must be the one in the manifest **and** the one the builder
   publishes for that channel — a release with two version numbers in one repo is how a
   submission ends up shipping the wrong build;
3. the source must be signed with the publisher key, and the signature must verify against the
   file set the host will pack (hidden files, `node_modules` and `*.cindy` are skipped by the
   host's packer, so the signature must skip them too).

Then it prints the three host calls that remain, with the exact arguments.

Usage
-----
    python scripts/release_cindy_plugin.py --variant community
    python scripts/release_cindy_plugin.py --variant community --version 1.5.13
    python scripts/release_cindy_plugin.py --variant official --dry-run

The publisher key stays on this machine (`~/.cindy/publisher-keys/`); this script never prints
it and never writes it anywhere but the source directory's `cindy-signatures.json`.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BUILDER = REPO / "scripts" / "build_cindy_plugin_community_variant.py"
SIGNER = REPO / "scripts" / "sign-plugin-package.mjs"
DEFAULT_KEY = Path.home() / ".cindy" / "publisher-keys" / "misakanet-ed25519.pem"
PUBLISHER_NAME = "Ikalus1988"
#: The host's packer skips these; the signature must skip exactly the same files, or the
#: installed package would not match its own signature.
SKIP_NAMES = {".git", "node_modules", "__MACOSX"}


def source_dir(variant: str) -> Path:
    return REPO / (".cindy-plugin-community" if variant == "community" else ".cindy-plugin")


def skip_file(name: str) -> bool:
    return name.startswith(".") or name.endswith(".cindy") or name in SKIP_NAMES


def packed_files(base: Path) -> list[Path]:
    return sorted(
        (p for p in base.rglob("*") if p.is_file() and not skip_file(p.name)),
        key=lambda p: p.relative_to(base).as_posix(),
    )


def run_builder() -> None:
    """Rebuild the community package from the official source and check the three-place contract."""
    done = subprocess.run([sys.executable, str(BUILDER)], capture_output=True, text=True, cwd=REPO)
    if done.returncode != 0:
        print(done.stdout, file=sys.stderr)
        print(done.stderr, file=sys.stderr)
        raise SystemExit("the community package is out of sync with the official source — fix that first")


def check_versions(variant: str, base: Path, requested: str) -> str:
    manifest = json.loads((base / "ghost.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if requested and requested != version:
        raise SystemExit(
            f"--version {requested} does not match the manifest ({version}); "
            "bump the manifest (and the builder's COMMUNITY_VERSION for the community channel) first"
        )
    if variant == "community":
        builder_text = BUILDER.read_text(encoding="utf-8")
        for line in builder_text.splitlines():
            if line.startswith("COMMUNITY_VERSION"):
                declared = line.split('"')[1]
                if declared != version:
                    raise SystemExit(
                        f"the builder publishes {declared} but the community manifest says {version} — "
                        "the community package would be published under the wrong version number"
                    )
    return version


def build_package(base: Path, version: str) -> Path:
    """A local `.cindy` zip of the plugin directory, the way the host packs it."""
    target = base / f"misakanet-{version}.cindy"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in packed_files(base):
            archive.write(path, path.relative_to(base).as_posix())
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--variant", choices=["community", "official"], default="community")
    parser.add_argument("--version", default="", help="the version being released")
    parser.add_argument("--key", default=str(DEFAULT_KEY), help="publisher key path")
    parser.add_argument("--dry-run", action="store_true", help="check everything, sign nothing")
    args = parser.parse_args(argv)

    if args.variant == "community":
        run_builder()
    base = source_dir(args.variant)
    if not (base / "ghost.json").exists():
        raise SystemExit(f"{base} has no ghost.json")

    version = check_versions(args.variant, base, args.version)
    manifest = json.loads((base / "ghost.json").read_text(encoding="utf-8"))
    print(f"variant   : {args.variant}")
    print(f"source    : {base}")
    print(f"version   : {version} (manifest agrees)")
    print(f"id        : {manifest['id']}")

    if args.dry_run:
        print("\n--dry-run: nothing signed, nothing written.")
        return 0

    key = Path(args.key)
    if not key.exists():
        raise SystemExit(f"publisher key not found at {key}")

    # 1. sign the source (writes cindy-signatures.json next to it)
    done = subprocess.run(
        [
            "node", str(SIGNER), "release",
            "--package", str(build_package(base, version)),
            "--key", str(key),
            "--name", PUBLISHER_NAME,
            "--emit-to", str(base),
        ],
        capture_output=True, text=True, cwd=REPO,
    )
    if done.returncode != 0:
        print(done.stdout, file=sys.stderr)
        print(done.stderr, file=sys.stderr)
        raise SystemExit("signing failed")
    for line in done.stdout.splitlines():
        if line.strip().startswith('"'):
            try:
                print("  ", json.loads(line).get("ghostVersion", ""), "signed")
            except json.JSONDecodeError:
                pass

    # 2. build the package again, now carrying the signature, and verify it
    package = build_package(base, version)
    verified = subprocess.run(
        ["node", str(SIGNER), "verify", "--package", str(package)],
        capture_output=True, text=True, cwd=REPO,
    )
    try:
        report = json.loads(verified.stdout[verified.stdout.index("{"):])
    except (ValueError, IndexError):
        print(verified.stdout, file=sys.stderr)
        print(verified.stderr, file=sys.stderr)
        raise SystemExit("could not read the verification report")
    if not report.get("signed") or not report.get("signatureOk"):
        raise SystemExit(f"the signature does not verify: {report}")
    print(f"  signed  : {report['label']} (keyId {report['keyId']}, {report['files']} files)")

    print("\nNext, in the client (the host owns these three calls):")
    print(f"  1. ghost_forge_pack(dir={str(base)!r})")
    print(f"  2. ghost_forge_install(dir={str(base)!r}, namespace='local')   # the market copy cannot be overwritten by a local package")
    print(f"  3. ghost_contribution_prepare(ghost_id='{manifest['id']}', namespace='local')")
    print("     → then ghost_contribution_submit(prepared_id=…)")
    print("\nAfter the review approves it, write the KV once (the marketplace's version, not the repo's):")
    print("  python scripts/publish_cindy_plugin_version.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
