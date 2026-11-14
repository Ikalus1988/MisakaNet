#!/usr/bin/env python3
"""`scripts/gsc_pull.py` — the request it builds, the token it never prints, the file it writes.

Why a test for a 150-line puller: the failure this guards against is silent. A wrong property id, a
date range that asks for data Search Console has not finalised, or a token that leaks into a log line
all produce *a file* that looks like a measurement — and the reader of that file has no way to tell.
`data/gsc/` is git-ignored on purpose (a weekly series of dated snapshots is the shape
`tests/test_benchmark_snapshot_retention.py` exists to stop), so nothing downstream re-checks it.

What is pinned here:
  * the property id is percent-encoded into the path, trailing slash included;
  * the body asks for a finalised window, never for today's partials;
  * the token comes from the environment first, `gcloud` second, and appears in no printed line;
  * a dry run writes nothing; a real run writes the request it made next to the answer.
"""
from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import gsc_pull as gsc  # noqa: E402


class FakeOpener:
    """Records the request it was handed and answers with a fixed payload."""

    def __init__(self, payload: dict | None = None):
        self.calls = []
        self.payload = payload if payload is not None else {
            "rows": [
                {"keys": ["pip install timeout"], "clicks": 3, "impressions": 40, "position": 6.5},
                {"keys": ["wsl2 landlock"], "clicks": 0, "impressions": 90, "position": 18.0},
            ]
        }

    def open(self, request, timeout=None):
        self.calls.append(request)
        return io.BytesIO(json.dumps(self.payload).encode("utf-8"))


def test_the_property_is_percent_encoded_into_the_path():
    # A URL-prefix property is written with scheme and a trailing slash; the API wants that whole
    # string in the path, and an unencoded one changes the route.
    key = gsc.site_key("https://misakanet.org/")
    assert key == "https%3A%2F%2Fmisakanet.org%2F"


def test_the_body_asks_for_a_finalised_window_not_today():
    body = gsc.build_body("2026-10-18", "2026-11-11")
    assert body["startDate"] == "2026-10-18" and body["endDate"] == "2026-11-11"
    assert body["dimensions"] == ["query"] and body["rowLimit"] == 200
    assert body["dataState"] == "final", "asking for partials reads as a drop in traffic"

    start, end = gsc.default_window(28, today=date(2026, 11, 14))
    assert end == "2026-11-12", "the window must stop before the unfinalised tail"
    assert start == "2026-10-16"
    assert (date.fromisoformat(end) - date.fromisoformat(start)).days == 27


def test_the_token_comes_from_the_environment_first(monkeypatch):
    monkeypatch.setenv("GSC_ACCESS_TOKEN", "env-token")
    # A gcloud that would explode if it were consulted proves the environment won.
    assert gsc.load_token(gcloud="/nonexistent/gcloud") == "env-token"


def test_a_missing_token_names_both_ways_to_supply_one(monkeypatch):
    monkeypatch.delenv("GSC_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit) as exc:
        gsc.load_token(gcloud="/nonexistent/gcloud")
    assert "GSC_ACCESS_TOKEN" in str(exc.value)


def test_the_request_carries_the_bearer_and_the_digest_ranks_by_impressions():
    opener = FakeOpener()
    body = gsc.build_body("2026-10-18", "2026-11-11")
    payload = gsc.query("https://misakanet.org/", body, "secret-token", opener=opener)
    assert len(opener.calls) == 1
    request = opener.calls[0]
    assert "sites/https%3A%2F%2Fmisakanet.org%2F/searchAnalytics/query" in request.full_url
    assert request.get_header("Authorization") == "Bearer secret-token"
    assert json.loads(request.data.decode("utf-8"))["dataState"] == "final"

    digest = gsc.summarise(payload)
    assert "2 query row(s)" in digest and "130 impression(s)" in digest
    assert digest.index("wsl2") < digest.index("pip install"), (
        "the digest ranks by impressions, so the query nobody found us for still shows up")
    assert "secret-token" not in digest


def test_a_dry_run_writes_nothing_and_a_real_run_records_the_request(tmp_path, monkeypatch, capsys):
    opener = FakeOpener()
    monkeypatch.setattr(gsc, "OPENER", opener)
    monkeypatch.setenv("GSC_ACCESS_TOKEN", "env-token")

    assert gsc.main(["--start", "2026-10-18", "--end", "2026-11-11",
                     "--out", str(tmp_path), "--dry-run"]) == 0
    assert list(tmp_path.iterdir()) == [], "a dry run wrote a file"
    printed = capsys.readouterr().out
    assert "dry run" in printed and "env-token" not in printed

    assert gsc.main(["--start", "2026-10-18", "--end", "2026-11-11", "--out", str(tmp_path)]) == 0
    written = tmp_path / "search-analytics-2026-11-11.json"
    saved = json.loads(written.read_text(encoding="utf-8"))
    assert saved["request"]["startDate"] == "2026-10-18"
    assert saved["response"]["rows"][0]["keys"] == ["pip install timeout"]
    assert "env-token" not in written.read_text(encoding="utf-8"), (
        "the file records the request, never the credential that authorised it")


# ── the service-account path: a real signature, and a key that does not linger ────────────────
# This is the only credential route that works unattended (a GitHub Action or a cron), so it is
# the one whose failures are silent: a signature that is merely *present* would still be rejected
# by Google with a 400 that says nothing about which half was wrong.


@pytest.fixture
def rsa_key(tmp_path):
    """A throwaway RSA key, generated by the same `openssl` the script will use."""
    key = tmp_path / "key.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                    "-out", str(key)], check=True, capture_output=True)
    if not key.exists():
        pytest.skip("openssl could not generate a key")
    return key


def test_the_assertion_is_really_signed(rsa_key):
    pem = rsa_key.read_text(encoding="utf-8")
    jwt = gsc.build_signed_jwt("gsc-reader@example.iam.gserviceaccount.com", pem,
                               "https://oauth2.googleapis.com/token", now=1_700_000_000)
    header, claims, signature = jwt.split(".")
    assert json.loads(base64.urlsafe_b64decode(header + "=="))["alg"] == "RS256"
    decoded = json.loads(base64.urlsafe_b64decode(claims + "=="))
    assert decoded["scope"] == "https://www.googleapis.com/auth/webmasters.readonly"
    assert decoded["aud"] == "https://oauth2.googleapis.com/token"
    assert decoded["exp"] - decoded["iat"] == 3600

    # The signature must verify against the public half — "three dot-separated parts" is not a sign.
    public = rsa_key.with_suffix(".pub")
    subprocess.run(["openssl", "pkey", "-in", str(rsa_key), "-pubout", "-out", str(public)],
                   check=True, capture_output=True)
    signing_input = f"{header}.{claims}".encode("ascii")
    raw_sig = public.with_suffix(".sig")
    raw_sig.write_bytes(base64.urlsafe_b64decode(signature + "=="))
    verified = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(public),
                               "-signature", str(raw_sig)],
                              input=signing_input, capture_output=True)
    assert verified.returncode == 0, verified.stderr


def test_the_private_key_does_not_linger_in_tmp(rsa_key):
    pem = rsa_key.read_text(encoding="utf-8")
    before = set(Path(tempfile.gettempdir()).glob("*.pem"))
    gsc.build_signed_jwt("x@example.com", pem, "https://oauth2.googleapis.com/token")
    after = set(Path(tempfile.gettempdir()).glob("*.pem"))
    assert after == before, f"a key copy survived: {after - before}"


def test_a_key_file_is_exchanged_for_a_token_and_never_echoed(rsa_key, tmp_path, capsys):
    opener = FakeOpener({"access_token": "sa-token", "expires_in": 3599})
    key_json = tmp_path / "sa.json"
    key_json.write_text(json.dumps({
        "client_email": "gsc-reader@example.iam.gserviceaccount.com",
        "private_key": rsa_key.read_text(encoding="utf-8"),
        "token_uri": "https://oauth2.googleapis.com/token",
    }), encoding="utf-8")

    token = gsc.service_account_token(key_json, opener=opener)
    assert token == "sa-token"
    request = opener.calls[0]
    assert request.full_url == "https://oauth2.googleapis.com/token"
    body = urllib.parse.parse_qs(request.data.decode("utf-8"))
    assert body["grant_type"] == ["urn:ietf:params:oauth:grant-type:jwt-bearer"]
    assert len(body["assertion"][0].split(".")) == 3
    assert "sa-token" not in capsys.readouterr().out


def test_a_file_that_is_not_a_service_account_key_says_so(tmp_path):
    wrong = tmp_path / "not-a-key.json"
    wrong.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        gsc.service_account_token(wrong, opener=FakeOpener({"access_token": "x"}))
    assert "client_email" in str(exc.value)


# ── the user-consent path: what an org that forbids service-account keys still allows ──────────
# `iam.disableServiceAccountKeyCreation` blocks the key download, not the API. A refresh token from
# a real consent carries the same scope and needs no key, so this is the path that survives the
# policy — and the two things that go wrong (a consent without `access_type=offline`, a stored file
# that is world-readable) both fail quietly.


def test_the_consent_url_asks_for_a_refresh_token_and_the_scope():
    url = gsc.build_consent_url("cid.apps.googleusercontent.com", "http://127.0.0.1:9/", "state123")
    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert parsed["access_type"] == ["offline"], "without offline there is no refresh token to store"
    assert parsed["prompt"] == ["consent"], "a silent re-approval returns no refresh token"
    assert parsed["scope"] == [gsc.SCOPES]
    assert parsed["redirect_uri"] == ["http://127.0.0.1:9/"]
    assert parsed["state"] == ["state123"], "the state is what makes the loopback response ours"


def test_a_refresh_token_is_minted_from_the_stored_file_and_never_echoed(tmp_path, capsys):
    opener = FakeOpener({"access_token": "fresh-token", "expires_in": 3599})
    store = tmp_path / "oauth-credentials.json"
    store.write_text(json.dumps({
        "client_id": "cid", "client_secret": "csecret", "refresh_token": "rtoken",
        "scope": gsc.SCOPES,
    }), encoding="utf-8")

    assert gsc.refresh_access_token(store, opener=opener) == "fresh-token"
    request = opener.calls[0]
    body = urllib.parse.parse_qs(request.data.decode("utf-8"))
    assert body["grant_type"] == ["refresh_token"]
    assert body["refresh_token"] == ["rtoken"]
    assert request.full_url == gsc.TOKEN_URI
    assert "fresh-token" not in capsys.readouterr().out


# ── the listener-free path: what actually rescued the flow ────────────────────────────────────
# On this host the browser could not reach the WSL listener, and the code sat in the address bar of
# an error page. Pasting that URL into `--code` finished the consent with no socket involved — which
# is why these three cases carry the weight: an error URL, a URL without a code, and a good one.


def test_a_pasted_url_exchanges_the_code_and_stores_the_token(tmp_path):
    client_json = tmp_path / "client.json"
    client_json.write_text(json.dumps({"installed": {
        "client_id": "cid.apps.googleusercontent.com", "client_secret": "csecret"}}), encoding="utf-8")
    store = tmp_path / "oath.json"
    monkeypatched = gsc.exchange_code
    captured = {}

    def fake_exchange(client_id, client_secret, code, redirect_uri, opener=None):
        captured.update(code=code, redirect_uri=redirect_uri)
        return {"refresh_token": "refresh-1", "scope": gsc.SCOPES}

    gsc.exchange_code = fake_exchange
    try:
        url = "http://localhost:45365/?state=s&iss=https://accounts.google.com&code=4/0A-REAL&scope=x"
        assert gsc.exchange_pasted_url(client_json, url, "http://localhost:45365/", store) == 0
    finally:
        gsc.exchange_code = monkeypatched

    assert captured["code"] == "4/0A-REAL"
    assert captured["redirect_uri"] == "http://localhost:45365/", (
        "the exchange must reuse the exact redirect_uri the code was issued for")
    saved = json.loads(store.read_text(encoding="utf-8"))
    assert saved["refresh_token"] == "refresh-1" and saved["client_secret"] == "csecret"
    assert "4/0A-REAL" not in store.read_text(encoding="utf-8"), "the code is single-use; do not keep it"


def test_a_pasted_error_page_is_reported_as_google_reported_it(tmp_path):
    client_json = tmp_path / "client.json"
    client_json.write_text(json.dumps({"installed": {"client_id": "c", "client_secret": "s"}}),
                           encoding="utf-8")
    url = "http://localhost:1/?error=access_denied&error_description=The+user+denied+the+request"
    with pytest.raises(SystemExit) as exc:
        gsc.exchange_pasted_url(client_json, url, "http://localhost:1/", tmp_path / "o.json")
    text = str(exc.value)
    assert "access_denied" in text and "The user denied" in text


def test_a_pasted_url_without_a_code_says_what_to_copy(tmp_path):
    client_json = tmp_path / "client.json"
    client_json.write_text(json.dumps({"installed": {"client_id": "c", "client_secret": "s"}}),
                           encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        gsc.exchange_pasted_url(client_json, "http://localhost:1/?state=only",
                                "http://localhost:1/", tmp_path / "o.json")
    assert "whole URL" in str(exc.value), "the failure has to name the thing to copy"
