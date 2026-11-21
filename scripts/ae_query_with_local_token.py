#!/usr/bin/env python3
"""Run the Analytics Engine report with the token kept on this machine.

`scripts/ae_query.py` needs two environment variables:

* `CLOUDFLARE_API_TOKEN` — a Cloudflare API token with **Account | Account Analytics | Read**
  (the wrangler OAuth token does **not** carry that scope: it comes back as
  `Authentication error` from the Analytics Engine SQL endpoint, which is why this wrapper exists);
* `CLOUDFLARE_ACCOUNT_ID` — the 32-hex account id (the endpoint's account).

The token is read from a file **outside the repository** so it never lands in git:

    ~/.config/misakanet/cf_analytics_token

Creating the token: Cloudflare dashboard → My Profile → API Tokens → Create Token →
"Edit Cloudflare Workers" template (or a custom token) with the account permission
**Account | Account Analytics | Read** for the account that owns the endpoint.

Usage
-----
    python scripts/ae_query_with_local_token.py            # last 7 days
    python scripts/ae_query_with_local_token.py --days 30
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUERY = REPO / "scripts" / "ae_query.py"
TOKEN_FILE = Path.home() / ".config" / "misakanet" / "cf_analytics_token"
ACCOUNT_FILE = Path.home() / ".config" / "misakanet" / "cf_account_id"


def read_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    if os.environ.get("CLOUDFLARE_API_TOKEN"):
        return os.environ["CLOUDFLARE_API_TOKEN"].strip()
    raise SystemExit(
        f"no token found.\n"
        f"  Put it in {TOKEN_FILE} (one line, no quotes), or export CLOUDFLARE_API_TOKEN.\n"
        f"  The token needs the account permission 'Account | Account Analytics | Read' — the\n"
        f"  wrangler OAuth token does not have it (that is what the SQL endpoint rejects)."
    )


def read_account() -> str:
    if ACCOUNT_FILE.exists():
        value = ACCOUNT_FILE.read_text(encoding="utf-8").strip()
    else:
        value = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", value):
        raise SystemExit(
            f"no account id found. Put the 32-hex account id in {ACCOUNT_FILE} "
            f"or export CLOUDFLARE_ACCOUNT_ID."
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    env = dict(os.environ)
    env["CLOUDFLARE_API_TOKEN"] = read_token()
    env["CLOUDFLARE_ACCOUNT_ID"] = read_account()
    env.setdefault("HTTPS_PROXY", "http://127.0.0.1:7890")
    done = subprocess.run(
        [sys.executable, str(QUERY), "--days", str(args.days)],
        env=env, cwd=REPO,
    )
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
