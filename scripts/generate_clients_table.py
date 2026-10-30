#!/usr/bin/env python3
"""The client table on `/install/` is generated from `docs/data/clients.json` (issue #3640).

**Why a generator and not a table in the page.** The page's default path is one command for
every client, so the only thing left to say about a client is what the installer writes for it,
whether that client can report lessons back, and whether it needs an account. Those three
answers change when the installer changes — and a table that drifts from the installer is worse
than no table, because a reader trusts it. So the table is generated, and `--check` fails when
the page and the data file disagree.

    python scripts/generate_clients_table.py            # print the table
    python scripts/generate_clients_table.py --check    # exit 1 when the page has drifted
    python scripts/generate_clients_table.py --write    # rewrite the page in place

The page is edited **between the markers** only; everything outside them is left alone.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "docs" / "data" / "clients.json"
PAGE = REPO / "docs" / "install" / "index.html"
START_MARKER = "<!-- clients-table:start -->"
END_MARKER = "<!-- clients-table:end -->"

#: The three answers the table gives, and the words they are printed in.
REPORTING_WORDS = {
    "auto-with-consent": "Auto, with consent",
    "mcp-only": "MCP only",
}
ACCOUNT_WORDS = {
    "write-only": "Only to write",
    "no": "Not needed",
}


def load_clients(path: Path = DATA) -> dict:
    """Read the client data, and refuse to render a table that would be wrong.

    A generator that renders whatever it is given is a generator that publishes lies: a missing
    client, a duplicate id or an unknown value has to stop the build, not appear in the page.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"the client data is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"the client data is not valid JSON: {path}: {exc}") from exc

    clients = data.get("clients")
    if not isinstance(clients, list) or not clients:
        raise SystemExit(f"the client data has no clients: {path}")

    seen: set[str] = set()
    for client in clients:
        for field in ("id", "name", "writes", "scope", "reporting", "account"):
            if not client.get(field):
                raise SystemExit(
                    f"the client data has a client without {field!r}: {json.dumps(client)}"
                )
        if client["id"] in seen:
            raise SystemExit(f"the client data has a duplicate id: {client['id']!r}")
        seen.add(client["id"])
        if client["reporting"] not in REPORTING_WORDS:
            raise SystemExit(
                f"unknown reporting value {client['reporting']!r} for {client['id']!r}; "
                f"expected one of {sorted(REPORTING_WORDS)}"
            )
        if client["account"] not in ACCOUNT_WORDS:
            raise SystemExit(
                f"unknown account value {client['account']!r} for {client['id']!r}; "
                f"expected one of {sorted(ACCOUNT_WORDS)}"
            )
    return data


def render_table(data: dict) -> str:
    """The table, as HTML."""
    rows = []
    for client in data["clients"]:
        docs = client.get("docs")
        guide = (
            f'<a href="{docs}">Guide</a>' if docs else '<span class="muted">—</span>'
        )
        rows.append(
            "        <tr>"
            f'<td data-label="Client"><strong>{client["name"]}</strong></td>'
            f'<td data-label="Install"><code>{client["writes"]}</code></td>'
            f'<td data-label="Reporting">{REPORTING_WORDS[client["reporting"]]}</td>'
            f'<td data-label="Account">{ACCOUNT_WORDS[client["account"]]}</td>'
            f'<td data-label="Docs">{guide}</td>'
            "</tr>"
        )
    return "\n".join(
        [
            '      <table class="client-table">',
            "        <thead>",
            "          <tr>"
            "<th>Client</th><th>Install</th><th>Reporting</th><th>Account</th><th>Docs</th>"
            "</tr>",
            "        </thead>",
            "        <tbody>",
            *rows,
            "        </tbody>",
            "      </table>",
        ]
    )


def render_summary(data: dict) -> str:
    """The disclosure line above the table — the count is data too, so it is generated as well.

    It read "Show the ten supported clients" over a table that already had eleven rows (measured
    2026-10-30, the day the twelfth landed). The count sat *outside* the generated block, so it
    drifted in exactly the way the table itself was made impossible to drift; a hand-maintained
    number next to a generated list is the same bug waiting one client later.
    """
    return f'      <summary>Show the {len(data["clients"])} supported clients</summary>'


def page_block(data: dict) -> str:
    """The marked block, as it appears in the page: the disclosure line and the table."""
    return f"{START_MARKER}\n{render_summary(data)}\n{render_table(data)}\n{END_MARKER}"


def read_block(page: Path = PAGE) -> str:
    """The block currently in the page, or raise if the markers are missing or duplicated."""
    try:
        text = page.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"the install page is missing: {page}") from exc
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise SystemExit(
            f"the install page must carry exactly one {START_MARKER} / {END_MARKER} pair: {page}"
        )
    start = text.index(START_MARKER)
    end = text.index(END_MARKER)
    return text[start : end + len(END_MARKER)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when the page has drifted")
    parser.add_argument("--write", action="store_true", help="rewrite the page in place")
    args = parser.parse_args(argv)

    data = load_clients()
    block = page_block(data)

    if args.write:
        text = PAGE.read_text(encoding="utf-8")
        current = read_block()
        if current == block:
            print(f"the client table is already up to date: {PAGE}")
            return 0
        PAGE.write_text(text.replace(current, block), encoding="utf-8")
        print(f"wrote the client table into {PAGE}")
        return 0

    if args.check:
        current = read_block()
        if current == block:
            print(f"the client table is up to date: {PAGE}")
            return 0
        print(
            f"the client table in {PAGE} has drifted from {DATA}\n"
            "run: python scripts/generate_clients_table.py --write",
            file=sys.stderr,
        )
        return 1

    print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
