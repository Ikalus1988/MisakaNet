# MisakaNet 自启动接入（让 agent 自己想起这个记忆库）

一句话：装上之后，agent 在**新会话里自动**做三件事——遇到失败先查课程、查不到就提问、到检查点自动脱敏上传——
**不需要用户提醒**。

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

# 3) 真会话：新开一个，说「docker exit code 137 是什么原因」，看它是否调 misakanet_search
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
