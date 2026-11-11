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
`manual/misakanet/MANUAL.md`（随包手册）、`assets/icon.png`。市场里发布的就是本仓库这个包（提审期间市场可能仍显示上一版），仓库已到 **1.6.0**（市场评审后同步：三态外发、CSPRNG client id、`detail="full"` 透传正文、提醒计数以内存为准、四个读工具带 `trust_notice`、移除未使用的 `network` 声明）；
审核通过后，仓库这与市场里的包内容一致。

### 1.1 社区通道的变体（`.cindy-plugin-community/`）

市场里的**社区投稿通道**（同一个插件 id `misakanet`，由发布者自己签名）用的是同一份源码加两项
官方通道没有的能力：**只读调用的一次保守重试**，和**上报前的交互卡确认闸门**。它在
[`.cindy-plugin-community/`](https://github.com/Ikalus1988/MisakaNet/tree/main/.cindy-plugin-community)，
当前版本 1.5.5；官方随包通道那份在 [`.cindy-plugin/`](https://github.com/Ikalus1988/MisakaNet/tree/main/.cindy-plugin)，
当前版本 1.6.0。两个版本号刻意错开，免得互相占掉对方的版本位。

社区变体**不是**另一份 fork：它由官方那份重新构建，官方通道修过的每个修复都会带过去。
2026-11-11 之前两条通道是**双向分叉**的——社区那份保留了卡闸门，却漏掉了官方修掉的
`trust_notice` 标注、await 回包和 `new_lesson_candidate` 分类；官方那份则一直没有卡闸门。
现在由 `tests/test_cindy_plugin_community_package.py` 的漂移守卫盯着：官方有的标记，社区变体少一个就红。
两项社区能力本身由 `workers/misakanet-cindy-plugin-community.test.mjs` 的行为用例守住。

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
