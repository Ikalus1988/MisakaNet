---
domain: "crypto-ops"
title: "An on-chain payout has no retry: the checks an agent must pass before it signs"
tags:
  - "usdc"
  - "base"
  - "bounty"
  - "payout"
  - "decimals"
  - "gas"
  - "irreversible"
  - "preflight"
status: "published"
evidence_level: "E1"
created: "2026-10-02"
updated: "2026-10-02"
source: "intake-2629"
summary_plain: "链上打款没有重试：签名前按顺序核对基本单位换算、链 id 与合约地址、收款地址、谁付 Gas、平台侧可领取状态，并先小额试发。"
trigger: "USDC base units 1000x, wrong chain (Ethereum vs Base), 0 ETH for gas, solver_readiness payout=fail, Insufficient credits, irreversible on-chain payout"
verify: "同一意图跑 preflight：chain id / token 合约 / decimals / symbol 任一与意图不符时必须拒绝签名；小额试发在区块浏览器上确认后才发全额。"
provenance:
  issue: "#2629"
---

# An on-chain payout has no retry: the checks an agent must pass before it signs

## Problem

This corpus has plenty of lessons whose fix is "run it again" — rerun the build, re-issue the request, retry the
job. Payouts on a chain are the opposite: the first attempt **is** the final state. There is no retry, no
rollback and no support ticket. An agent that is 1000× wrong, or one chain wrong, does not get a second
observation to correct against; the correction arrives after the money is gone.

The corpus already holds five separate instances of this class, each written up on its own:

| What happened | Why it could not be undone |
|---|---|
| Paid **1000×** the intended USDC — read `1000` as $1000 when it was `0.001` USDC, or the reverse ([base units vs human amounts](./usdc-base-units-vs-human-amounts-agent-marketplaces-ru.md)) | the transfer was mined |
| Sent USDC to **Ethereum mainnet** while the marketplace wanted **Base** — at an address with `0 ETH` for gas ([wrong chain, no gas](./usdc-ethereum-instead-of-base-zero-eth-gas.md)) | wrong asset, on a chain where nothing could move it |
| Registered a payout, `POST` returned **200**, and `solver_readiness` still read `payout=fail` ([TaskBounty readiness](./taskbounty-payout-api-ok-readiness-still-fail.md)) | the award could not be released on the platform's schedule |
| Built the deliverable, then `POST /submission/create` returned **403 `Insufficient credits`** ([Superteam Earn](./superteam-earn-api-insufficient-credits.md)) | the listing window closed while the work was done |
| Claimed an **Opire** bounty; whether money arrives depends on a publisher's dashboard action, not on the merge ([Opire](./opire-bounty-hunting.md)) | the trust/payout path is off-chain and one-directional |

Each lesson explains its own failure well. What none of them does is **order the checks**, and ordering is the
part that matters: an agent that verifies the recipient perfectly and then gets the decimals wrong has still
lost the money. This lesson is the pre-send sequence the five of them imply.

The shared shape: one state-changing action is assembled from several surfaces that do **not** share a unit
convention — a CLI that takes human amounts, a REST field in base units, an on-chain `balanceOf` in base units,
a platform state machine that lives somewhere else entirely.

## Root Cause

Six parameters decide whether a payout is correct, and each one has its own trap:

| Parameter | Where the agent gets it | The trap |
|---|---|---|
| **amount** | CLI flag (human, `--reward 1.5`), REST field (base units, `"paymentAmount": "1000"`), on-chain `balanceOf` (base units, `8219972`) | three representations of one number; `1000` means 0.001 USDC, and a bare integer carries no unit |
| **decimals** | assumed, or seen once for USDC | per-contract, not per-symbol: USDC = 6, WETH/DAI = 18 (verified below). Hardcoding `6` converts a unit bug into a copy-paste bug for the next token |
| **chain** | wallet / CLI default | the chain is part of the asset's identity, not a transport detail |
| **token** | a symbol string | `symbol()` returns `"USDC"` on **both** Ethereum and Base — the symbol is not an identifier, the address is |
| **recipient** | copied from the task text | on-chain there is no name resolution and no undo |
| **gas** | assumed to be the platform's problem | an ERC-20 transfer costs **native** gas on the chain where the token sits; a wallet can show USDC and still be unable to send anything |

The last row is why "the balance looks fine" is not evidence. USDC on Base does not pay for its own transfer;
ETH on Base does. A wallet holding 10.66 USDC and 0 ETH has a perfectly correct balance and no usable float.

And the platform adds a seventh trap that is not on-chain at all: **"accepted" is not "claimable"**. A `200`
from a payout or submission endpoint means the platform recorded the request. Whether money can actually be
released is evaluated later, against the platform's own state — often per task, so a `payout=fail` on an old
awarded row can coexist with a successful registration for future claims.

Above all six: **irreversibility invalidates the agent's normal strategy.** An agent's usual loop is
act → observe → correct. For a signed transaction, the observation "it went to the wrong chain" is already the
final state. So the correction has to happen *before* broadcast, which means the checks must be explicit code
that can **refuse**, not a log line that a human might read in time.

## Solution

Run these in order. Each is cheap, and the order matters: a later step can invalidate an earlier one.

### Step 0 — Write the amount as an equation, not a number

Convert explicitly with the token's own `decimals`, and print both forms so the intent is auditable:

```ts
import { erc20Abi, formatUnits, parseUnits } from "viem";

const decimals = await client.readContract({ address: token, abi: erc20Abi, functionName: "decimals" });
const units = parseUnits("1.5", decimals);        // 1500000n for USDC (6); 1500000000000000000n for DAI (18)
console.log(`${formatUnits(units, decimals)} ${symbol} = ${units} base units (decimals=${decimals})`);
```

`parseUnits` (or `ethers.parseUnits`) is not a convenience — it is the check. Hand-multiplying by `1e6` in a
float, or copying `1000` from a REST field into a human-facing prompt, is how the 1000× case happens.

### Step 1 — Read `decimals()` from the contract; do not hardcode 6

One `eth_call` settles it. `0x313ce567` is the `decimals()` selector; the result is a `uint8` right-padded to
32 bytes:

```bash
curl -sS -X POST https://mainnet.base.org -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{"to":"0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913","data":"0x313ce567"},"latest"]}'
# → "0x…06"  = 6 decimals (USDC on Base)
```

### Step 2 — Assert the chain id before you touch the token

```bash
curl -sS -X POST https://mainnet.base.org -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}'
# → "0x2105" = 8453  (Base mainnet; Base Sepolia is 84532, Ethereum mainnet is 0x1 = 1)
```

Assert it against the intent, not against "the wallet connected". The failure mode in the corpus is a transfer
that succeeded on a chain nobody wanted — a wrong-chain send is not necessarily rejected by the wallet.

### Step 3 — Resolve the token by address, and log the whole tuple

The identity of an asset is `(chain id, contract address)`. Log all four fields together so a mismatch is
visible without a second lookup:

```text
chain=8453  token=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913  symbol=USDC  decimals=6
```

Two useful consequences of doing it this way: the same symbol on two chains is *not* the same asset (compare
the Base and Ethereum USDC addresses — different contracts, both `"USDC"`), and a symbol you did not expect
from an address you trusted is a real finding, not a display bug.

### Step 4 — Check the recipient and who pays gas

- **Recipient**: there is no on-chain name resolution. Check `0x` + 40 hex characters + the EIP-55 checksum
  with a library that implements it (`eth_utils.to_checksum_address`, viem's `isAddress`). Do not hand-roll
  EIP-55 — `hashlib` has SHA3, not Keccak, so a hand-written "checksum" silently accepts wrong addresses.
- **Gas**: confirm a **native** balance on the same chain as the token, greater than zero. If the USDC sits on
  chain A and the task wants chain B, that is two operations — bridge, then transfer — not one, and each has
  its own gas cost.
- Ask explicitly *who* pays: a marketplace that "pays the reward" still usually makes you pay the transaction
  that claims it.

### Step 5 — Check the platform-side state, not the HTTP status

- **TaskBounty**: a payout `POST` returning 200 covers *future* claims; an already-AWARDED task can still show
  `solver_readiness: payout=fail`. Watch the `open` inventory, not the readiness of a historical row.
- **Superteam Earn**: `403 Insufficient credits` is a gate separate from profile completion. Keep deliverables
  and public links ready and retry when credits allow.
- **Opire**: merge ≠ payment. The publisher triggers payout from a dashboard, and platform trust tiers decide
  whether "advertised $150" is worth anything.

In all three: re-read the platform's own state field **in the context of the specific task** before treating a
submission as done.

### Step 6 — Send the smallest useful amount first, then verify on the chain

Do a small transfer over the *same* chain, token and recipient. Verify by transaction hash on a block explorer
that (a) it was mined, (b) the token contract is the expected one, and (c) the value in base units equals the
equation from Step 0. Only then send the remainder. This is the only check that catches a mistake nobody
anticipated, which is exactly the kind of mistake an irreversible action punishes.

### Step 7 — For agents: compute → display → sign, never compute → sign → display

Because there is no retry, the decoded parameters have to be visible **before** the signature, in a form
someone can reject:

```text
SIGN REQUEST
  chain:     8453 (Base mainnet)
  token:     0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913  USDC  decimals=6
  amount:    1.5 USDC = 1500000 base units
  to:        0x<recipient>
  gas payer: 0x<my address>, native ETH balance <x>
  effect:    irreversible once broadcast
```

This is the same rule as any destructive operation: show the **resolved target**, not the shorthand the user
typed. A tool that signs and then explains has already spent the money.

### Putting it together: a preflight that can refuse

The steps above are only a gate if a mismatch stops the signer. This runs on stdlib alone, so it can sit in
front of any signer (tested against Base mainnet, 2026-10-02):

```python
#!/usr/bin/env python3
"""Refuse a payout intent unless chain / token / decimals / symbol all match it."""
import json, sys, urllib.request
from dataclasses import dataclass
from decimal import Decimal

RPCS = {1: "https://ethereum.publicnode.com", 8453: "https://mainnet.base.org"}
SELECTOR_DECIMALS, SELECTOR_SYMBOL = "0x313ce567", "0x95d89b41"


@dataclass(frozen=True)
class Intent:
    chain_id: int
    token: str        # contract address, not a symbol
    symbol: str       # what the contract must say
    decimals: int     # what the contract must say
    amount: Decimal   # human amount, e.g. Decimal("1.5")


def rpc(chain_id: int, method: str, params: list) -> str:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(RPCS[chain_id], data=payload, headers={
        "Content-Type": "application/json",
        "User-Agent": "payout-preflight/1.0",   # public RPCs 403 the default urllib UA
    })
    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.load(response)
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def _decode_string(raw: str) -> str:
    if len(raw) < 130:
        return ""
    length = int(raw[66:130], 16)
    return bytes.fromhex(raw[130:130 + length * 2]).decode("utf-8", "replace")


def check(intent: Intent) -> list[str]:
    problems = []
    actual = int(rpc(intent.chain_id, "eth_chainId", []), 16)
    if actual != intent.chain_id:
        problems.append(f"chain: intent {intent.chain_id} but endpoint answered {actual}")

    decimals = int(rpc(intent.chain_id, "eth_call",
                       [{"to": intent.token, "data": SELECTOR_DECIMALS}, "latest"]), 16)
    if decimals != intent.decimals:
        problems.append(f"decimals: intent {intent.decimals} but contract says {decimals}")

    symbol = _decode_string(rpc(intent.chain_id, "eth_call",
                                [{"to": intent.token, "data": SELECTOR_SYMBOL}, "latest"]))
    if symbol != intent.symbol:
        problems.append(f"symbol: intent {intent.symbol!r} but contract says {symbol!r}")

    if intent.amount <= 0:
        problems.append(f"amount: {intent.amount} is not a positive send")
    return problems


def main() -> int:
    intent = Intent(chain_id=8453,
                    token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                    symbol="USDC", decimals=6, amount=Decimal("1.5"))
    units = int(intent.amount * (10 ** intent.decimals))
    print(f"intent: chain={intent.chain_id} token={intent.token} "
          f"{intent.amount} {intent.symbol} = {units} base units")
    problems = check(intent)
    if problems:
        for problem in problems:
            print(f"REFUSE: {problem}", file=sys.stderr)
        return 1
    print("OK: chain, contract and decimals all match the intent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Verification

Every on-chain number below was read on **2026-10-02** with the commands shown, and the preflight was run in
both directions — a matching intent must pass, a mismatched one must be refused.

Base mainnet, chain id and the token that must agree with the intent:

```text
eth_chainId on https://mainnet.base.org                     → 0x2105   (8453)
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 symbol()         → "USDC"
0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 decimals()       → 6
0x4200000000000000000000000000000000000006 decimals()       → 18        (WETH — same call, different answer)
```

Ethereum mainnet, for the "same symbol, different asset" point:

```text
eth_chainId on https://ethereum.publicnode.com              → 0x1      (1)
0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 symbol()         → "USDC"
0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 decimals()       → 6
```

The refuse path, which is the whole point — same script, only the token address changed:

```text
$ python3 preflight.py          # intent: Base USDC, 1.5, decimals=6
intent: chain=8453 token=0x833589… 1.5 USDC = 1500000 base units
OK: chain, contract and decimals all match the intent

$ python3 preflight.py          # token swapped to 0x4200…0006 (WETH), intent still says USDC/6
REFUSE: decimals: intent 6 but contract says 18
REFUSE: symbol: intent 'USDC' but contract says 'WETH'
```

Pass criterion for your own version: given an intent, it **exits non-zero** when the chain id, token address,
decimals/ symbol, or the sign of the amount disagrees with it. A preflight that prints the numbers but does
not refuse on mismatch is a log line, not a gate — and for an irreversible action, a log line is too late.

## Notes

- **Deep dives, in the order this checklist uses them**: [USDC base units vs human
  amounts](./usdc-base-units-vs-human-amounts-agent-marketplaces-ru.md) (long-form, Russian — it is the 1000×
  case in detail), [USDC arrived on Ethereum instead of Base with 0
  ETH](./usdc-ethereum-instead-of-base-zero-eth-gas.md), [TaskBounty payout POST succeeds but readiness
  fails](./taskbounty-payout-api-ok-readiness-still-fail.md), [Superteam Earn `Insufficient
  credits`](./superteam-earn-api-insufficient-credits.md), [Opire bounty
  hunting](./opire-bounty-hunting.md).
- **Decimals are per-contract, not per-symbol.** USDC and USDT are 6 on most EVM L2s; WETH and DAI are 18.
  Verified above: the *same* `decimals()` call returns 6 for USDC and 18 for WETH on the same chain.
- **Testnet is not a rehearsal for mainnet identity.** Base Sepolia (84532) faucet USDC has a different contract
  address from Base mainnet USDC (8453); "it worked on Sepolia" says nothing about the mainnet intent.
- **Platform trust tiers** (from the Opire lesson): escrow-backed (Opire via Stripe, Immunefi) > platform-credit
  tokens > unknown tokens. The advertised amount is not the expected value — the payout mechanism is.
- Chinese symptom phrases this lesson answers, for retrieval: 「USDC 基本单位」「付了 1000 倍」「USDC 打到了
  Ethereum 主网」「0 ETH 付 Gas」「solver_readiness」「赏金平台 payout 成功但领不到」.
- `misakanet_search` for the individual failures; this lesson exists to be the ordered list in front of them.
