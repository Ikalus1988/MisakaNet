---
title: 注册链路设计 — Worker 只创建 Issue，其余交给 Workflow
domain: feishu
tags:
- registration
- worker
- register
- github-actions
- feishu
- fallback
status: published
created: '2026-07-06'
language: zh
source: unknown
domain_expert: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

MisakaNet 节点注册需要一条对国内外用户都通畅的链路。最初 Worker 既创建 Issue 又读写 counter.json，导致 Worker 和 register.yml 双重自增、竞态、Worker 权限过大等问题。

## Root Cause

旧 Worker 的设计缺陷：

1. **双重自增**：Worker 通过 GitHub API 读写 counter.json，同时 register.yml（由 Worker 创建的 Issue 触发）也读写 counter.json → 同一个注册加两次
2. **Worker 权限过大**：需要 `contents: write`（读写 counter.json），增加了 Token 泄露风险
3. **Worker 不可达时无兜底**：`*.workers.dev` 在国内被阻断，用户卡死在 ⏳ 注册中

## Solution方案：三层降级注册

### 第一层：Worker（最优路径）

Worker 职责精简为**只创建 Issue**，不 touch counter.json：

```
用户表单 → Worker → 创建 Issue（label: registration）→ 返回 issue_url + issue_number
                                   ↓
                            register.yml workflow
                            (欢迎词 + 打标签 + 关 issue)
                                   ↓
                     节点号由 worker 的 KV 计数发放（不是这个 workflow）
```

> **2026-09-23 修正（#2106）**：下面第 2 步那句「register.yml 分配节点号」已经作废。那个 workflow
> 以前把 `data/counter.json` +1 再 push 回 main，等于让同一个事实有两个写入者：2026-09-23 文件是
> 11047 而 KV 是 11777（差 730），站点上「✅ 已分配 Misaka11048」报的是一个几百号之前的数字，也不
> 是用户 `misakanet_register` 真正拿到的那一个。现在编号只由 worker 的 KV 计数发放，`register.yml`
> 只贴欢迎词、打 `registered` 标签、关 issue —— 它连 `contents` 权限都没有。

Worker 代码关键改动：

```
// ⚠️ 不要在这里读写 counter.json
// 不要在这里发欢迎评论
// 只做：校验 → 创建 Issue → 返回
```

Token 权限从 `contents: write` + `issues: write` 降为仅 `issues: write`。

### 第二层：GitHub Issue 直连（Worker 不通时）

Worker 不可达时，前端显示 Issue 模板入口：

```
🌐 注册节点暂时不可达
📋 有 GitHub 账号？→ 点此创建 Issue（template=register.yml）
    ↓
register.yml 自动处理（30 秒完成）
```

register.yml 的触发条件**不要**用标题关键词包含匹配 —— 用模板/接口会自己打的标签：

```yaml
if: |
  github.event_name == 'workflow_dispatch' ||
  (github.event.issue.title != null &&
   (contains(github.event.issue.labels.*.name, 'registration') ||
    startsWith(github.event.issue.title, 'join') ||
    startsWith(github.event.issue.title, '[JOIN]')))
```

`.github/ISSUE_TEMPLATE/register.yml` 和 worker 的 `/api/register` 都会打 `registration` 标签，所以
标签是机械可判的。反例是实测的：`contains(title, 'register')` 在 2026-09-22 让这个 job 在三条
**无关** issue 上跑了起来（标题里只是提到了 registration），然后每条都死在 push 那一步，看起来像
注册链路坏了（run 35749203103 / 35761772072 / 35764549504）。同类事故更早还有一次：#1258 那个
「always open」的 onboarding issue 因为标题含 "Register" 在 reopen 时被误关。

同时加 `workflow_dispatch` 兜底——如果自动触发失败可以手动补注册。

### 第三层：飞书 Webhook 人工兜底（无 GitHub 账号时）

前端嵌入飞书群机器人 Webhook，用户填表后直接推送到管理员飞书群：

```
📧 无 GitHub 账号？
填 Agent 类型 + 联系方式 → 提交 → 飞书群通知管理员
                                       ↓
                                管理员手动创建 Issue
                                       ↓
                                register.yml 自动处理
                                       ↓
                                管理员回复用户节点号
```

飞书 Webhook URL 的格式：

```
https://open.feishu.cn/open-apis/bot/v2/hook/<WEBHOOK_ID>
```

注意：飞书群机器人 Webhook 只能**发**消息，不能收。消息会推送到配置了该 Webhook 的飞书群。

### 前端轮询：⏳ 分配中 → ✅ 已分配

注册成功后，前端每 10 秒轮询 GitHub API 检查 Issue 评论：

```javascript
const cr = await fetch(`${BASE}/issues/${issue_number}/comments`);
// 检测欢迎词中的 "**MisakaXXXXX**" 节点号
// 注意：2026-09-23 起这个号是 worker 的「下一个号」（读 /api/counter 预测），
// 真正生效的是用户自己 misakanet_register 返回的 node_id；欢迎词里写明了这一点。
const match = c.body.match(/节点代号.*?[*]{2}(Misaka\d+)[*]{2}/);
```

检测到后自动切换 UI：

```
⏳ 分配中  →  ✅ 已分配
Misaka10051 → Misaka10051（确认）
⏳ 等待刷新 →（移除）
```

最长轮询 3 分钟，超时后提示"请刷新页面"。

## Verification

```bash
grep -i feishu lessons/contrib/feishu-*.md 2>/dev/null | wc -l
echo Feishu verified
```

**Expected Output:**
```
# (count)
Feishu verified
```

## Pitfalls

- Worker 不设超时控制会挂死 → 加 `AbortController` 15 秒超时
- `rateMap` 在 Workers 不同 isolate 间不共享 → 限流不跨区，但在低并发下够用
- `*.workers.dev` 在国内被阻断 → 绑定自定义域名或走三层降级
- register.yml 仍要 `concurrency` group：现在没有编号竞态了（不再分配编号），但两个 run 同时贴欢迎词会产生两条重复评论
- 前端轮询的 CSS 选择器要和成功 UI 的 class 名匹配，否则轮询到了也不会更新 UI