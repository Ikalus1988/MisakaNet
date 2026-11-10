"""`misakanet tombstone validate|draft` — the local, zero-network half of the crash pipeline.

The crash pipeline is: guard → tombstone (JSON) → draft lesson → review. The middle step used to be a
script that only worked inside a checkout. This subcommand makes the **contract check** runnable
anywhere an installed wheel is (`validate`, which needs nothing else), and keeps `draft` honest about
what it needs: a repository checkout, because a draft lesson is a file in `lessons/drafts/` that the
repo's own gate will read.

    misakanet tombstone validate crash.json
    cat crash.json | misakanet tombstone validate -
    misakanet tombstone draft crash.json --dry-run     # needs a checkout (or MISAKANET_REPO=)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from misakanet.tombstone import validate_payload

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="misakanet tombstone",
        description="Check a crash tombstone against the v1 contract, or turn it into a draft lesson.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check the payload against the v1 contract (no network)")
    validate.add_argument("source", help="tombstone JSON file, or - to read stdin")
    validate.add_argument("--json", action="store_true", help="machine-readable verdict")

    draft = sub.add_parser(
        "draft",
        help="turn a tombstone into lessons/drafts/<slug>.md (needs a MisakaNet checkout)",
    )
    draft.add_argument("source", help="tombstone JSON file, or - to read stdin")
    draft.add_argument("--dry-run", action="store_true", help="print the draft instead of writing it")
    return parser


def _read(source: str) -> dict:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("the tombstone must be a JSON object")
    return data


def _repo_root() -> Path | None:
    """The checkout that owns `scripts/tombstone_to_draft.py`, or None.

    `MISAKANET_REPO` wins so a script can point at a clone from anywhere; otherwise walk up from the
    working directory, which is what "run it from the repo" produces.
    """
    configured = os.environ.get("MISAKANET_REPO", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates += [Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        if (candidate / "scripts" / "tombstone_to_draft.py").is_file():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data = _read(args.source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"misakanet tombstone: cannot read {args.source}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    problems = validate_payload(data)
    if args.command == "validate":
        if args.json:
            print(json.dumps({"valid": not problems, "problems": problems}, ensure_ascii=False, indent=2))
        elif problems:
            print("invalid tombstone v1:", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
        else:
            print(f"valid tombstone v1 ({data.get('reason')}, schemaVersion 1)")
        return EXIT_OK if not problems else EXIT_INVALID

    # draft: refuse an invalid payload before shelling out — the converter would skip it with a
    # less specific message.
    if problems:
        print("invalid tombstone v1; fix these before drafting:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return EXIT_INVALID

    root = _repo_root()
    if root is None:
        print(
            "misakanet tombstone draft needs a MisakaNet checkout (it writes lessons/drafts/ and the\n"
            "repo's gate reads it). Set MISAKANET_REPO=/path/to/MisakaNet, or run:\n"
            "  git clone https://github.com/Ikalus1988/MisakaNet && "
            "python3 MisakaNet/scripts/tombstone_to_draft.py --from-file <tombstone.json>",
            file=sys.stderr,
        )
        return EXIT_USAGE

    command = [sys.executable, str(root / "scripts" / "tombstone_to_draft.py")]
    if args.dry_run:
        command.append("--dry-run")
    if args.source == "-":
        command.append("--stdin")
        payload = json.dumps(data, ensure_ascii=False)
        return subprocess.call(command, input=payload, text=True)
    command += ["--from-file", args.source]
    return subprocess.call(command)
