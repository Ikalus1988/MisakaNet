# Handoff — 2026-11-24（vol 47：确认闸门到底该由谁按下，以及 MCP 的「没有回答」）

> 承接 `handoff-2026-11-24.md`（vol 46，D1 读放大）。这一卷两条线，结局都很朴素：
> **插件 1.5.15 被驳回**（闸门是假的），**服务端把「没有回答」编成了一帧错误**（#5694）。
> 另外记一笔最贵的经验：**合并 ≠ 上线**，worker 修复合并后 5 小时仍未生效，唯一原因是等 owner 批部署。

---

## 1. 判断

### 1.1 提审快照取自「这台机器上已安装的实例」，而装了的那份会落后于仓库

1.5.15 是 13:12 打的包；同一天 15:07 / 15:12 又合了两笔（卡片只能挂在真实工具调用上）。不重装就
`ghost_contribution_prepare`，提上去的就是**没有那两笔修复的字节**。这次做对了：

```
ghost_forge_pack(dir) → ghost_forge_install(dir, namespace='local')
→ 逐字节核对已装副本与仓库构建（main.js / manual / ghost.json 全 SAME）→ prepare → submit
```

**判据**：提审前先问"这台机器上跑的那份和仓库 HEAD 是同一份字节吗"。安装不跟着仓库走，这是
宿主的设计（提审只承认已安装实例），不是可以绕的步骤。

### 1.2 审核真正在问的是一句话：**谁有权替用户说「同意」**

驳回理由拆开就是两条，两条都成立：

| 现状 | 为什么是假闸门 |
|---|---|
| 轮末没命中后，插件把「要沉淀就调 `misakanet_submit_intake(..., user_confirmed=true)`」注入给 agent | `user_confirmed` 由 **agent** 预置 = agent 替用户说话 |
| 卡供不出来时走 `confirm="direct"` 直发（仍需 `user_confirmed`） | 「没有卡就没有闸门」，等于没有闸门 |

于是闸门只剩两种**宿主独占、插件伪造不了**的证据：主机画的一次点击，或**用户自己发出去的消息**。
这一卷的另一半（另一会话完成，源仓 #5710）选了后者：卡只负责披露原文 + 6 位短码，插件订阅只读的
`message` 主题、**只认 `role=user`** 的消息；agent 转述、卡片按钮、确认框都不算数，短码 15 分钟、
绑定用户看过的那一版原文（改一个字就 `CONTENT_CHANGED`）、用一次即废（重放 `CODE_UNKNOWN`）。

**判据**：设计任何"用户确认"时，先问「这个'同意'是**谁**产生的字节」。由被约束的一方（agent）产生的，
无论叫什么名字都不是闸门。

### 1.3 手机端不是"点不动卡就没辙"——但聊天里的确认框也不是手机方案

宿主有原生确认弹窗 `cindy.confirm`（manifest 声明 `"confirm": true`；主机画壳、点击链路主机独占、
90 秒无人应答按"没同意"），**但它按来源呈现**：不带移动来源时确认框落在**桌面**；只有带有效
`mobilePageId`（从插件自己的移动端页面发起的请求）才由手机 Host 原生确认，且失效来源**不得回退桌面
弹窗**，按"没同意"处理。

再加上真机实测的两条：卡片上的按钮派生出的 `spawnCallId` 是**卡位**而不是一次工具调用（手册 §4.5），
点击之后插件自己发起的 `cindy.fetch` 被网络闸 0 ms 拒掉；手机/远程会话里卡片点击不回传 `card-action`。
**结论**：手机端可行的闸门只有「用户自己打的字」或「插件自己的移动端页面」，聊天里的卡片与确认框
都不构成手机端闸门。

### 1.4 「没有回答」是一种答案，而 SSE 流表达不了它

客户端按 MCP 规范带 `Accept: application/json, text/event-stream` 时走 SSE 分支，而
`notifications/initialized` 的内层回答是 **202 + 空正文**。包装层照旧 `JSON.parse("")`，抛错后落进
兜底分支，于是每台按规范发通知的客户端都会在握手之后收到一帧
`-32603 internal error: the handler did not return JSON`——一个它没问过、也不存在的失败（#5694）。

修法不是"顺手别报错"，而是**给"没有回答"一条能表达它的路径**：通知（无 `id`、非 batch）直接走
JSON 路径保持 `202` + 空正文；包装层遇到 202/204/空正文只结束流（#5698）。

**判据**：凡是把多个返回值塞进同一条流/同一个字段的封装，先问"空、无、不适用"怎么表达。表达不了的
封装会把"什么都没有"翻译成"出错了"。

### 1.5 手写 MCP 客户端别用 `startsWith("event:")` 判断是不是 SSE

SSE 分支的**首字节是 4 KiB 的 `:` 注释行**（`": " + 4092 空格`）。它是故意的：首字节必须在检索之前
离开缓冲区，否则整份响应在 ~3 s 后才到、链路先断（2026-10-31 实测首字节 8,100 ms）。注释行在 SSE 里
本来就必须被丢弃。

报告方那台 Mac 的 helper 用 `body.startsWith("event:")` 决定要不要按 SSE 解析，于是把整段当 JSON 解析 →
`Unable to parse MCP response`。正确做法：按 `content-type` 判断，或扫 `data:` 行并跳过 `:` 开头的行；
另外 **202/空正文 = 已接受、没有回答**，不是解析失败（不该重试）。

已写进 `docs/integrations/mcp-remote.md` 给手写客户端的那一节，避免下一个人再踩。

---

## 2. 数字（2026-11-24 收工，UTC）

| 项 | 值 | 判据 |
|---|---|---|
| 生产 worker | **693d171e7**（8 小时未动） | `curl -s misakanet.org/api/health` |
| 阻塞生产的唯一原因 | deploy run **45366745219** 自 09:36 起 `waiting` | `gh api '.../actions/runs?status=waiting'` |
| 3.21.0 | PyPI **3.21.0** / npm `latest` **3.21.0** / tag `v3.21.0` 08:11:40Z | 读 registry，不读 run 的颜色 |
| 3.22.0 | 发版 PR #5703 已开 | 下一轮入口 |
| 插件市场在售 | **1.5.14**（`release c1713e99…`） | `ghost_my_plugins` |
| 1.5.15 | 07:32:49Z 提审 → **08:06:29Z 驳回**（34 分钟）；`submission cmwudnny…`、`release ccf33c26…`、sha256 `5683028a…` | 驳回理由见 §1.2 |
| 1.5.17 | 14:44:38Z 提审（另一会话，短码闸门）；`submission cmwut2zrn…`、sha256 `14758f06…` | 审核中 |
| 服务端修复 | #5698 于 09:36:03Z 合并；**尚未上线** | 与第一行同一条 |
| 用例 | `node --test workers/mcp-*.test.mjs` **90 通过**；#5694 相关 3 条**先红后绿** | 把 `register-proxy-sw.js` 单独 stash 掉重跑 |
| 报告方实测 | SSE 正文 4,266（initialize）/ 4,230（通知）字节；JSON 路径 147 字节 | #5694 评论 |

`data/cindy-plugin-versions.json` 里仍写着 `community: 1.5.12`（11-19），而真实 KV 是 `1.5.14` —— **漂移**。
KV 是写对过的（当日写 + 回读），只是文件没跟上；下次写 KV 时把文件一起改对，别让"记录"和"事实"分开跑。

---

## 3. 悬着的账

- **只有 owner 能点**：deploy run `45366745219`（`release` environment）。合并了三个 worker 改动
  （#5678 每日 D1 成本看护、#5684 语句级计量、#5698 通知帧），一条都没上线，**都压在这一个批准上**。
- **等审核**：1.5.17（短码闸门）。过审后写一次 KV（`--community 1.5.17`），并顺手修正 §2 末尾那条漂移。
- **等报告方**：那台 Mac 的 helper 按 §1.5 改解析（服务端不再改了）。
- **1.5.15 已作废**：被驳回的版本号不再能提审，别再拿它重试。
- 3.22.0 发版 PR（#5703）合并后照旧读 registry 核对。

---

## 4. 下一轮入口

```bash
# 上线了没有：读 health 的 commit_sha，与 origin/main 的 workers/ 改动比
curl -s https://misakanet.org/api/health | jq -r .commit_sha
git fetch origin --prune && git diff <live_sha>..origin/main --stat -- workers/

# 谁在等 owner 批准
env -u GITHUB_TOKEN gh api 'repos/Ikalus1988/MisakaNet/actions/runs?status=waiting&per_page=10' \
  --jq '.workflow_runs[] | "\(.id) \(.name) \(.created_at)"'

# 发版到底发出去了没有（读 registry，不读 run 的颜色）
curl -s https://registry.npmjs.org/misakanet/latest | jq -r .version
curl -s https://pypi.org/pypi/misakanet/json | jq -r .info.version

# 市场在售版本与最近一次提审
#   ghost_my_plugins(query='misakanet')      → market.version / latestSubmission
#   过审后：python scripts/publish_cindy_plugin_version.py --community <在售版本>

# MCP 两条路径的形状（同一请求，只换 Accept）
for acc in "application/json, text/event-stream" "application/json"; do
  curl -sS -D- -o /tmp/b.bin -X POST https://misakanet.org/mcp \
    -H 'content-type: application/json' -H "accept: $acc" \
    --data-binary '{"jsonrpc":"2.0","method":"notifications/initialized"}' | head -3
  wc -c < /tmp/b.bin
done
```

---

## 5. 坑（本卷实际踩到的）

1. **同一工作仓两个会话并发时，`git add -A` 会把对方的在途改动卷进你的提交。** 实测差点把
   `workers/misakanet-cindy-plugin.test.mjs` 的 170 行（另一会话在做）提交进去。提交前先
   `git show --stat HEAD` 核一遍；已经卷进去了用 `git reset --soft HEAD~1` + `git reset` 拆开，
   再用精确路径 `git add <文件>`。
2. **`gh pr merge --squash` 报 "base branch policy prohibits the merge" 不是权限问题**，是 required
   check 正在新一轮跑（release-please 的分支刚被 bot force-update，旧 head 的绿不作数）。用 `--auto`
   排队，别加 `--admin` 绕过。
3. **release-please 的分支会被自动 force-update**：看到"刚才全绿"先确认 head 没变，再决定能不能合。
4. **`curl registry.npmjs.org/misakanet` 的整份 JSON 在本机管道里会被截断**（约 197 KB 处
   `Expecting ',' delimiter`）。读 `/latest`，或先落盘再解析。
5. **本地已装的插件副本 ≠ 仓库**（§1.1）。它只在 `ghost_forge_install` 那一刻同步。
6. **`GITHUB_TOKEN` 仍是失效的**：所有 `gh` / `git push` 都要 `env -u GITHUB_TOKEN`（本卷全程如此，
   已不再复述进坑列表，但忘一次就是 401）。
