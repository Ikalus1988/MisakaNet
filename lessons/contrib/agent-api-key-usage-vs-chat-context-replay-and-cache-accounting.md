---
title: "为什么 AI 编码代理的 API Key 用量是普通聊天的上百倍：上下文重放 + 缓存统计口径（附本地台账与官网余额对不上的原因）"
domain: "agent"
tags:
  - "dsh"
  - "deepseek"
  - "token-usage"
  - "prompt-cache"
  - "cost-meter"
  - "agent-loop"
  - "context-replay"
  - "subagent"
  - "cost-optimization"
  - "api-key"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3312"
summary_plain: "用户在 DeepSeek 官网「API 用量」里发现自己 DSH（DeepSeek Harness）用的那把 key 占了绝大部分 token，怀疑代理在乱烧钱。"
trigger: "为什么 AI 编码代理的 API Key 用量是普通聊天的上百倍：上下文重放 + 缓存统计口径（附本地台账与官网余额对不上的原因）. 用户在 DeepSeek 官网「API 用量」里发现自己 DSH（DeepSeek Harness）用的那把 key 占了绝大部分 token，怀疑代理在乱烧钱。"
verify: "① 读 `E:\\Deepseek\\dsh-data\\.dsh\\storages\\cost-meter\\ledger.json`：`days[]` 每项含 input / cacheRead / output / calls / cost，以及 `byProviderModel`、`sessions[]`（可定位是哪个会话烧的）；`days[d].cacheRead /…"
provenance:
  issue: "#3312"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用户在 DeepSeek 官网「API 用量」里发现自己 DSH（DeepSeek Harness）用的那把 key 占了绝大部分 token，怀疑代理在乱烧钱。
本地三份台账互相矛盾，进一步加深困惑：
1) DSH 的 cost-meter 台账 `E:\Deepseek\dsh-data\.dsh\storages\cost-meter\ledger.json` 15 天算出 **¥6.36**；
2) 同一账号余额口径（`.dsh-usage.json` 的 `history`，16 天）实际扣了 **¥40.64** —— 差约 6 倍；
3) 缓存报告显示单个会话 **610 次请求 / input 63.49M / cached 60.63M（命中 95.5%）/ output 仅 754.4K**，输入是输出的 84 倍。

## Root Cause

1) **agent 循环天生重放上下文**：LLM 请求是无状态的，每一步都要把整段会话（系统提示 + 全部历史 + 工具 schema + 工具输出）重新发一遍。实测 15 天 1,843 次请求：cacheRead 415.7M + 新输入 13.1M，**平均每次请求要送 ≈23 万 token 上下文**，而输出总共只有 1.9M（≈1,040/次）。官网按 token 计「用量」，所以看到的几乎全是这把 key 的输入重放，而不是模型「说了多少话」。
2) **prompt cache 只降单价、不降用量计数**：命中率 95.5% 时账单便宜了，但官网 token 计数依然按全量累加，所以「占大头」的观感不会因为缓存而消失。
3) **本地 cost-meter 的数不能当账**：它的配置 `includeSubagentCost: false`（子代理的 token 不计入台账），价格表按 USD 定价 × 7.2 汇率折算、并采用很低的 cache-hit 单价（实测反推：新输入 ≈¥0.26–0.51/M，cache-hit ≈¥0.004–0.037/M）。所以 15 天 ¥6.36 与余额口径 ¥40.64 必然对不上。
4) **空闲击穿缓存 TTL**：缓存报告里 14.8h / 9.7h 空闲后各出现一次全前缀重计费（108.5K、84K token），另有 820K token 是 provider 侧 TTL/驱逐导致、无法归因。
5) **多凭据并存会造成误判**：余额账本（`.dsh-usage.json` 的 `accounting.books`）显示 2026-10-11 起另外两把凭据完全为 0，全部消耗集中在当前这一把 —— 于是「某把 key 占大头」其实是「只剩这一把在用 + agent 循环本身耗量大」的叠加。

## Fix

降本清单（按收益排序，均已在本机实测过）：
1) **任务结束就开新会话**：成本 ≈ 上下文长度 × 步数，长会话是复利；单会话跑到 600+ 请求、上下文 190K+ 时，每步都在重发这 190K。
2) **及早压缩**：本会话 47 次折叠「毛省 383M token / 净省 382M token」，是目前最大的单一杠杆；越早压越省（等上下文爆了再压，压缩调用本身也贵）。
3) **连续作业，别让会话空腹**：缓存 TTL 一过，回来第一条就把整个前缀按新输入重算。
4) **砍常驻注入**：`context_audit` 实测每轮固定开销 ≈6.9K token（AGENTS.md 1.1K + 技能描述 357 + 58 个工具 schema 5.4K），乘以 1,843 次 ≈ 1,270 万 token；Hindsight 每轮提醒（≈1.8K）也在这个量级。
5) **把账算对**：以官网为准；cost-meter 只当趋势看（且它默认不含子代理）。子代理、插件、标题生成、压缩摘要都走同一把 key，要一起计。
6) 大批量、可容忍延迟的任务放到 DeepSeek 的错峰时段跑（cost-meter 自带谷峰提示）。

## Verification

① 读 `E:\Deepseek\dsh-data\.dsh\storages\cost-meter\ledger.json`：`days[]` 每项含 input / cacheRead / output / calls / cost，以及 `byProviderModel`、`sessions[]`（可定位是哪个会话烧的）；`days[d].cacheRead / days[d].calls` 就是「平均每次重发多少上下文」。
② 读 `E:\Deepseek\dsh-data\.dsh\.dsh-usage.json`：`accounting.books[<id>].days[<day>].debitUnits / 1e8` = 该凭据当天扣的人民币；逐日矩阵能直接看出「是不是只有一把 key 在花钱」。
③ 用 `acp_cache` 看单会话账：total input / total cached / total output、miss 三分类（new content / compress re-pay / upstream-TTL 未归因）、以及 body stability 的 mid-history divergence 计数 —— 这是判断「输入重放」而非「输出过多」的直接证据。
④ 用 `context_audit` 量每轮固定注入（指令链 / 技能目录 / 工具 schema / MCP 工具面），确认可裁剪的常量开销。
⑤ 交叉验证：若官网「API 用量」里某 key 占比接近 100%，且本地账本显示同期其他凭据 debit 为 0，即可确认「消耗集中 + 循环重放」这一结论，而不是模型输出变长。
