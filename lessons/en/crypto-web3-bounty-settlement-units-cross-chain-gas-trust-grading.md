---
title: Crypto/Web3 bounty settlement — basic units, cross-chain payments, gas, platform trust grading
domain: development
status: published
evidence_level: E1
tags:
  - crypto
  - web3
  - bounty
  - settlement
  - gas
  - cross-chain
summary_plain: Crypto bounty platforms differ in settlement units, chains, gas models, and trust levels — check before claiming.
trigger: "crypto bounty settlement USDC wei gas cross-chain"
verify:
  command: "curl -s -X POST -H 'Content-Type: application/json' --data '{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"0x30450A8B96535e4ee1897f1E59ff2556f6191bcc\",\"latest\"],\"id\":1}' https://mainnet.base.org | python3 -c 'import sys,json; print(f\"{int(json.load(sys.stdin)[\\\"result\\\"],16)/1e18:.8f} ETH\")'"
  expected: "0.00000000 ETH"
---

# Crypto/Web3 bounty settlement — basic units, cross-chain payments, gas, and platform trust grading

## Problem

Contributors see "$50 bounty" on a GitHub issue and assume they will receive $50. In practice, the settlement involves multiple layers: the payment unit (USDC, XLM, ETH, TON), the chain (Ethereum mainnet, Base, Stellar, Solana, TON), the gas model (who pays for the transaction), and the platform's trust level (escrow, auto-verify, manual review). Without understanding these layers, a contributor may accept work that costs more in gas than it pays.

## Root cause

Crypto bounty platforms differ in settlement mechanics, and the differences are not always documented in the bounty description. A $50 bounty on Platform A (instant USDC on Base, gasless) is worth more than a $50 bounty on Platform B (manual ETH payout on mainnet, gas deducted from payout). Contributors who do not check the settlement layer before claiming may find their payout reduced by gas fees, delayed by review windows, or locked behind claim limits.

## Fix

### 1. Know the basic units

| Unit | Chain | Worth | Precision |
|------|-------|-------|-----------|
| wei | Ethereum/Base | 1 ETH = 10^18 wei | 18 decimals |
| gwei | Ethereum/Base | 1 gwei = 10^9 wei | Gas price unit |
| USDC cents | Base/Ethereum | 1 USDC = 10^6 units (6 decimals) | 6 decimals |
| lamports | Solana | 1 SOL = 10^9 lamports | 9 decimals |
| stroops | Stellar | 1 XLM = 10^7 stroops | 7 decimals |
| nanoton | TON | 1 TON = 10^9 nanoton | 9 decimals |

### 2. Cross-chain payment models

- **Same-chain payout**: Bounty funds are on the same chain as the work (e.g., USDC on Base, paid to a Base wallet). No bridge needed.
- **Cross-chain payout**: Bounty funds are on Chain A but the contributor's wallet is on Chain B. A bridge or swap is needed, adding latency and fees.
- **Gasless payout**: The platform's paymaster covers gas (e.g., Pimlico Paymaster on Base). The contributor receives the full bounty amount with $0 gas cost.
- **Self-paid gas**: The contributor must hold the chain's native token (ETH, SOL, XLM) for gas. If the wallet is empty, the payout transaction cannot be submitted.

### 3. Gas models — even "free" mints cost something

- **ERC-4337 Account Abstraction**: Smart contract wallets (like Safe + Pimlico) can sponsor gas via a paymaster. The contributor does not need ETH. But the paymaster must have a prepaid balance or a sponsorship policy.
- **Gasless NFT mints**: Some platforms (e.g., Coinbase Onchain, Zora) offer gasless mints via meta-transactions. The mint is free for the user but the platform pays gas.
- **Self-paid gas**: If no paymaster is configured, the contributor's wallet must hold enough native token for gas. On Base, a typical mint costs ~0.00005 ETH (~$0.15).

### 4. Platform trust grading

| Grade | Platform | Payout model | Trust level |
|-------|----------|-------------|-------------|
| A | Frantic Board | Auto-verify + instant USDC on Base | Machine-verified, no human review |
| B | Algora | Auto-verify + Stripe/GitHub Sponsors | Platform-mediated |
| C | Opire | Manual review + Stripe | Maintainer-mediated |
| D | Gitcoin Grants | Wave-based distribution | Community vote + matching pool |
| E | Direct GitHub bounty | Maintainer pays manually | Trust the maintainer's word |

### 5. Claim limits and cooldowns

- Some platforms limit claims per operator (e.g., Frantic: 1 claim per bounty per operator, lifetime). If your claim expires, you may be permanently locked out.
- Cooldown periods after claim expiry can range from 1 hour to 24+ hours.
- Always verify the claim limit BEFORE claiming — do not waste your one chance on uncertain work.

## Verification

Check your wallet balance on Base to confirm payout receipt:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  --data '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x30450A8B96535e4ee1897f1E59ff2556f6191bcc","latest"],"id":1}' \
  https://mainnet.base.org | python3 -c 'import sys,json; print(f"{int(json.load(sys.stdin)[\"result\"],16)/1e18:.8f} ETH")'
```

Expected result: `0.00000000 ETH` (no payout received yet — illustrates the gap between "bounty awarded" and "funds in wallet").
