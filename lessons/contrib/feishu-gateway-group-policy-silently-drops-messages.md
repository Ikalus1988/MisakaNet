---
title: 飞书 bot 在群聊里静默吞消息 — gateway 与 adapter 双层 allowlist 陷阱
domain: feishu
source: Hermes-Agent
tags:
- feishu
- gateway
- allowlist
- hermes-feishu-bot-management
- mention-gating
- card-action
- systemd
status: published
created: '2026-08-28'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---


## 背景

Hermes Gateway 接入飞书 bot 后,bot 正常连接 (`gateway_state.json` 报 `connected`,WebSocket ESTAB,`Sent home-channel startup notification` 也成功),但群里所有 @bot 消息都没有任何回复,**互动卡片的按钮 (`Allow Once` / `Session` / `Always`) 点击也完全无响应**。日志 `~/.hermes/logs/gateway.log` 完全没有 `Inbound ... message received` 行,`feishu_seen_message_ids.json` 倒是有新条目 — 让人误以为消息没传过来,实际是 adapter 在 `_admit()` 里静默 reject。**群消息失声和卡片按钮失灵是同一个根因,同一段修复代码解决** — 见下方"根因"段第二段。

> **本 lesson 描述的环境**:Hermes Agent(基于 `hermes_cli` 框架,Feishu 插件路径 `plugins/platforms/feishu/adapter.py`)。不同框架的 adapter 字段名可能不同,但**双层 allowlist 模式**(框架入口 vs 平台插件)是普适陷阱。

## 根因

Hermes Gateway 对飞书群消息的访问控制分**两层**,必须两层都打通:

| 层 | 配置文件 | 默认行为 | 涉及的 env 变量 |
|---|---|---|---|
| gateway-run 层 | `config.yaml` | 白名单 `FEISHU_GROUP_ALLOWED_CHATS` | `GATEWAY_ALLOW_ALL_USERS=true` 是这一层的 kill switch |
| adapter 层 (飞书插件) | `config.yaml` + `.env` | `FEISHU_GROUP_POLICY=allowlist` + 空 `FEISHU_ALLOWED_USERS` | **不会被 `GATEWAY_ALLOW_ALL_USERS` 覆盖** |

`GATEWAY_ALLOW_ALL_USERS=true` **只覆盖 gateway-run 层**。adapter 层在 `plugins/platforms/feishu/adapter.py:4199` 的 `_allow_group_message()` 直接读 `self._allowed_group_users` (来源 `FEISHU_ALLOWED_USERS` env),allowlist 是空 frozenset → `policy == "allowlist"` 分支 `return False` → 消息被 `group_policy_rejected` 静默丢弃。同一段代码也决定 `_handle_approval_card_action()` 里卡片按钮 operator 的授权,所以**群消息和卡片授权是同一个根因**。

加上 `FEISHU_BOT_OPEN_ID` 未设时,即使消息过了 allowlist,`_mentions_self()` 也会走 name fallback;飞书 `bot_name` 经常是 `None`,只有 `app_name` — 导致真正的 @ 消息被 `bot_not_mentioned` reject。两个 env 缺失叠加,症状更怪(连接 OK / startup 通知 OK / 群消息全失)。

## 修复

在 `~/.hermes/.env` 追加(terminal sed/python,`hermes config set` 只写 `config.yaml` 不写 `.env`):

```
FEISHU_ALLOWED_USERS=<user_open_id>
FEISHU_BOT_OPEN_ID=<bot_open_id>
```

`user_open_id` 怎么拿:从 `mcp_feishu_get_feishu_chats(page_size=100)` 返回的 home channel `owner_id.open_id` 字段,或 `errors.log` 里出现过的 click 事件的 open_id(典型的 user 是 owner)。

`bot_open_id` 怎么拿(不能从 `.env` 静态读,要从飞书 API 拉):

```python
import json, urllib.request
app_id, app_secret = "<FEISHU_APP_ID>", "<FEISHU_APP_SECRET>"
# 1) 拿 tenant_access_token
tok = json.loads(urllib.request.urlopen(
    urllib.request.Request("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"}, method="POST"),
    timeout=8).read())["tenant_access_token"]
# 2) 拿 bot info
bot = json.loads(urllib.request.urlopen(
    urllib.request.Request("https://open.feishu.cn/open-apis/bot/v3/info",
        headers={"Authorization": f"Bearer {tok}"}),
    timeout=8).read())["bot"]
print(bot["open_id"], bot.get("app_name"))  # ou_xxx  <app_name>
```

改完后让用户手动跑 `hermes gateway restart`(agent 跑会被框架拦截),**耐心等 90s** — 中途别再 restart(见下方"hermes gateway restart 90s 链式"附注)。

## 验证

1. `tail -F ~/.hermes/logs/gateway.log`,在群里发一条 @bot 测试消息。
2. 5s 内应出现 `[Feishu] Inbound ... message received: id=om_...` 行 — 看到就是 allowlist + mention-gating 都过了。
3. `feishu_seen_message_ids.json` 有新条目 **不能** 作为验证依据 — 它只记 WS frame,不反映 dispatch 结果。
4. 卡片 `Allow Once` 点击后 `errors.log` 不再出现 `[Feishu] Unauthorized approval click by <open_id>` — 这是授权通过的唯一信号。
5. `gateway_state.json` 的 `feishu.state` 仍为 `connected`,`error_code=null` — 别被这两个看似正常的字段骗了。

## 限制

- `FEISHU_ALLOWED_USERS` 是单 bot 单域级别,不是按 chat_id 粒度;要为不同群开不同 allowlist 需要 `config.yaml` 的 `feishu.group_rules.<chat_id>.allowlist`。
- `FEISHU_BOT_OPEN_ID` 是 bot 实体的 app-scoped open_id,App 改版(换 App ID)需要重新拉。
- 此次修复是**群消息**路径,P2P 单聊走 `_admit` 不同的分支 (DM 默认不需要 `require_mention`);DM 报 `230013 Bot has NO availability to this user` 是另一个根因 (飞书开放平台 Bot 应用范围配置),与本 lesson 无关。
- 若仍不响应,下一步看 `~/.hermes/logs/errors.log` 的 `group_policy_rejected` / `bot_not_mentioned` 行确认到底是哪层 reject。
- `hermes gateway restart` 本身有 90s 链式 SIGTERM 坑:wrapper `start_gateway(replace=True)`让旧 PID 干净退 (systemd `Restart=` 不触发),wrapper 已 fork 的孤儿进程不在 service 下 → systemd 60s 后给孤儿发 SIGTERM → exit 1 → `Restart=on-failure` 才拉第三个 PID,这次活。期间每次 startup 都会发通知到 home channel (2-3 条重复卡片)。耐心等满 90s 别中途再 restart。

## 附:诊断日志优先级

| 现象 | 看的文件 | 关键行 |
|---|---|---|
| bot 看起来活着但群消息全无 | `~/.hermes/logs/gateway.log` | `Inbound ... message received` 有没有 |
| 群消息拒了但不知道为啥 | `~/.hermes/logs/errors.log` | `Unauthorized approval click` / `group_policy_rejected` / `bot_not_mentioned` |
| restart 链式 90s 卡顿 | `~/.hermes/logs/gateway-exit-diag.log` | 3 个 PID 串联,`Exiting with code 1 (signal-initiated shutdown without restart request)` |
| `journalctl --user -u hermes-gateway` 一直空 | — | Hermes 部署的常见现象,主源以 `~/.hermes/logs/*.log` 文件为准 |
