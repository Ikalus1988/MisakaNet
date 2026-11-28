# Cindy Integration

> **状态（2026-11-03）**：Cindy 是第 **13** 个宿主，也是第一个**安装器不写任何文件**的宿主。
> 它的工具来自 Cindy 自己安装的插件包 `misakanet`（公开市场名「MisakaNet 故障记忆」）；
> 安装器只做两件事：**检测到这台机器上有 Cindy**，然后把这条手动步骤**打印出来**。
> `--verify` 对它回答**「查不了」**——插件装没装只在应用内可见，本进程读不到；这个答案是
> **退出码 2**（未知），不是 1（坏了）。

## 0. 为什么安装器不写文件

三条都实测过（2026-10-31 / 11-03）：

1. Cindy 没有 Claude Code / Codex 那种**用户级 MCP 配置文件**。它的工具由插件在自己的宿主内注册；
2. 插件内容存在**应用自己的 owner store** 里（一个安装登记表 + 应用数据目录），不是安装器可以写的路径；
   读它是越权，写它更不是安装器该做的事；
3. Cindy 的应用内行为规则来自**插件自带的手册**（`manual/misakanet/MANUAL.md`，随插件安装出现在助手的
   使用说明里），没有 `AGENTS.md` 这类文件可以注入。

所以写任何文件都会得到同一类假绿：**文件看起来装了，应用里却没有工具**。这是这个仓库其它每个宿主都在
避免的形状，Cindy 也一样——安装器打印步骤，`--verify` 说「查不了」，剩下的交给应用内安装。

## 1. 安装（一步，在 Cindy 里）

> **从插件市场装，别从 `.cindy` 文件装。** 宿主把**市场来源**的安装当作「跟随市场更新」的那一种——
> 新版上架，它自己就跟上。而**自签 `.cindy` 文件**装的实例在宿主里记的是 *local* 来源，**永远不跟随
> 市场更新**：市场发了新版本，它们那边也收不到（2026-11-23 实测：近 7 天仍有 25% 的插件检索跑在
> 1.2.x / 1.3.x 那两条老线上）。
> 已经用 `.cindy` 文件装过的，**卸掉再从市场装一次**，之后就自动更新了。
> 插件自己也会在会话第一轮提醒这件事，并把「你用的是哪个版本」写进首轮提示。

在 Cindy 的**插件列表 / 市场**里安装 **MisakaNet 故障记忆**（插件 id `misakanet`）。安装器会把这一句打印
出来：

```bash
npx @misaka-net/misakanet-setup --only cindy
```

```text
! Cindy：工具来自应用内插件「MisakaNet 故障记忆」（id: misakanet），安装器不写任何文件 →
  在 Cindy 的插件/市场里安装该插件；装好后在对话里让它调用 misakanet_search 复核
```

（上面第二条是安装器原样的输出；`!` 前缀表示"需要你做一步"，不是错误。）

插件源码在本仓库 [`.cindy-plugin/`](https://github.com/Ikalus1988/MisakaNet/tree/main/.cindy-plugin)：
`ghost.json`（清单）、`main.js`（电子脑）、`locales/en.json` 与 `locales/zh-CN.json`（文案）、
`manual/misakanet/MANUAL.md`（随包手册）、`assets/icon.png`。市场里发布的就是本仓库这个包（提审期间市场可能仍显示上一版），仓库已到 **1.6.13**（市场评审后同步：三态外发、CSPRNG client id、`detail="full"` 透传正文、提醒计数以内存为准、四个读工具带 `trust_notice`、移除未用的 `network` 声明、清单默认描述与 zh-CN 对齐、`me_inbox` 拒绝同时给两个查询编号、domain 过滤零命中单独标记、首轮公告带版本号与更新办法、自报通道头 `X-MisakaNet-Channel`、透传端点带回的 `plugin_version` 并在落后时说出口、只读重试与确认卡闸门并进唯一真身）；
审核通过后，仓库这与市场里的包内容一致。

### 1.1 社区通道的变体（`.cindy-plugin-community/`）

市场里的**社区投稿通道**（同一个插件 id `misakanet`，由发布者自己签名）和官方随包通道
**用同一份实现**。两份包只在三处不同：通道标记（`X-MisakaNet-Channel`）、版本号、更新说明。

唯一真身在 [`.cindy-plugin/`](https://github.com/Ikalus1988/MisakaNet/tree/main/.cindy-plugin)
（当前版本 1.6.6）；社区那份由 `scripts/build_cindy_plugin_community_variant.py` 从它**生成**
（当前版本 1.5.12）。两个版本号刻意错开，免得互相占掉对方的版本位。

社区变体**不是**另一份 fork：它是官方真身的薄壳。2026-11-11 之前两条通道是**双向分叉**的——
社区那份保留了只读重试与确认卡闸门，却漏掉了官方修掉的 `trust_notice` 标注、await 回包和
`new_lesson_candidate` 分类；官方那份则一直没有那两项能力。2026-11-20 起两项能力都并进唯一真身，
社区那份不再需要 700 行补丁去追赶——`tests/test_cindy_plugin_community_package.py` 的漂移守卫
也从「比对一堆标记」缩成**逐字节比对，三处允许不同**，内容一旦分家就红。

### 1.1.1 两条通道的版本号线（发布时要写一次 KV）

同一个插件 id 有两套版本号线，**刻意错开**：社区投稿通道走 1.5.x，官方随包通道走 1.6.x。
端点要回答「你落后了吗」（`Ikalus1988/MisakaNet#5185`），得同时知道两件事：

1. **调用方在哪条通道上** —— 插件每次请求自报 `X-MisakaNet-Channel: community | official`；
2. **市场上当前是哪个版本** —— 端点从 KV 键 `cindy:plugin:latest` 读。

第 2 件事的**唯一写入方是发布者**：版本发出去之后，跑一次

```bash
python scripts/publish_cindy_plugin_version.py
```

它把 `data/cindy-plugin-versions.json`（两条通道的当前版本）写进 KV，并回读校验。
两条通道用同一份实现，但**版本号线不同**，所以 KV 里是两个数字：端点按调用方自报的通道取对应那个。

> **忘了写不是缺陷。** 端点没有可比对的版本，就对版本保持沉默；插件那头也不说（结果里没有
> `plugin_version`）——静默是设计，不是 bug。代价只是：暂时没人被提醒「你落后了」。

### 1.1.2 三条运维命令

| 命令 | 干什么 | 需要什么 |
|---|---|---|
| `python scripts/release_cindy_plugin.py --variant community` | 发版前把整件事做掉：重建社区包、断言两条通道只差三处、断言版本号一致、用发布者私钥签名、验签，然后打印接下来那三个宿主调用（`ghost_forge_pack` → `ghost_forge_install` → `ghost_contribution_prepare` → `submit`） | 本机的发布者私钥（`~/.cindy/publisher-keys/`） |
| `python scripts/cindy_plugin_market_stats.py` | 市场触达（下载/使用，**无 API，只能在客户端页面上观察后记进 `data/cindy-plugin-market-stats.json`**）+ 遥测侧版本分布（生产 `misakanet-ops` 的 `search_signals`，`agent='cindy'` 那一片） | 遥测部分需要能跑 wrangler（本机在 WSL 上跑） |
| `python scripts/ae_query_with_local_token.py` | 端点侧的分阶段耗时（AE 的 `misakanet_events`：语料读 / BM25 索引 / 打分 / 语义回退各 p95） | 一个带 **Account \| Account Analytics \| Read** 的 Cloudflare API token（放在 `~/.config/misakanet/cf_analytics_token`，**不在仓库里**） |

`release_cindy_plugin.py` 的存在理由是**别再手搓那五步**：手工流程里最容易出的错是
「先签名、后改源码」——签名与包内容对不上，宿主直接拒装。脚本把版本一致性与签名校验放在发布之前，
对不上就不往下走。

### 1.2 发布者签名与公钥（社区投稿通道）

市场投稿通道的包带**发布者签名**：包内 `cindy-signatures.json` 记录这份包的文件清单
（每个文件的 SHA256 与字节数）、发布者 keyId 与公钥，以及对清单的 Ed25519 签名。
Cindy 安装时会按同一口径**复算清单并验签**——清单对不上、或文件在签名后被改过的包直接拒装，
不会静默降级成未签名包。

| 项 | 值 |
|---|---|
| 算法 | Ed25519 |
| keyId | `ed25519:7ea71fcd12e457221aefc33b05ee9da9` |
| 发布者公钥（base64 SPKI DER） | `MCowBQYDK2VwAyEA3wVdEJk80b7jo1QqTEpK+AAlKKmlFapl5zuzRilgJjY=` |
| 机器可读副本 | [`cindy-publisher-key.json`](cindy-publisher-key.json) |

签名证明「文件没被改、还是同一把钥匙」，**不证明发布者的现实身份**。本机的发布者信任表为空，
所以界面显示的是「有签名，发布者身分未验」；官方把这个公钥加入发布者信任表后，才会变成「发布者已验」。

自己核对（签名工具在本仓 [`scripts/sign-plugin-package.mjs`](https://github.com/Ikalus1988/MisakaNet/blob/main/scripts/sign-plugin-package.mjs)，
只用 Node 内置模块（不装任何第三方包），口径与客户端逐字对齐）：

```bash
node scripts/sign-plugin-package.mjs verify --package misakanet-<版本>.cindy
```

私钥只在本机（`~/.cindy/publisher-keys/`），从未进仓库、`.cindy` 包或聊天记录；公钥是公开印章样本。
官方随包通道那份不含本节的发布者签名——它的签名由平台发布流水线写入。

## 2. 工具面

插件只做四件事，全部匿名、只读或经用户确认后上报：

| 工具 | 用途 |
|---|---|
| `misakanet_search` | 按报错原文/关键词检索教训（`detail` 三档，默认最省上下文） |
| `misakanet_get_lesson` | 按 id 或仓库路径取一篇教训全文（`path` 优先；端点会截断到约 5000 字符） |
| `misakanet_preflight` | 高风险操作前的只读预检（`risk_level` + `guards`） |
| `misakanet_me_inbox` | 查一次已提交上报的答复／是否已转成课程 | `intake_id` 或 `dedup_key`（二选一） |
| `misakanet_submit_intake` | 提交 intake / 提问 / 计划（`kind=proposal`，计划类不会被自动判定）；**必须** `user_confirmed=true`，联网目标只有 `misakanet.org` |

联网目标在 `ghost.json` 里显式声明为 `misakanet.org`——市场审核要求，也是给用户的边界：
插件不写任何外部系统、不读你的文件（只用它自己的私有目录存 `client_id` 与提醒计数 `checkpoint.json`）、不需要凭证。

## 3. 验证

**应用内**：让 Cindy 调一次 `misakanet_search`（`query` 用报错原文的片段），返回里应有 lesson 列表与
`source: worker-bm25`；零命中时它会带回端点自己的 `suggestion` 与 `intake` 参数。

**安装器侧**：

```bash
npx @misaka-net/misakanet-setup --only cindy --verify
```

预期：出现一行 `Cindy：插件装没装只在应用内可见，本进程读不到 → …`，并且**退出码是 2**。
退出码 2 在这套 CLI 里表示"没能验证"，与 1（"装了但坏了"）分开——这正是这条集成最该说清楚的一点。

## 4. 卸载

在 Cindy 的插件列表里移除「MisakaNet 故障记忆」即可。安装器对 Cindy **没有写过文件**，所以
`--uninstall` 不需要为它做任何清理（它也不会假装清理）。

## 5. 证据等级

🟡 **recipe**：插件本身已提交到本仓库、市场在审、手册与工具清单可核对；但**本仓库还没有记录过
一次端到端运行**（应用内安装 → 提问 → 工具调用 → 返回教训）。等第一次实际运行后，把命令与输出补进
[status.md](status.md)，等级随之升到 ✅。

## 6. 已知边界

- 安装器**不写任何文件**，所以"重跑安装命令"修不了 Cindy 的任何问题——能修的只有应用内的插件状态；
- `--verify` 的「查不了」**不是错误**，它不会让安装失败，只让退出码变成 2；
- 私有数据目录里存一个每机稳定的 `client_id`（用于端点侧的复用计数）和一个提醒计数 `checkpoint.json`，卸载时随插件数据一起走。

## 7. 插件待办（按优先级）

### P1 — 通道收尾（等人，不急）

- 源仓 [#5375](https://github.com/Ikalus1988/MisakaNet/pull/5375) ✅ 已合并：两条通道并成一份实现、
  社区变体降级成薄壳、漂移守卫改成字节级。
- 源仓 [#5377](https://github.com/Ikalus1988/MisakaNet/pull/5377) ✅ 已合并：三条运维命令（发版一键化、
  市场与遥测读数、AE 包装器）。
- 源仓 [#5637](https://github.com/Ikalus1988/MisakaNet/pull/5637) ✅ 已合并：**确认卡闸门的四处缺陷**
  （维护者 2026-11-23 点的名）——点击用新的在途 callId、超时只落卡不发第二个回执、direct 重提作废旧卡、
  私有目录写不进去时不带假 client id。社区包版本 **1.5.14**（在售 **1.5.13**）。
- 源仓 [#5639](https://github.com/Ikalus1988/MisakaNet/pull/5639) / [#5638](https://github.com/Ikalus1988/MisakaNet/pull/5638)：构建脚本的文件集比较改成「包内文件」规则、发版脚本的 Windows 编码、市场触达读数（1,316 下载 / 415 使用）。
- **1.5.13 / 1.5.14 都已过审并上架**（2026-11-24 02:19:51Z / 03:36:37Z 过审）：市场在售版本已是 **1.5.14**，
  KV 已写 `{"community":"1.5.14","official":""}`（写+回读校验一致）。端点实测：社区通道问 1.5.14 → `outdated:false`，
  问 1.5.13 / 1.5.9 → `outdated:true`；官方通道**沉默**（KV 里 official 留空 = 不发版本信号，这是对的）。
  **市场来源的安装会自动跟上**。1.5.14 的 submission `cmwu4ktbd0354wv01hly337b4`、release
  `c1713e99fa0158c20160f096d`、sha256 `38c1a5fd…`；已装副本与仓库 main 的构建逐字节一致 ✓。
- **1.5.15 已提审**（2026-11-24 07:32:49Z；submission `cmwudnny900uf0101c1d24nh5`、release
  `ccf33c26e2ade64ab49f3fb29`、sha256 `5683028a…`）——过审后再写一次 KV 并补「已上架」。
  它带的是 failure 模式的三处真问题——失败文本的**顺序**
  （整段截到 120 字，原来的顺序会把最有信息量的报错摘要截掉，查询词就查不中）、**每条新失败都再查一次**
  （原来一个会话只查一次）、**「你自己查过」与「插件替你查过」分成两个记号**（老版本塞进同一个标记，
  于是代查过一次之后这个会话里再失败也永远不再查——真机上撞到了）。
  提审快照取自这台机器上重装过的 local 开发副本，与仓库 main 的构建**逐字节一致**（不是 13:12 那次旧包——
  本地装的那份当时落后两个提交，若不重装就会把没带卡片修复的字节提上去）。
- 真机上量到的宿主载荷（**别再按猜测写判定**）：
  `tool_use → {toolUseId, toolName, input}`、`tool_result → {summary, toolUseIds}`——
  `tool_result` **没有 error 字段、没有退出码、没有工具名**，失败与否只在 `summary` 里，
  而工具名与命令行只在 `tool_use` 里 → 必须按 id 配对，否则失败那段文字只剩「exit code 7」这种查不中的碎片。
  源仓 [#5675](https://github.com/Ikalus1988/MisakaNet/pull/5675) ✅ 已合并（配对 + summary 判定 +
  状态文件改成每轮只写一次）。
- **真机上查到的卡片真相**（2026-11-24）：宿主的卡只渲染「挂在正在执行的工具调用上」的卡
  （`card-update` 必须带那个在途调用号，宿主会核对）。所以：
  ①轮末那次「自动沉淀卡」用的是合成 callId → 被宿主以 `unknown-call` 拒掉，**卡片从来没出现过**
  （真机上只剩一句 toast）；现在改成「轮末备草稿 + 下一轮请 agent 调一次真工具」（源仓 #5687 ✅ 已合并）。
  ②经 **MCP 桥**发起的工具调用不是宿主侧 agent 的原生调用 → 卡挂在一个聊天不认识的调用上，也不渲染。
- **卡供不出来时插件停止发送**（维护者 2026-11-24 审核 1.5.15 的意见）：回执 `CARD_UNAVAILABLE` +
  `delivery="not_sent"`，远端没有任何记录；提交必须先取得**用户对具体内容的明确授权**。
  于是流程变成：插件总结并把原文交给 agent → **agent 问用户** → 用户明确同意 → agent 调
  `misakanet_submit_intake`（带 `user_confirmed=true`）→ 插件供确认卡 → 用户点「确认提交」→ 发布。
  插件**不得**替用户预置那个确认标记。
- - 触达老用户的三处文案（源仓 #5674 ✅ 已合并，**已上线**）：插件安装页 `integrations/cindy` §1、
  `quickstart` 的 Cindy 段、社区包更新说明（市场详情页）。文档站在
  `https://ikalus1988.github.io/MisakaNet/`（**不在 misakanet.org 上**——主站没有 cindy 页）。
  提审时踩到的两件事：宿主的**安装确认卡在手机端会被自动拒**（要在桌面端点一下），以及提审快照
  必须取自已安装实例——宿主不允许用本地包覆盖市场版实例，所以要另装一份 local 开发副本。
- 官方通道：**已关闭**（维护者 2026-11-20 明确保留个人发布那条，官方仓里的 `misakanet/` 副本已被
  #371 移除）。`.cindy-plugin/` 现在只是唯一真身，社区变体由它生成。

### P2 — 端点耗时的分阶段定位（**暂缓，上量再提**）

- 目的：把一次检索的耗时拆成**语料读 / BM25 索引 / 打分 / 语义回退**四段（AE 的
  `misakanet_events`；phase 列 2026-11-15 那次部署才有）。
- 现在的判断：**6s 不算难以忍受的用户摩擦**——插件侧平均 3.3s、>6s 占 14%；Claude Code 侧
  45% >6s，但那是另一种调用形状（detail/full、top 更大）。所以这条**在上量之前不追**。
- 上量后再做的成本：一个带 `Account | Account Analytics | Read` 的 Cloudflare token（放仓库外
  `~/.config/misakanet/cf_analytics_token`），或直接在 Cloudflare 控制台跑一条 SQL——
  两种读法 `scripts/ae_query_with_local_token.py` 里都写了。
- 一句话理由：这条服务的是**端点的性能优化**，插件自己的决策不依赖它。

### ~~P2 — 老版本 cohort 的触达~~ → **不做**（2026-11-19 owner 判断：没必要）

- 事实照旧：近 7 天仍有 **25% 的检索跑在 1.2.x / 1.3.x**（那批机器不发新协议，服务端手段够不着；
  市场来源的安装才会跟随更新，自签 `.cindy` 包装的不会）。
- 但**不为他们发版、不改市场文案**：那批机器的代码是冻结的，唯一能触达他们的地方是市场条目与官网
  公告——而**那一次发版的内容本来没有任何行为变化**（社区包 1.5.13 与已上架的 1.5.12 行为一致，
  只是实现归一了）。为一个没有行为变化的版本去改市场文案，成本高于收益。
- 真正在起作用的是**滚动漏斗**：≥1.5.12 的用户由首轮公告与端点的 `plugin_version` 信号告知
  「从市场安装」，于是下一代的 cohort 不再掉队。**漏斗之外的历史欠账，不追。**
