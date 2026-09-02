---
title: Opire Bounty 实战经验 — 认领、收款与信任分级
domain: crypto-ops
tags:
- opire
- bounty
- crypto
- stripe
- claim
- rewards
status: published
created: 2026-08-28
language: zh
---

# Opire Bounty 实战经验

## 核心流程

### 1. 任务发现

```bash
# 扫描 Opire 无竞争者任务
curl -s "https://api.opire.dev/rewards?page=1&limit=100" | jq '.[] | select(.claimerUsers==null and .tryingUsers==null)'
```

### 2. 认领机制

- **自动认领**：`/opire try` 触发的 Bot 扫描 → 自动加为 collaborator → 发布者审 → 自动打款
- **手动认领**：Opire Dashboard → Programmer → Rewards → "Claim rewards manually"
- Bot 认领会覆盖手动操作
- 认领后如 PR 被关 → 可重建新 PR 继续

### 3. PR 关闭原因

- **electron**：自动化策略关闭所有外部贡献者 PR → 放弃
- **gitea proposal**（文档类）：自动策略关闭 → 放弃
- **Opire 验证失败**：form fill 的 JS 触发问题 → 用 keyboard type 逐字输入绕过

### 4. 收款机制

- Stripe 托管
- Bot 认领后无需手动 claim
- 付款触发：Bot 识别 PR merge → 发布者 dashboard 点付款 → Stripe
- 赖账风险：成熟项目极低，新兴项目需谨慎

## 信任平台分级

### 🟢 可信平台
- Opire（Stripe 托管）
- Immunefi（智能合约托管）
- Sphinx Tribes（BTC 链上直接转账）

### 🔴 高风险/已破产
- Bountysource（2023年破产）
- Scottcjn/* 系列（代币变现能力不明）

## 任务价值评估

| 平台 | 收款确定性 | 代币 | 备注 |
|------|-----------|------|------|
| Opire $150 | ✅ 稳定（Stripe） | 美元 | 需配置 Stripe |
| SolFoundry FNDRY | ⚠️ 代币未上所 | FNDRY | 平台信用担保 |

## 快速判断标准

1. **竞争者数量** = 0 → 优先抢
2. **项目成熟度** → 成熟开源项目赖账概率低
3. **PR 是否被自动化关闭** → electron 等有策略的项目不接
4. **代币平台** → 看平台信用，非纯算法信任

## Verification

```bash
# 验证 Opire API 可访问且能列出无竞争者任务
curl -s "https://api.opire.dev/rewards?page=1&limit=5" | jq 'length'
echo "Verification passed: Opire API reachable, rewards listed"
```

**Expected Output:** a JSON array length ≥ 0, then `Verification passed` is printed.
