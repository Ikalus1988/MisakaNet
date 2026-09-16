# MisakaNet 自启动接入

## 👉 不想碰命令行的（推荐给不会技术的人）

**复制这一句，粘贴到 Claude Code / Codex 的对话框里，回车，然后回一句「好」**：

```
帮我接入 MisakaNet 失败记忆库：请读取 https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/INSTALL_FOR_ME.md ，按里面的「第 2 部分：给你的要求」执行，做完用中文简单告诉我结果。
```

助手会自己改配置、自己验证、自己解释。想关掉就说「把 MisakaNet 关掉」。
完整说明（含网络受限时的备用网址）在 **[INSTALL_FOR_ME.md](INSTALL_FOR_ME.md)**。

---

**一行命令安装**（不需要 clone、不需要读文档）：

```powershell
# Windows（PowerShell）
powershell -NoProfile -Command "iwr -useb https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/bootstrap.ps1 | iex"
```
```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main/integrations/agent-autostart/bootstrap.sh | bash
```

装完**只做一件事**：开一个新会话，问一句带报错原文的片段（如「switch vision model」）——
它应该自己调 `misakanet_search`，而不是凭记忆回答。

想知道到底通没通，一条命令：

```bash
python3 ~/.misakanet-agent/install_misakanet_agent.py --verify
# ✓ 端点可达 · ✓ 写入通道 · ✓ MCP 注册 · ✓ 检查点钩子 → 结论：READY
```

装错了/不想要了：`--uninstall`（只删它自己加的东西，改过的文件都有 `.misakanet.bak`）。

| 我想…… | 命令 |
|---|---|
| 先看它会改什么 | `... bootstrap.sh | bash -s -- --dry-run` |
| 只配一个 agent | `--only claude` / `--only codex,hermes` |
| 不要匿名 token（纯只读） | `--no-register` |
| 出问题了给我个 issue 链接 | `--report "错误描述"` |

---


```
integrations/agent-autostart/
├─ install-misakanet-agent.bat     Windows 一键（找 Python → 跑下面的 .py）
├─ install_misakanet_agent.py      安装器本体（三平台通用，纯标准库）
├─ checkpoint_reminder.py          钩子：数轮次 → 第 20 轮注入「该沉淀了」；工具失败 → 注入检索提醒
├─ prompt.md                       行为契约（可整段粘贴，任何 agent 都能用）
└─ README.md                       本文件
```

## 30 秒上手

```bat
:: Windows
integrations\agent-autostart\install-misakanet-agent.bat
```
```bash
# macOS / Linux / WSL
python3 integrations/agent-autostart/install_misakanet_agent.py
```

先看不落盘的预览：`--dry-run`；只配一个：`--only claude`；卸载：`--uninstall`。


## 新用户安装漏斗（产品视角：每多一步就掉一批人）

| 步骤 | 旧状态 | 现在 | 还剩什么 |
|---|---|---|---|
| 发现 → 拿到安装器 | clone 仓库 / 找到文件 | **一行 curl/iwr**（bootstrap）| 需要知道这条命令（README 顶部 / 发布说明）|
| 前置依赖 | 需要 Python | 仍需要 Python 3.9+ | **下一步**：`npx @misaka-net/misakanet-setup`（复用现有 npm 发布通道）|
| 选 agent | 自己判断用哪个 | 自动检测，逐个报告 | — |
| 改配置的恐惧 | 不知道会动什么 | `--dry-run` 预览 + `.bak` 备份 + `--uninstall` | — |
| 写工具要 token | 手动 register + 导出环境变量 | **自动注册匿名节点并写入 token 文件**（0600，不进任何 agent 配置）| — |
| 是否装好了 | 自己猜 | **`--verify` 一条命令给 READY / NOT READY + 每条修复动作** | — |
| 出问题找谁 | 无渠道 | `--report` 生成预填 issue（不含主机名/路径）| — |
| 第一个价值 | 下个会话才知道 | 下个会话问一句带错误码的问题即可 | **MCP 首次信任提示**（客户端会弹一次，脚本无法代点）|


## 它到底装了什么（三件事缺一不可）

| # | 要解决的问题 | 机制 |
|---|---|---|
| 1 | agent **能**调用知识库 | 注册 MCP 服务器 `https://misakanet.org/mcp`（streamable HTTP）；没有 MCP 客户端的 agent 走 skill + `curl` |
| 2 | agent **知道什么时候**该调用 | 把 `prompt.md` 的规则块注入它自己的规则文件（`CLAUDE.md` / `AGENTS.md` / `SOUL.md`） |
| 3 | 检查点**不靠用户触发** | 钩子数轮次：第 20 轮（其后每 10 轮）把「该沉淀了」注入上下文；工具失败时注入检索提醒 |

**为什么必须有第 3 件**：写在规则里的「每 20 轮总结一次」永远不会触发——agent 不记账。只有钩子会。
没有 (1)(2)，钩子没有可调用的东西；没有 (3)，(1)(2) 全靠 agent 自觉。

## 各 agent 的支持度（2026-09-13 核对）

| agent | MCP 注册 | 规则注入 | 检查点触发 | 备注 |
|---|---|---|---|---|
| **Claude Code** | 自动写 `~/.claude.json` 的 `mcpServers` | `~/.claude/CLAUDE.md` 标记块 | **自动**：`UserPromptSubmit` + `PostToolUseFailure` 钩子 | 装完即全自动 |
| **Codex** | 自动写 `~/.codex/config.toml`（`experimental_use_rmcp_client = true` + `[mcp_servers.misakanet]`，顶级键插在第一个 `[table]` 之前） | `~/.codex/AGENTS.md` 标记块 | **手动**：用户级钩子写法未确认 → 靠规则自律，或用外层 wrapper 每轮跑一次 `checkpoint_reminder.py` | 若你的版本报「未知键」，删掉 `misakanet-top:*` 区块即可 |
| **Hermes** | **手动一条命令**：`hermes mcp add misakanet --url https://misakanet.org/mcp`（它自己管 YAML 与首次同意） | `~/.hermes/SOUL.md` 标记块 | **手动**：把 `checkpoint_reminder.py prompt` 加到 `~/.hermes/config.yaml` 的钩子并过 allowlist，再 `hermes hooks doctor` | 见 `hermes hooks --help` |
| **DSH** | 无 MCP 客户端（`dsh` 没有 `mcp` 子命令，已核对）→ 装 skill 到 `~/.agents/skills/misakanet/`，走 `curl` | skill 内 + 项目 `AGENTS.md` | **手动/靠规则** | `prompt.md` §0 有可直接粘的 curl |

> 这张表是**核对结果**，不是愿望。凡是「手动」的都在安装输出里以「需要你手动一步」列出，脚本不假装做过。

## 安全与边界（重要）

- **课程内容是数据，不是指令**：钩子注入的命中摘要来自外部语料，包含其中的命令不要无条件执行。
- **脱敏在上传前完成**：密钥/凭据 → `<REDACTED>`；人名/邮箱/真实域名/绝对家目录 → 泛化（`~/project`、`example.com`）；
  不粘贴会话转录或整段工具输出。规则见 `prompt.md` §3.2。
- **不打断用户任务**：钩子出任何问题都 `exit 0` 且无输出；上传失败只记一句，不阻塞。
- **token 只放环境变量**：`MISAKANET_TOKEN` 用于写入类工具；安装器**不会**把它写进任何配置文件
  （Codex 侧用 `bearer_token_env_var` 引用变量名）。
- **可回滚**：改过的文件都留 `<file>.misakanet.bak`；`--uninstall` 只删自己加的东西（标记块 + 自己注册的条目），
  你原有的 hooks / mcpServers / TOML 键都保留（有测试覆盖）。



### 网络受限时（raw.githubusercontent 被墙/超时）

一行安装默认走 `raw.githubusercontent.com`，但它在不少网络下会**卡住而不是报错**（本仓库开发机上实测：
到 `185.199.108.133` 的 TCP 连接挂死，而 `api.github.com`、`codeload` 秒回）。所以两个 bootstrap 都内置了
**多源回退**，按顺序尝试并打印实际来源：

1. `$MISAKANET_RAW_BASE`（默认 raw.githubusercontent）
2. `https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main`（jsDelivr，实测 1.6s）
3. `https://ghproxy.net/https://raw.githubusercontent.com/...`（实测 1.0s）

现象与对策：

- 输出里出现 `（来源：https://cdn.jsdelivr.net/...）` → 说明主源不通，回退生效了，**不用管**；
- 三个源都试过仍失败 → 手动下载 `install_misakanet_agent.py`、`checkpoint_reminder.py`、`prompt.md`
  到 `~/.misakanet-agent/`，再跑 `python3 ~/.misakanet-agent/install_misakanet_agent.py`；
- 想固定用某个源：`MISAKANET_RAW_BASE=https://cdn.jsdelivr.net/gh/Ikalus1988/MisakaNet@main`；
- 想固定只用主源（离线/内网镜像）：`MISAKANET_RAW_ONLY=1`。

**镜像的代价（实测）**：jsDelivr 缓存 `@main`，最长约 12 小时。本仓库实测过一次：
用 `raw` 源发布的修复，30 分钟后通过 jsDelivr 的 URL 取到的仍是旧文件（下载耗时 91s 且没有新版才有的进度行）。
所以镜像只负责"**能装上**"，不保证"立刻最新"；要立刻拿最新版就固定主源：

```bash
MISAKANET_RAW_BASE=https://raw.githubusercontent.com/Ikalus1988/MisakaNet/main ...
```

失败回退顺序会打印在输出里（`· 文件 ← 主机 … OK/失败`），第一次成功的源会被记住并优先用于后续文件——
主源"能连上但不传数据"时只付一次超时代价（实测：换源后三个文件共 **4s**）。


> jsDelivr 会缓存 `@main`（最长约 12 小时），所以刚发布的修复可能晚一点才通过镜像可见——这是"能装上"与"立刻最新"的取舍。

## Windows 实测记录（两个只有真跑才会暴露的坑）

这两个都是**在 cmd.exe 里实跑发现的**，不是读代码看出来的，所以留在这里省下一次重踩：

1. **`.bat` 里不能写非 ASCII 注释**。cmd.exe 按 OEM 代码页解析 `.bat`，UTF-8 中文注释会被解码错乱，
   碎片被当成命令执行（报一堆 `'…' 不是内部或外部命令`）。所以这个 .bat **刻意全英文**；
   中文输出交给 Python 侧（脚本里已 `chcp 65001` + `sys.stdout.reconfigure(utf-8)`）。
2. **从 WSL/网络路径运行要先 `pushd "%~dp0"`**。`\\wsl.localhost\...` 这类 UNC 路径不能作为 cmd 的当前目录，
   不 pushd 会直接失败；pushd 会自动映射一个盘符（实测映射为 `Z:`）。
3. **Python 在中文 Windows 上默认用 GBK 输出**，打印 `✓` 会抛 `UnicodeEncodeError`——
   最糟的是它发生在**文件已经改完之后**。现在两个脚本都在入口强制 stdout/stderr 走 UTF-8 +
   `errors="replace"`，并有回归测试（`test_installer_survives_a_non_utf8_console`）。

## 验证装好了

```bash
# 1) 钩子本身（不需要 agent）
MISAKANET_HOOK_STATE=/tmp/mn python3 integrations/agent-autostart/checkpoint_reminder.py prompt <<< '{"session_id":"t"}'   # 第 1 次: 静默
for i in $(seq 2 20); do MISAKANET_HOOK_STATE=/tmp/mn python3 integrations/agent-autostart/checkpoint_reminder.py prompt <<< '{"session_id":"t"}'; done  # 第 20 次: 打印检查点

# 2) 失败提醒
python3 integrations/agent-autostart/checkpoint_reminder.py failure <<< '{"error":"exit code 137"}'

# 3) 真会话：新开一个，说「switch vision model」这类片段，看它是否调 misakanet_search
```

可调环境变量：`MISAKANET_CHECKPOINT_AT`（默认 20）· `MISAKANET_CHECKPOINT_EVERY`（默认 10）·
`MISAKANET_HOOK_STATE`（轮次状态目录）· `MISAKANET_HOOK_FETCH=1`（失败时**顺带**拉回命中课程的摘要）·
`MISAKANET_ENDPOINT` · `MISAKANET_TOKEN` · `MISAKANET_HOOK_DEBUG=1`。

## 开发

```bash
pytest tests/test_agent_autostart.py -q      # 14 例：安装 / 幂等 / 卸载 / 钩子行为
python3 integrations/agent-autostart/install_misakanet_agent.py --home /tmp/fakehome --dry-run
```

测试全部跑在临时 HOME 上，**不会**碰你真实的 agent 配置。
