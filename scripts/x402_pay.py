#!/usr/bin/env python3
"""x402 "exact" payment client — pay-per-call HTTP without an API key.

Why this file exists
--------------------
MisakaNet's benchmark runner talks to LLM providers through a small registry in
``scripts/bench_orchestrator.py``. Every provider there is authenticated with a bearer token,
which is not the only shape: an x402 endpoint answers an unpaid request with ``402 Payment
Required`` and a machine-readable price, then expects the caller to sign a payment authorisation
and retry. This module implements that retry so a provider entry can be a plain function call.

The protocol details below were **measured against the live endpoint** on 2026-10-20, not copied
from a document that may have drifted:

* the 402 body carries ``accepts[0] = {scheme, network, amount, asset, payTo, maxTimeoutSeconds,
  extra}``; ``amount`` is in the asset's atomic units (USDC has 6 decimals, so ``"2000"`` is
  $0.002);
* the client header is ``PAYMENT-SIGNATURE`` (v2). The v1 ``X-PAYMENT`` name is ignored — the
  server answered it with a fresh 402;
* the signed blob is base64(JSON) of ``{x402Version, scheme, network, accepted, payload}``, where
  ``accepted`` echoes the chosen requirement and ``payload`` is
  ``{signature, authorization}``;
* ``authorization``'s ``value`` / ``validAfter`` / ``validBefore`` must be **strings** on the wire.
  Sending integers makes the facilitator reject the body with
  ``Error at "/paymentPayload/payload/..."`` before it ever looks at the signature;
* the EIP-712 domain is ``{name: extra.name, version: extra.version, chainId: <from network>,
  verifyingContract: asset}`` with primary type ``TransferWithAuthorization``.

A correct envelope, signed by an address holding no USDC, gets past signature verification and
fails only at the on-chain call (``contract call failed: ... execution reverted``). That is the
distinction this module's errors try to preserve: "your payment was malformed" and "your wallet
is empty" are different problems and the operator can only act on the second one.

The spending cap is not optional
--------------------------------
The price is chosen by the **server**, not by us. A buggy or hostile endpoint can answer with any
``amount`` it likes, and a client that signs whatever it is told is a client that empties a wallet
on request. So :func:`pay_and_post` refuses to sign above ``max_amount_atomic`` (default: 0.01
USDC) and can additionally pin ``payTo`` and ``asset``. The cap is checked *before* any key
material is touched.

Dependency
----------
Signing needs ``eth-account`` (secp256k1 + keccak256 + EIP-712 encoding). It is imported lazily so
that this module — and therefore the benchmark runner and its tests — import cleanly on a machine
without it. Hand-rolling the curve arithmetic was considered and rejected: a subtle error in
keccak padding or in RFC-6979 nonce derivation produces a signature that is valid-looking and
wrong, and there is no way for a reviewer to see that by reading it.

    pip install eth-account

Install it only if you intend to use the ``x402`` provider; nothing else imports it.
"""
from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.error
import urllib.request
from typing import Any, Callable

#: Atomic-unit ceiling for a single call. USDC has 6 decimals, so 10_000 == $0.01.
DEFAULT_MAX_AMOUNT_ATOMIC = 10_000

#: x402 v2 carries the signed payment in this header. v1's ``X-PAYMENT`` is not accepted by v2
#: servers, so sending both buys nothing and hides which one worked.
PAYMENT_HEADER = "PAYMENT-SIGNATURE"

#: A User-Agent is not optional. Cloudflare answered the stdlib default (``Python-urllib/3.x``)
#: with a bare ``403`` and an empty body, which reads as "the endpoint is down" rather than
#: "identify yourself" — measured 2026-10-20 on the provider this module was written for.
USER_AGENT = "MisakaNet-bench/1.0 (+https://misakanet.org)"

_EIP712_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


class X402Error(RuntimeError):
    """A payment could not be produced or the server refused it.

    ``detail`` is carried separately from the message so a caller can surface the server's own
    words (which name the failing field) without having to parse a formatted string.
    """

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


def _decode_json(raw: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw.decode("utf-8", errors="replace"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_challenge(body: bytes, headers: Any = None) -> dict[str, Any]:
    """Extract the payment requirements from a 402 response.

    The body is preferred; the ``PAYMENT-REQUIRED`` header carries the same JSON for servers that
    send an empty body. Raises :class:`X402Error` rather than returning an empty dict — a silent
    "no requirements" would surface later as a confusing 402 loop.
    """
    payload = _decode_json(body)
    if payload is None and headers is not None:
        header = headers.get("PAYMENT-REQUIRED") or headers.get("payment-required")
        if header:
            try:
                padded = header + "=" * (-len(header) % 4)
                payload = json.loads(base64.b64decode(padded))
            except (ValueError, json.JSONDecodeError):
                payload = None
    if payload is None:
        raise X402Error(
            "402 response carried no readable payment requirements",
            detail=body[:300].decode("utf-8", errors="replace"),
        )
    if not payload.get("accepts"):
        raise X402Error(
            "402 response listed no acceptable payment option",
            detail=str(payload)[:300],
        )
    return payload


def select_requirement(
    challenge: dict[str, Any],
    *,
    network: str | None = None,
    scheme: str = "exact",
) -> dict[str, Any]:
    """Pick the requirement we know how to satisfy.

    Filtering on scheme first keeps a server that offers several options from steering us onto one
    this client cannot sign for. ``network`` is an optional narrowing, not a requirement — the
    caller's default is "whatever the server prices in".
    """
    accepts = challenge.get("accepts") or []
    for option in accepts:
        if option.get("scheme") != scheme:
            continue
        if network is not None and option.get("network") != network:
            continue
        return option
    offered = sorted({str(o.get("scheme")) for o in accepts})
    raise X402Error(
        f"no {scheme!r} payment option"
        + (f" on {network}" if network else "")
        + f" (server offers: {', '.join(offered) or 'nothing'})"
    )


def build_authorization(
    requirement: dict[str, Any],
    payer: str,
    *,
    now: int | None = None,
    nonce: str | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Build the EIP-3009 authorisation for ``requirement``.

    Returns ``(wire, typed)``. They differ on purpose: EIP-712 signs ``uint256`` values, while the
    x402 JSON body must carry them as decimal **strings**. Signing the wire form is the bug that
    the facilitator reports as a body error, which is why both are returned together instead of
    letting a caller re-derive one from the other.

    ``nonce`` and ``now`` are injectable so the result is reproducible in tests.
    """
    issued_at = int(time.time()) if now is None else int(now)
    window = int(requirement.get("maxTimeoutSeconds") or 300)
    typed = {
        "from": payer,
        "to": requirement["payTo"],
        "value": int(requirement["amount"]),
        "validAfter": issued_at - 60,
        "validBefore": issued_at + window,
        "nonce": nonce or "0x" + secrets.token_hex(32),
    }
    wire = {key: str(value) for key, value in typed.items()}
    return wire, typed


def typed_data(requirement: dict[str, Any], authorization: dict[str, Any]) -> dict[str, Any]:
    """Assemble the full EIP-712 message the signature must cover."""
    network = str(requirement.get("network", ""))
    try:
        chain_id = int(network.split(":")[1])
    except (IndexError, ValueError):
        raise X402Error(f"cannot derive a chain id from network {network!r}") from None
    extra = requirement.get("extra") or {}
    return {
        "types": _EIP712_TYPES,
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": extra.get("name", ""),
            "version": str(extra.get("version", "1")),
            "chainId": chain_id,
            "verifyingContract": requirement["asset"],
        },
        "message": authorization,
    }


def sign_authorization(message: dict[str, Any], private_key: str) -> str:
    """Sign ``message`` with ``private_key`` and return a ``0x``-prefixed signature.

    ``eth-account`` is imported here, not at module scope: the benchmark runner must import on a
    machine that has never installed it, and a missing optional dependency should fail at the one
    call that needs it with an instruction rather than at import time for every unrelated command.
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_typed_data
    except ImportError as exc:  # pragma: no cover - depends on the host environment
        raise X402Error(
            "signing an x402 payment needs the 'eth-account' package",
            detail=f"install it with: pip install eth-account ({exc})",
        ) from exc

    try:
        signed = Account.sign_message(
            encode_typed_data(full_message=message), private_key=private_key
        )
    except (ValueError, TypeError) as exc:
        # Deliberately does not echo the key, and does not echo ``exc`` either: some eth-account
        # errors quote the value they were given, and that value is key material.
        raise X402Error("could not sign the payment with the supplied wallet key") from None
    return "0x" + bytes(signed.signature).hex()


def encode_payment(payment: dict[str, Any]) -> str:
    """Base64-encode the payment envelope for the ``PAYMENT-SIGNATURE`` header."""
    blob = json.dumps(payment, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(blob).decode("ascii")


def build_payment(
    challenge: dict[str, Any],
    private_key: str,
    *,
    payer: str | None = None,
    network: str | None = None,
    max_amount_atomic: int = DEFAULT_MAX_AMOUNT_ATOMIC,
    expected_pay_to: str | None = None,
    expected_asset: str | None = None,
    now: int | None = None,
    nonce: str | None = None,
    signer: Callable[[dict[str, Any], str], str] = sign_authorization,
    address_of: Callable[[str], str] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Turn a 402 challenge into a header value, or refuse.

    Returns ``(header_value, requirement)`` so the caller can report what it paid without parsing
    the base64 blob back.

    Every check that can be made without touching the key is made first, and the amount ceiling is
    compared before signing: an endpoint that answers ``amount: "1000000000"`` is a wallet-drain
    attempt, and the useful response to it is a refusal, not a signed authorisation.
    """
    requirement = select_requirement(challenge, network=network)

    amount = int(requirement.get("amount", 0))
    if amount <= 0:
        raise X402Error(f"server asked for a non-positive amount ({amount!r})")
    if amount > max_amount_atomic:
        raise X402Error(
            f"server asked for {amount} atomic units, above the {max_amount_atomic} ceiling; "
            "refusing to sign"
        )
    if expected_pay_to and requirement.get("payTo", "").lower() != expected_pay_to.lower():
        raise X402Error(
            f"server asked to be paid at {requirement.get('payTo')!r}, "
            "not the pinned address"
        )
    if expected_asset and requirement.get("asset", "").lower() != expected_asset.lower():
        raise X402Error(
            f"server asked for asset {requirement.get('asset')!r}, "
            "not the pinned asset"
        )

    if payer is None:
        if address_of is None:
            payer = _address_of(private_key)
        else:
            payer = address_of(private_key)

    wire, typed = build_authorization(requirement, payer, now=now, nonce=nonce)
    signature = signer(typed_data(requirement, typed), private_key)
    payment = {
        "x402Version": int(challenge.get("x402Version") or 2),
        "scheme": requirement["scheme"],
        "network": requirement["network"],
        "accepted": requirement,
        "payload": {"signature": signature, "authorization": wire},
    }
    return encode_payment(payment), requirement


def _address_of(private_key: str) -> str:
    """Derive the payer address, reusing the optional dependency check from signing."""
    try:
        from eth_account import Account
    except ImportError as exc:  # pragma: no cover - depends on the host environment
        raise X402Error(
            "deriving the payer address needs the 'eth-account' package",
            detail=f"install it with: pip install eth-account ({exc})",
        ) from exc
    try:
        return Account.from_key(private_key).address
    except (ValueError, TypeError):
        raise X402Error("the supplied wallet key is not a valid secp256k1 private key") from None


def _post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, Any, bytes]:
    """Single HTTP POST. Returns ``(status, headers, body)``; 4xx/5xx are values, not exceptions."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def pay_and_post(
    url: str,
    payload: dict[str, Any],
    private_key: str,
    *,
    max_amount_atomic: int = DEFAULT_MAX_AMOUNT_ATOMIC,
    expected_pay_to: str | None = None,
    expected_asset: str | None = None,
    timeout: float = 90.0,
    transport: Callable[[str, bytes, dict[str, str], float], tuple[int, Any, bytes]] = _post,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """POST ``payload``, settle a 402 if one comes back, and return ``(json, requirement)``.

    ``transport`` is injectable so the retry logic can be exercised without a network — the whole
    point of this function is the second request, and a test that needs an endpoint to observe it
    is a test that runs on someone else's schedule.
    """
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }

    status, response_headers, response_body = transport(url, body, headers, timeout)
    if status != 402:
        return _require_json(status, response_body, response_headers), {}

    challenge = parse_challenge(response_body, response_headers)
    payment_header, requirement = build_payment(
        challenge,
        private_key,
        max_amount_atomic=max_amount_atomic,
        expected_pay_to=expected_pay_to,
        expected_asset=expected_asset,
    )

    paid_headers = dict(headers)
    paid_headers[PAYMENT_HEADER] = payment_header
    status, response_headers, response_body = transport(url, body, paid_headers, timeout)
    if status == 402:
        # The server took the payment header and still wants money: it rejected what we signed.
        # Surfacing its text is the difference between "wrong envelope" and "empty wallet".
        detail = ""
        try:
            detail = str(json.loads(response_body).get("error", ""))[:400]
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            detail = response_body[:400].decode("utf-8", errors="replace")
        raise X402Error("payment was refused", detail=detail)
    return _require_json(status, response_body, response_headers), requirement


def _require_json(status: int, body: bytes, headers: Any = None) -> dict[str, Any]:
    """Decode a success response, or explain what the server sent instead."""
    parsed = _decode_json(body)
    if status >= 400:
        detail = (
            (parsed or {}).get("error")
            if parsed
            else body[:300].decode("utf-8", errors="replace")
        )
        raise X402Error(f"server returned HTTP {status}", detail=str(detail)[:400])
    if parsed is None:
        raise X402Error(f"server returned HTTP {status} with a non-JSON body")
    return parsed
