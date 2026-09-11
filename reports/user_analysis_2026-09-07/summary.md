# MisakaNet 数据分析总览

_报告生成于 2026-09-07T17:13:57.877681+00:00 (UTC)_

## 📊 数据规模

- **Cloudflare KV** namespace `d5fb6b0797b84d17b0586fb982231ffe`: **162 个 keys**
- **Email inbox**: **10 封邮件**
- **CF Account**: `6b92325b505f2b76aec49e9fe4195d31` (Ikalus1988)
- **邮箱 alias**: misakanet@agent.qq.com, bot@misakanet.org

## 🗂 KV 类别分布

| 类别 | 数量 | 占比 |
|------|------|------|
| `node` | 60 | 37.0% |
| `mcp_token` | 42 | 25.9% |
| `gap` | 19 | 11.7% |
| `intake_dedup` | 13 | 8.0% |
| `traffic` | 10 | 6.2% |
| `email-node` | 6 | 3.7% |
| `email-intake` | 5 | 3.1% |
| `helpful` | 3 | 1.9% |
| `feedback` | 2 | 1.2% |
| `(none)` | 1 | 0.6% |
| `rate` | 1 | 0.6% |

## 📈 关键发现


- **网络规模**: MisakaNet 当前有 **60 个节点** (`node:Misaka*`) 注册，
  但 `10112` 节点计数器在 KV 里，活跃 mcp_token 引用了 **41 个不同 node_id**
- **MCP 客户端**: **42 个 mcp_token**，分布在 19 种 agent 类型
- **入站邮件**: 5 封 email-intake（路由到 3 个节点）
- **知识盲区**: **19 个 gap**，用户搜过但没找到答案
- **流量**: 最近3 天 agent / crawler / mcp / pageview 都有活动
- **限频**: 至少 1 个邮件发件人（`hello@trymcpvault.com`）被限频

## 📑 报告清单

- [`summary.md`](summary.md) — 本文件：总览摘要
- [`user_profile.md`](user_profile.md) — 用户画像与行为分析
- [`kv_health_report.md`](kv_health_report.md) — KV 健康状态报告
- [`recommendations.md`](recommendations.md) — 行动建议清单
- [`raw_kv_dump.json`](raw_kv_dump.json) — 162 keys 完整 dump
- [`raw_email_dump.json`](raw_email_dump.json) — 10 封邮件完整 dump

## 🔐 安全说明

- 本次拉取 Cloudflare OAuth token 在 `~/.cf_oauth_token.json`（access_token + refresh_token）
- **建议**: 不再需要时执行 `rm ~/.cf_oauth_token.json` 删除本地凭据
- 报告全部为**本地文件**，未写入 KV/邮件