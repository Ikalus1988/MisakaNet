#!/usr/bin/env python3
"""Pull Search Console search analytics for the verified property — the first external demand signal.

Why this exists
---------------
Everything else this repository measures is *internal*: MCP calls (`/api/analytics`), retrievals per
lesson (`search_signals`), intake volume. None of them can answer "what do people **outside** type
into a search engine before they arrive here". Search Console is the only free source that can, and
it is compatible with the site's privacy promise because it sets no cookie and loads no script
(`docs/maintainer/cloudflare-google-leverage-2026-10-31.md` §6).

Since 2026-08-31 the same API also reports AI Overviews / AI Mode exposure. For a service whose
users are agents, *being cited by an AI answer* is the distribution channel that matters, and this is
the only place it is visible.

The property is a URL-prefix property (`https://misakanet.org/`), verified by the HTML file at
`docs/googled7bffcd986dade3f.html` and the meta tag in `docs/index.html`.

Credentials
-----------
Three ways, in the order this script tries them:

1. `--credentials <service-account.json>` — a service-account key. The script signs a JWT with
   `openssl` (no Python dependency) and exchanges it for an access token. This is the only path that
   works unattended, and the account's email must be added as a **user of the property** in Search
   Console.
2. `GSC_ACCESS_TOKEN` — a token the caller already holds (short-lived).
3. `gcloud auth print-access-token` (`--gcloud`/`GCLOUD` picks the binary).

Whatever the path, the credential is never printed, never put in a URL, and never written into the
output file. The token needs the `webmasters.readonly` scope: read the property, nothing else.

Output
------
`data/gsc/search-analytics-<end-date>.json`, **git-ignored on purpose**: a weekly series of dated
snapshots is the shape `tests/test_benchmark_snapshot_retention.py` exists to stop (each copy doubles
the repository and adds no measurement). Keep the pulls local, or push them into D1 if they ever need
to be queried in production.

Exit codes: `0` the file was written (or a dry run printed the summary), `1` the API or the
credential failed — with a message that is safe to paste into an issue.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SITE = "https://misakanet.org/"
ENDPOINT = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
OPENER = urllib.request.build_opener()
SCOPES = "https://www.googleapis.com/auth/webmasters.readonly"
#: Search Console finalises data 2–3 days behind today; asking for fresher rows returns partials.
LAG_DAYS = 2


def site_key(site: str) -> str:
    """The property id as the API wants it in the path: the whole URL, percent-encoded."""
    return urllib.parse.quote(site, safe="")


def build_body(start: str, end: str, dimension: str = "query", row_limit: int = 200) -> dict:
    """The request body. Kept separate so a test can assert it without a network."""
    return {
        "startDate": start,
        "endDate": end,
        "dimensions": [dimension],
        "rowLimit": row_limit,
        "dataState": "final",
    }


def default_window(days: int, today: date | None = None) -> tuple[str, str]:
    """`(start, end)` for the last `days` days of *final* data."""
    end = (today or date.today()) - timedelta(days=LAG_DAYS)
    return (end - timedelta(days=days - 1)).isoformat(), end.isoformat()


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def build_signed_jwt(client_email: str, private_key_pem: str, token_uri: str,
                     now: int | None = None, scope: str = SCOPES) -> str:
    """A signed RS256 assertion, as the service-account flow wants it.

    `openssl` does the signing (this repository keeps Python dependency-free). The key is written to
    a 0600 temp file because `openssl dgst -sign` takes a path, and the file is removed before the
    claim is returned — the key never lingers beside the output.
    """
    issued = int(time.time()) if now is None else now
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {"iss": client_email, "scope": scope, "aud": token_uri,
              "iat": issued, "exp": issued + 3600}
    signing_input = (_b64url(json.dumps(header, separators=(",", ":")).encode()) + "." +
                     _b64url(json.dumps(claims, separators=(",", ":")).encode()))
    handle, key_path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as key_file:
            key_file.write(private_key_pem)
        os.chmod(key_path, 0o600)
        proc = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key_path],
                              input=signing_input.encode("ascii"), capture_output=True)
    finally:
        try:
            os.unlink(key_path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise SystemExit("error: `openssl` could not sign the assertion — is openssl installed? "
                         f"{(proc.stderr or b'').decode('utf-8', 'replace').strip()[:200]}")
    return signing_input + "." + _b64url(proc.stdout)


def service_account_token(credentials: str | Path, opener=None,
                          now: int | None = None) -> str:
    """Exchange a service-account key for an access token. Never echoes the key or the token."""
    opener = opener or OPENER
    try:
        info = json.loads(Path(credentials).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: could not read the service-account key at {credentials}: {error}")
    client_email = info.get("client_email")
    private_key = info.get("private_key")
    if not client_email or not private_key:
        raise SystemExit("error: that file is not a service-account key "
                         "(no client_email/private_key)")
    token_uri = info.get("token_uri") or "https://oauth2.googleapis.com/token"
    assertion = build_signed_jwt(client_email, private_key, token_uri, now=now)
    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }).encode("utf-8")
    request = urllib.request.Request(
        token_uri, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener.open(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300] if error.fp else ""
        raise SystemExit(f"error: the token endpoint answered {error.code}: {detail}")
    except urllib.error.URLError as error:
        raise SystemExit(f"error: could not reach the token endpoint: {error.reason}")
    token = payload.get("access_token")
    if not token:
        raise SystemExit("error: the token endpoint returned no access_token")
    return token


def load_token(environ=None, gcloud: str | None = None, credentials: str | None = None) -> str:
    """A bearer token from a service account, the environment, or `gcloud`. Never echoed."""
    if credentials:
        return service_account_token(credentials)
    env = os.environ if environ is None else environ
    token = (env.get("GSC_ACCESS_TOKEN") or "").strip()
    if token:
        return token
    binary = gcloud or env.get("GCLOUD") or "gcloud"
    try:
        out = subprocess.run([binary, "auth", "print-access-token"],
                             capture_output=True, text=True, check=True)
    except FileNotFoundError:
        raise SystemExit("error: no GSC_ACCESS_TOKEN, and `gcloud` is not on PATH "
                         "(install it or set GSC_ACCESS_TOKEN)")
    except subprocess.CalledProcessError as error:
        # stderr can carry a hint (which account is not authenticated); it carries no token.
        raise SystemExit(f"error: `{binary} auth print-access-token` failed: "
                         f"{(error.stderr or '').strip()[:200]}")
    value = (out.stdout or "").strip()
    if not value:
        raise SystemExit("error: `gcloud auth print-access-token` returned nothing")
    return value


def query(site: str, body: dict, token: str, opener=None) -> dict:
    """POST the query. Raises SystemExit with a pasteable message on failure."""
    opener = opener or OPENER
    request = urllib.request.Request(
        ENDPOINT.format(site=site_key(site)),
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with opener.open(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300] if error.fp else ""
        raise SystemExit(f"error: Search Console answered {error.code}: {detail}")
    except urllib.error.URLError as error:
        raise SystemExit(f"error: could not reach Search Console: {error.reason}")


def summarise(payload: dict, top: int = 10) -> str:
    """A readable digest: totals, then the queries people actually used."""
    rows = payload.get("rows") or []
    clicks = sum(r.get("clicks", 0) for r in rows)
    impressions = sum(r.get("impressions", 0) for r in rows)
    lines = [f"{len(rows)} query row(s) · {clicks:.0f} click(s) · {impressions:.0f} impression(s)"]
    ranked = sorted(rows, key=lambda r: (-r.get("impressions", 0), -r.get("clicks", 0)))[:top]
    for row in ranked:
        key = (row.get("keys") or [""])[0]
        lines.append(f"  {row.get('impressions', 0):>8.0f} imp  {row.get('clicks', 0):>5.0f} clk  "
                     f"pos {row.get('position', 0):>5.1f}  {key[:70]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pull Search Console search analytics")
    parser.add_argument("--site", default=DEFAULT_SITE, help="verified property (URL-prefix or sc-domain)")
    parser.add_argument("--days", type=int, default=28, help="window length, ending LAG_DAYS ago")
    parser.add_argument("--start", help="override the window start (YYYY-MM-DD)")
    parser.add_argument("--end", help="override the window end (YYYY-MM-DD)")
    parser.add_argument("--dimension", default="query", help="query | page | country | device")
    parser.add_argument("--out", default=str(REPO / "data" / "gsc"), help="output directory")
    parser.add_argument("--dry-run", action="store_true", help="print the digest, write nothing")
    parser.add_argument("--gcloud", help="path to the gcloud binary")
    parser.add_argument("--credentials",
                        help="service-account JSON key (its email must be a user of the property)")
    args = parser.parse_args(argv)

    if args.end:
        end = args.end
    else:
        _, end = default_window(args.days)
    start = args.start or default_window(args.days)[0]

    body = build_body(start, end, args.dimension)
    payload = query(args.site, body, load_token(gcloud=args.gcloud, credentials=args.credentials))
    print(f"property: {args.site}  window: {start} → {end}")
    print(summarise(payload))
    if args.dry_run:
        print("(dry run — nothing written)")
        return 0

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"search-analytics-{end}.json"
    path.write_text(json.dumps({"site": args.site, "request": body, "response": payload},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
