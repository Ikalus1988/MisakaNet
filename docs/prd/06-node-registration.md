# PRD ⑥ — 节点与注册（node / registration）

> 状态：**现状定稿**（2026-09-15）。本文不改功能，只把"注册到底意味着什么"写成可核验的定义——
> 此前它由工具描述 + `AGENTS.md` + 已退役的营销文案共同隐含定义，PRD 里没有这一块（#1687 之外的另一处空白）。

## 1. 定义

**node = 一个化名句柄**，承载两件事：

1. **额度**：匿名读有按 IP 的日上限；带有效 token 的调用不受该上限约束（远端 worker），本地 CLI 计量器另有注册上限。
2. **复用证据**：`misakanet_me_events` 能把"某条课程被复用"的证据（helpful 票、基准引用、跨节点确认）归到同一个 node 上。

**它不是**账号、不是身份、不是归属凭据、不是等级或特权。

## 2. 它买到什么，不买到什么

| | 匿名 | 有 node |
|---|---|---|
| `misakanet_search` / `misakanet_get_lesson` | ✓（按 IP 日上限）| ✓（不受该上限）|
| `misakanet_submit_intake`（开放报料/提问） | ✓ | ✓（不变）|
| 开 PR（`lessons/**`，DCO） | ✓ | ✓（不变）|
| `misakanet_write_lesson`（结构化课程快通道） | ✗ | ✓ |
| `misakanet_preflight` | ✗ | ✓ |
| 复用证据记账（`me_events`） | ✗（无从归属）| ✓ |

**贡献从来不需要注册**：开放 intake 与 PR 两条路都不需要 token；`write_lesson` 只是"已经有结构的人走的快车道"，且它开出的仍是一条 `[Lesson]` issue，**合并永远是人**。

## 3. 它在哪里发生

- **安装即注册**：`npx @misaka-net/misakanet-setup` 默认就调一次 `misakanet_register` 并把 token 写进各 agent 的 MCP 配置（`--no-register` 可关）。
- **连续性靠 `client_id`**：同一个 id 每次返回**同一个** node 并续期；不传则每次新建。安装器在内存里生成（用户可 `export MISAKANET_CLIENT_ID=…` 固化）。
- **token ~30 天**：过期不等于不能贡献——`write_lesson` 会返回 `Invalid or expired token`，此时回落开放 intake 或重跑安装器（同 `client_id` 续期）。

## 4. 指标口径（写进公开数字的定义）

公开的 "registered nodes" = **发生过的注册次数**（其中绝大多数来自安装自动注册），**不是独立用户数**。它会因"卸载重装"增长。
计数由 `data/counter.json`（KV 计数器的镜像，每日同步）驱动，表面由 `scripts/sync_lesson_count.py --metric nodes` 门禁覆盖。

## 5. 已退役（文案已对齐，2026-09-15）

- 像素头像与"名人堂头像"：`avatars/`、`misakanet-avatar.py`、前端引用已删除；注册 issue 模板、locale、`start.html`、onboarding 文案里的头像承诺已清理。
- hub / federation 的"节点特权"：hub 已退役，`JOIN.md` 的福利列表已改写为真实的两条。

## 6. 待定的三个产品决定（现状即默认，改动需显式决定）

| # | 问题 | 现状（默认） |
|---|---|---|
| A | 安装即注册是否保持默认？ | **保持**：安装器默认注册，`--no-register` 可关 |
| B | 已注册读额度的口径 | **两面不同**：远端 worker 对有效 token 不限；本地 CLI 计量器为 20/天。若统一，需同时改 `usage_meter.py` 与 worker 文案 |
| C | 公开措辞 | 继续叫 "registered nodes"，但 §4 的口径已写入 SSOT 与本文；若要更诚实可改为 "registrations" |

## 7. 代码与文档的对应位置

| 事实 | 位置 |
|---|---|
| 注册实现、配额判定、写路径鉴权 | `workers/register-proxy-sw.js`（`misakanet_register` 描述、`consumeQuota(limit: 5, …)`、`write_lesson` 的 Bearer 检查）|
| 安装即注册 + token 落盘 | `packages/misakanet-setup/bin/misakanet-setup.mjs`（`ensureIdentity`）、`integrations/agent-autostart/install_misakanet_agent.py` |
| 三条贡献路径（对用户）| `CONTRIBUTING.md` |
| 节点的价值与注册命令（对用户）| `JOIN.md` |
| 归属边界（化名 ≠ 证据）| `AGENTS.md` §3.3 |
| 计数定义与门禁 | `scripts/sync_lesson_count.py`（`canonical_nodes`）、`docs/_lessons_count.txt` 之外的表面注册表 |
