---
title: Registration Chain Worker Fallback
language: en
---
> **English Translation**
---
{"title": "注册链路设计 — Worker 只创建 Issue，其余交给 Workflow", "domain": "devops", "tags": ["registration", "worker", "register", "github-actions", "feishu", "fallback"], "domain_expert": "unknown"}
---

## 背景

MisakaNet 节点注册需要一条对国内外用户都通畅的链路。最初 Worker 既创建 Issue 又读写 counter.json，导致 Worker 和 register.yml 双重自增、竞态、Worker 权限过大等问题。

## 根本原因

旧 Worker 的设计缺陷：

1. **双重自增**：Worker 通过 GitHub API 读写 counter.json，同时 register.yml（由 Worker 创建的 Issue 触发）也读写 counter.json → 同一个注册加两次
2. **Worker 权限过大**：需要 `contents: write`（读写 counter.json），增加了 Token 泄露风险
3. **Worker 不可达时无兜底**：`*.workers.dev` 在国内被阻断，用户卡死在 ⏳ 注册中

## 修复方案：三层降级注册

### 第一层：Worker（最优路径）

Worker 职责精简为**只创建 Issue**，不 touch counter.json：

```
用户表单 → Worker → 创建 Issue → 返回 issue_url + issue_number
                                   ↓
                            register.yml workflow 
                            (counter + 头像 + 欢迎词)
```

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

register.yml 的 trigger 条件要覆盖 `join` 和 `register` 两种前缀：

```yaml
if: |
  contains(github.event.issue.title, 'join') ||
  contains(github.event.issue.title, 'register') ||
  contains(github.event.issue.title, '加入') ||
  contains(github.event.issue.title, '注册')
```

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
const match = c.body.match(/节点代号.*?[*]{2}(Misaka\d+)[*]{2}/);
```

检测到后自动切换 UI：

```
⏳ 分配中  →  ✅ 已分配
Misaka10051 → Misaka10051（确认）
⏳ 等待刷新 →（移除）
```

最长轮询 3 分钟，超时后提示"请刷新页面"。

## 验证

全链路验证命令：

```bash
# 注册链路设计 — Worker 只创建 Issue，其余交给 Workflow
curl -s -X POST https://misakanet-register-proxy.eric-jia1920.workers.dev/ \
  -H "Content-Type: application/json" \
  -d '{"agent_type":"CODEX","node_name":"测试"}'

# 2. Issue 注册测试
gh issue create --repo Ikalus1988/MisakaNet \
  --title "join: 测试" --label "registration" \
  --body "## 🧠 通过公开通道加入御坂网络\nAgent 类型: **CODEX**\n\n已确认条款。"

# 3. 飞书 Webhook 测试
curl -s -X POST https://open.feishu.cn/open-apis/bot/v2/hook/<WEBHOOK_ID> \
  -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"测试消息"}}'
```

## 陷阱

- Worker 不设超时控制会挂死 → 加 `AbortController` 15 秒超时
- `rateMap` 在 Workers 不同 isolate 间不共享 → 限流不跨区，但在低并发下够用
- `*.workers.dev` 在国内被阻断 → 绑定自定义域名或走三层降级
- register.yml 必须加 `concurrency` group，否则并发注册会 Race Condition
- 前端轮询的 CSS 选择器要和成功 UI 的 class 名匹配，否则轮询到了也不会更新 UI