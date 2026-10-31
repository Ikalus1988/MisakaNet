#!/usr/bin/env python3
"""Rewrite the `CHECKSUMS` block in `integrations/agent-autostart/bootstrap.sh`.

Why this exists
---------------
`bootstrap.sh` downloads an installer and `exec`s it (the audit's F19). The ref is pinned, which stops
`main` from moving; the digests are what stop a **mirror** from serving different bytes for the same
tag. They live inside `bootstrap.sh` rather than in a `CHECKSUMS` file fetched at run time, because in
exactly the network the mirrors exist for the primary host is unreachable — a checksum that cannot be
fetched verifies nothing.

Normalisation: digests are computed over `\\r\\n` folded to `\\n`, so a Windows checkout of this repo
produces the same value as the bytes raw.githubusercontent serves. Without that, the check would fail on
one platform for a reason that has nothing to do with tampering.

Usage
-----
    python3 scripts/update_install_checksums.py --check   # exit 1 when the block is stale
    python3 scripts/update_install_checksums.py --write   # rewrite the block in place

`tests/test_bootstrap_checksums.py` runs `--check`, so a stale block cannot merge.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO / "integrations" / "agent-autostart" / "bootstrap.sh"
START = "# >>> CHECKSUMS (generated: python3 scripts/update_install_checksums.py --write) >>>"
END = "# <<< CHECKSUMS <<<"
BLOCK = re.compile(re.escape(START) + r"\n(.*?)\n" + re.escape(END), re.S)


def files_of(bootstrap_text: str) -> list[str]:
    """The `FILES` list bootstrap downloads — one source of truth for which files are hashed."""
    match = re.search(r'^FILES="([^"]+)"', bootstrap_text, re.M)
    if not match:
        raise SystemExit("bootstrap.sh has no FILES= line")
    return match.group(1).split()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def expected_block(files: list[str]) -> str:
    lines = [f'{digest(REPO / "integrations" / "agent-autostart" / name)}  {name}' for name in files]
    return 'CHECKSUMS="\n' + "\n".join(lines) + '\n"'


def current_block(text: str) -> str:
    match = BLOCK.search(text)
    if not match:
        raise SystemExit("bootstrap.sh has no CHECKSUMS block (markers missing)")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="exit 1 when the block does not match the files")
    group.add_argument("--write", action="store_true", help="rewrite the block")
    args = parser.parse_args(argv)

    text = BOOTSTRAP.read_text(encoding="utf-8")
    want = expected_block(files_of(text))
    have = current_block(text)
    if args.check:
        if want == have:
            print(f"OK bootstrap CHECKSUMS matches {len(files_of(text))} file(s)")
            return 0
        print("bootstrap CHECKSUMS is stale — run:", file=sys.stderr)
        print("  python3 scripts/update_install_checksums.py --write", file=sys.stderr)
        print("expected:\n" + want, file=sys.stderr)
        print("found:\n" + have, file=sys.stderr)
        return 1

    BOOTSTRAP.write_text(BLOCK.sub(lambda _m: START + "\n" + want + "\n" + END, text, count=1),
                         encoding="utf-8")
    print(f"wrote bootstrap CHECKSUMS for {len(files_of(text))} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
