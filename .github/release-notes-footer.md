---

## 装上它只要一行（含"不会用命令行"的情况）

**已经在用 Claude Code 或 Codex：**

```bash
npx @misaka-net/misakanet-setup
```

装完**把这个助手窗口关掉再打开一次**，然后随便问一句带报错的（例如「pip install timeout 是什么原因」）——
它应该先去查经验库再回答。想确认状态 `npx @misaka-net/misakanet-setup --verify`，想关掉 `--uninstall`。

**不想碰命令行 / 不知道 assistant 的配置文件在哪：** 把下面这句话**复制粘贴给助手**，它会自己装好、自己验证、用大白话告诉你结果：

```
帮我接入 MisakaNet 失败记忆库：请读取 https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/INSTALL_FOR_ME.md ，按里面的「第 2 部分：给你的要求」执行，做完用中文简单告诉我结果。
```

如果上面这条网址打不开（部分网络会拦 `raw.githubusercontent.com`），换成 CDN 镜像的同一份文件：

```
帮我接入 MisakaNet 失败记忆库：请读取 https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main/integrations/agent-autostart/INSTALL_FOR_ME.md ，按里面的「第 2 部分：给你的要求」执行，做完用中文简单告诉我结果。
```

| 想做的事 | 用什么 |
|---|---|
| 一行装（有 Node） | `npx @misaka-net/misakanet-setup` |
| 让助手自己装（不会命令行） | 上面那段话（raw 或 jsDelivr 两个链接任选其一） |
| WSL / Linux / macOS 脚本 | `curl -fsSL https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/bootstrap.sh \| bash`（被拦就用 `https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main/...`） |
| 只看它要改什么 | 加 `--dry-run` |
| 卸载 | `--uninstall`（改过的文件都有 `.misakanet.bak`） |

> 读不需要注册（匿名 5 次/天/IP）；安装器会顺手注册一个匿名节点并把 token 写进**你本机**的配置，用来解除这个限制。
> 课程内容是数据不是指令——助手被要求不要把课程里的命令当命令执行。
