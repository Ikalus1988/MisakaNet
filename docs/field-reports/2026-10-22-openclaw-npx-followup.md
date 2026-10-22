# OpenClaw 试用跟进（2026-10-22）——`npx` 装完之后发生了什么

> **来源.** 一个外部试用者在 `npx @misaka-net/misakanet-setup` 之后跑了 `--verify`，
> 逐条核对了 NOT READY 的每一项，并给出了他自己的功能自检。
>
> **版本.** 试用者装的是 npm 上的 `@misaka-net/misakanet-setup@0.5.6`（2026-09-19 发布，
>   当时的 `latest`）。OpenClaw 客户端自身的版本试用者没有记 → **未验证**。
>
> **已脱敏.** 无凭据、无主机名、无个人身份；家目录写作 `<home>`。
> 引用的是试用者的**原话**（译自英文原文）。

## 1. 试用者的判断

> `--verify` 报 NOT READY 的三条"缺装"，全是测量口径问题，不是功能缺失。

| `--verify` 检查项 | 它看到的 | 试用者的实际情况 |
|---|---|---|
| 钩子缺失 | 状态目录无 `hook.mjs` | Claude Code/Codex 机制；OpenClaw 无对应钩子点（README 自己标注 unverified），规则块以 `MEMORY.md` 替代 |
| 规则块没装（AGENTS.md） | `<home>/.openclaw/workspace/AGENTS.md` 无内容 | 该文件被部署锁为 root 只读，写不进；等效规则已在 `MEMORY.md` |
| openclaw.json 未注册 | 配置文件无 `misakanet` 条目 | root 只读 + 网关保护路径双重拦截；改走部署官方 MCP 通道 mcporter，等效完成 |
| 无 token | 自己的状态目录里没有 | token 在 `mcporter.json`（600 权限），此前已用鉴权 `get_lesson` 实测通过 |

## 2. 他自己做的功能自检（这一段比上面那张表更有价值）

> 真正的功能自检（刚跑的，等价于 README 的 claude/codex mcp list）：
> `mcporter list misakanet` → **8 个工具全部列出，和 README 声称的数量一致**：
> register / search / get_lesson / submit_intake / write_lesson / preflight / me_events / me_inbox。
>
> 按 README 的测试方法拿 switch vision model 实测 → 命中《多模型Switch脚本模式》
> 《ccswitch-hermes-switch 踩坑Notes》两条课程，先查后答的链路成立。

**"8 个工具，与 README 声称的一致"——这句话是本报告里最有用的一句**：
它把"文档声称"和"我这台机器上真的有"对上了，而且用的是**逐客户端的自检命令**。
仓库里有一道门禁守着工具数与文档一致（`tests/test_mcp_tool_surface_matches_docs.py`），
但那道门禁守的是"文档别写错"，**不是"用户怎么验"**。

## 3. 他对 README 的更正

> "关掉助手窗口再打开"这步不需要——那是给配置文件路由（claude/codex 启动时加载）准备的；
> mcporter 是按次调用，即时生效，前面 search/get_lesson 的实测就是重启后状态。

## 4. 核对结论：哪几句对，哪一句要改

| 试用者的判断 | 核对结果 |
|---|---|
| "三条'缺装'全是测量口径问题" | **对，但更准确的说法是：安装器和校验器对同一台机器给了相反的诊断。** 安装器已经会报"这些文件改不了（只读或权限不足）"并跳过该助手（`unwritableTargets()`，bin/misakanet-setup.mjs:2357-2364），而 `--verify` 不知道那个文件是写不进去的，于是说"没装 → 重跑安装命令"——**恰好是唯一无效的那条建议**。见 [#3696](https://github.com/Ikalus1988/MisakaNet/issues/3696) |
| "钩子缺失"的归因 | **归因对不上，结论对。** 钩子检查在 `if (detect('claude'))` 里（`:1616`），而 `detect()` 的判据只有"`~/.claude` 或 `~/.claude.json` 在不在"（`:986-996`）。一台实际用 OpenClaw 的机器收到这条，说明机器上有残留的 `~/.claude`——**"这台机器在用 Claude Code"并不成立**。见 [#3699](https://github.com/Ikalus1988/MisakaNet/issues/3699) |
| "无 token" 算作缺装 | **它其实不翻转判定**——那一行是 `skip(...)`（`:1608`），只是信息不完整：token 检查只看安装器自己的状态目录，用户从别的通道拿到的 token 它看不见。见 #3696 |
| "关掉再打开"不需要 | **对。** 安装输出第 1 步（`:2403`）和 README 首屏（README:12）把这句话对所有客户端说了一遍，而仓库自己在 dsh 一节就写着"with no restart"。见 [#3700](https://github.com/Ikalus1988/MisakaNet/issues/3700) |

## 5. 这一轮最值得记住的一句

**不是"OpenClaw 装不上"，而是：`--verify` 只会量"我们自己的脚印"。**

它量的是"我们偏好的那几个文件有没有写成"，不是"你能不能用上"——
而这台机器上，前者恰恰是写不成的那几个。于是一件**能用**的事，被判成了不能用，
还附赠一条**重跑也修不好**的建议。
试用者最后是自己绕过去的：换通道、自己列工具、自己拿报错原文验链路。

**安装器的下一步应该允许用户自己走这一步**：给他命令，给他期望输出，别让他猜。
