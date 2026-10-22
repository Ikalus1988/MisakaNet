"""Tests for scripts/x402_pay.py — the x402 payment client.

Covers the three behaviours the maintainer asked to be pinned:
  (a) an unpaid request parses ``accepts[0]`` from the 402 challenge;
  (b) the client header is ``PAYMENT-SIGNATURE`` and the EIP-3009 wire values
      (``amount``/``validAfter``/``validBefore``) travel as decimal strings;
  (c) a server asking for more than ``max_amount_atomic`` is refused *before*
      anything is signed — this is the wallet-drain guard.

No network and no private key are required: ``signer``, ``address_of`` and
``transport`` are all injectable.
"""
from __future__ import annotations

import base64
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import x402_pay  # noqa: E402


PAY_TO = "0x00000000000000000000000000000000000000aa"
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
PAYER = "0x00000000000000000000000000000000000000bb"


def _challenge(amount: int = 2000, **over) -> dict:
    option = {
        "scheme": "exact",
        "network": "eip155:8453",
        "amount": str(amount),
        "payTo": PAY_TO,
        "asset": ASSET,
        "maxTimeoutSeconds": 300,
    }
    option.update(over)
    return {"x402Version": 2, "accepts": [option]}


def _fake_signer(message: dict, private_key: str) -> str:
    """Deterministic stand-in for the EIP-712 signer."""
    return "0x" + "ab" * 65


# --------------------------------------------------------------------- (a)
def test_unpaid_request_parses_accepts_zero_and_returns_402():
    """The 402 body is parsed and the first acceptable option is selected."""
    body = json.dumps(_challenge()).encode()
    challenge = x402_pay.parse_challenge(body)

    assert challenge["accepts"], "challenge must expose at least one option"
    chosen = x402_pay.select_requirement(challenge)

    assert chosen["payTo"] == PAY_TO
    assert chosen["amount"] == "2000"
    assert chosen is challenge["accepts"][0], "accepts[0] must be the default pick"


def test_select_requirement_skips_unsupported_scheme():
    """A server offering only an unknown scheme must not be paid blindly."""
    challenge = {"accepts": [{"scheme": "upto", "network": "eip155:8453", "amount": "1"}]}
    with pytest.raises(x402_pay.X402Error):
        x402_pay.select_requirement(challenge)


# --------------------------------------------------------------------- (b)
def test_payment_header_uses_payment_signature_and_string_values():
    """Header name is PAYMENT-SIGNATURE; wire amounts are decimal strings."""
    header_value, requirement = x402_pay.build_payment(
        _challenge(),
        "0x" + "11" * 32,
        payer=PAYER,
        now=1_700_000_000,
        nonce="0x" + "22" * 32,
        signer=_fake_signer,
    )

    assert x402_pay.PAYMENT_HEADER == "PAYMENT-SIGNATURE"

    decoded = json.loads(base64.b64decode(header_value).decode("ascii"))
    auth = decoded.get("payload", {}).get("authorization", decoded.get("authorization", {}))

    for field in ("value", "validAfter", "validBefore"):
        assert field in auth, f"{field} missing from the wire authorization"
        assert isinstance(auth[field], str), (
            f"{field} must be a decimal string on the wire, got {type(auth[field]).__name__}"
        )

    assert auth["value"] == "2000"
    assert int(auth["validBefore"]) > int(auth["validAfter"])
    assert requirement["payTo"] == PAY_TO


# --------------------------------------------------------------------- (c)
def test_refuses_amount_above_ceiling_without_signing():
    """The wallet-drain guard: over-cap amounts are rejected before signing."""
    calls: list = []

    def spy_signer(message: dict, private_key: str) -> str:
        calls.append(message)
        return "0x" + "cd" * 65

    with pytest.raises(x402_pay.X402Error) as excinfo:
        x402_pay.build_payment(
            _challenge(amount=10_000_000),
            "0x" + "11" * 32,
            payer=PAYER,
            max_amount_atomic=10_000,
            signer=spy_signer,
        )

    assert "ceiling" in str(excinfo.value).lower()
    assert calls == [], "the signer must never run for an over-cap amount"


def test_refuses_non_positive_amount():
    with pytest.raises(x402_pay.X402Error):
        x402_pay.build_payment(
            _challenge(amount=0),
            "0x" + "11" * 32,
            payer=PAYER,
            signer=_fake_signer,
        )
