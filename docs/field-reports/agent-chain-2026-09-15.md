# Agent 链路测试报告 — 2026-09-15（claude-haha / hermes / openclaw）

> 目标：在一台**真实 WSL 机器**上，对三个 agent 跑完整链路——安装 → 注册 → 连通 → **真实提问** →
> 是否真的调用 `misakanet_search` → 结果质量——并留下可复现的原始证据。
>
> 环境：`npx` 安装器 **0.4.0**（仓库内版本，含 #1680/#1681/#1682 全部改动），
> 端点 `https://misakanet.org/mcp`（worker 已含 #1697 协议协商修复）。
> 原始日志：`/tmp/chain/*.log`、`*.json`（本机，未入库）。

## 1. 结论

| agent | MCP 注册 | 连通/工具发现 | 真实提问**是否调用** misakanet_search | 判定 |
|---|---|---|---|---|
| **claude-haha**（Claude Code 内核） | ✓ `~/.claude.json` | ✓ `mcp list` → `misakanet: ✓ Connected` | **✓ 调用了**（`mcp__misakanet__misakanet_search`）| **通过** |
| **hermes** | ✓ `config.yaml` + `.env` | ✓ `registered 7 tool(s)` | **✓ 调用了**（`Tool call: mcp_misakanet_misakanet_search`，1.20s / 1908 字符）| **通过** |
| **openclaw** | ✓ `openclaw.json` | ✓ 7 个工具在列 | **修复前 ✗（`tools:["exec"]`）→ 修复后 ✓** | **通过（需 #1717）** |

**本机 `--verify`：READY**（含"端点可达：MCP 握手成功，7 个工具"）。修复前它是 NOT READY —— 见 §3.1。

## 2. 逐链路证据

### 2.1 claude-haha（Claude Code）

```bash
$ claude-haha mcp list
misakanet: https://misakanet.org/mcp (HTTP) - ✓ Connected

$ claude-haha -p "docker exit code 137 是什么原因？" \
      --output-format stream-json --verbose --permission-mode bypassPermissions
# 解析 stream-json 里的 tool_use：
工具调用序列: ['Bash', 'Bash', 'Bash', 'Bash', 'ToolSearch', 'mcp__misakanet__misakanet_search']
```

回答是真正的 exit 137（`128+9` SIGKILL / OOMKilled）排查路径（`docker inspect | grep -i oom`、
`dmesg -T | grep "killed process"`、cgroup 上限、`-XX:MaxRAMPercentage`）。
**注意**：`ToolSearch` 先出现，说明它是先发现工具再调用 —— 这条链路里模型**主动**找了 MisakaNet。

### 2.2 hermes

```bash
$ hermes chat -q "docker exit code 137 是什么原因？" -Q -v
# 关键行（DEBUG 日志）：
mcp.client.streamable_http - DEBUG - SSE message: result={'tools': [{'name': 'misakanet_register'…
tools.mcp_tool - INFO - MCP server 'misakanet' (HTTP): registered 7 tool(s)
root - DEBUG - Tool call: mcp_misakanet_misakanet_search with args: {"query":"docker exit code 137 OOM killed"…}
agent.tool_executor - INFO - tool mcp_misakanet_misakanet_search completed (1.20s, 1908 chars)
root - DEBUG - Tool result (1908 chars): {"result": "{\"results\":[],\"no_match\":true,…
```

**两个要点**：

1. **带 token 的链路不受限流**：同一时刻本机 IP 的匿名配额已用尽（§3.1），而 hermes 走 `.env` 里的
   `MCP_MISAKANET_API_KEY` → 检索正常返回（1.20s）。这正是安装器写入 token 的价值。
2. 规则**真的生效了**：日志里能看到模型自己复述规则——「Let me also recall the misakanet rules:
   "遇到报错… 先调 misakanet_search" — yes, exit 137 is an error pattern.」

### 2.3 openclaw（修复前 → 修复后）

```bash
$ openclaw agent --message "docker exit code 137 是什么原因？" --json
# 修复前：
toolSummary: {"calls": 2, "tools": ["exec"], "failures": 0}      ← 根本没调 misakanet_search
# 修复后（新 session，避免"已回答过"）：
toolSummary: {"calls": 1, "tools": ["misakanet__misakanet_search"], "failures": 0}
projectContextChars: 29522 → 29999                              ← 正好 +477 = 我们的规则块
injectedWorkspaceFiles: [{"name":"AGENTS.md","path":"/mnt/c/Users/Eric Jia/AGENTS.md",…}]
```

修复后它的回答还诚实报告了语料缺口：「MisakaNet 没有针对 `exit code 137` 的专 lesson（搜索命中 3 条
都是相关但不直接的内容）」，然后给出结论。

## 3. 抓到的两个真 bug（均已修，PR #1717）

### 3.1 `--verify` 把"匿名限流"误报成"端点不可达"→ NOT READY

真机输出（curl 同一时刻 200）：

```
! 端点不可达：https://misakanet.org/mcp（网络受限？读课程会静默失败）   结论：NOT READY
```

根因两条叠加：探针用的是 **`misakanet_search`**（每次 `--verify` 消耗 5 次匿名读中的 1 次），
而配额用尽时端点返回 **HTTP 200 + JSON-RPC result 内嵌 error**，判定条件因此判为"不可达"。
**改**：探针改用 `tools/list`（证明会讲 MCP、**不耗配额**、不需凭据），并修掉"结果无 `content` 数组时
解包抛错被吞成 `{}`"的潜在 bug。

### 3.2 OpenClaw 的规则写错目录（工具注册了，模型不知道要用）

`~/.openclaw/workspace/AGENTS.md` 是猜的；agent 实际读 `~/.openclaw/openclaw.json` 里
`agents.defaults.workspace` 指定的目录（本机 `/mnt/c/Users/Eric Jia`）。
**规则文件躺在猜的目录里、`--verify` 还找到了自己的标记 —— 一切看起来都对，模型从未看到规则。**

这说明**"文件写成功"不能当作"规则生效"的证据**：唯一可信的判据是 agent 侧的可观测输出
（`toolSummary` / `projectContextChars` / 系统提示 hash）。

## 4. 未决 / 新发现（建议立案）

1. **首次体验的示例问题正好没有课程**：安装器结尾教用户问「docker exit code 137 是什么原因」，
   而语料里**没有** exit 137 的 lesson（hermes 明确 `no_match: true`；openclaw 只命中 3 条"相关但不直接"）。
   新用户第一次问就会看到"查不到"。**建议**：要么补一篇 exit 137 的课程，要么把示例换成语料里确有命中的
   问题（README 顶部那张表里的 `DCO sign-off failed` / `pip install timeout` 就是现成的）。
2. **Python 安装器（`integrations/agent-autostart/install_misakanet_agent.py`）有同样两个问题**：
   OpenClaw 规则也写 `~/.openclaw/workspace`（同样会写错目录），且 OpenClaw 注册走 CLI、**token 进 argv**。
   JS 侧已修，Python 侧未动（只有 JS 被告警，见 #1681）。
3. **Codex 用户级钩子仍未确证**（installer 自己如实标注"靠规则自律"）；Codex 不在本轮三 agent 之列。

## 5. 复现命令

```bash
# 安装（真机）
npx @misaka-net/misakanet-setup@latest --verify            # 期望 READY + 版本对比

# 三个 agent 的链路（各自一条）
claude-haha mcp list
claude-haha -p "docker exit code 137 是什么原因？" --output-format stream-json --verbose --permission-mode bypassPermissions
hermes mcp test misakanet && hermes chat -q "docker exit code 137 是什么原因？" -Q -v
openclaw agent --message "docker exit code 137 是什么原因？" --json        # 看 toolSummary

# 判据：agent 侧是否真的调用了 misakanet_search（不是"文件写没写成功"）
```
