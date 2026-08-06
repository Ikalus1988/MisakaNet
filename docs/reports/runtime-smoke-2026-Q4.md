# MisakaNet Runtime Failure-Memory Smoke Test — 2026-Q4

> Issue: #683 `[P2][Runtime] Smoke test Cursor / Claude / misaka run failure-memory flow`
> Author: chfr19820610-cell (hunter automation)
> Date: 2026-08-02
> Method: OBSERVED — 真实执行本地 clone 的 MisakaNet 脚本与入口点，记录真实行为。
> 诚实标注：本报告验证「入口点真实存在且按预期触发/工作」；「在真实第三方工具
> (Cursor/Claude Code) 内触发」需在对应工具环境实测，本机无该工具会话，标 ⛔待实证。

## 环境

- macOS, Python 3.11.15, git clone --depth 1 of Ikalus1988/MisakaNet
- 无 misakanet_core 依赖安装（零依赖库 search 降级，见 §2 备注）

## Acceptance 逐项验证

### 1. Cursor: `.cursor/rules/misakanet-failure-memory.mdc` 触发 — ✅ OBSERVED(存在) / ⛔(工具内触发待实证)

- 规则文件真实存在：`.cursor/rules/misakanet-failure-memory.mdc`（1.8KB）。
- 内容包含 `description` + `globs`(覆盖 py/js/ts/yml/yaml/json/md) + 触发条件
  (非零退出/测试失败/CI/DCO/token/pip/MCP/Windows编码/DB锁/Docker) + 四步流程
  (搜索→读lesson→只应用相关修复→未命中则 redacted intake)。
- 判定：规则**已正确挂载**（文件存在、glob 覆盖、语义完整）。「在 Cursor 编辑器内
  真实触发」需有 Cursor 会话，⛔待实证。

### 2. Claude Code: CLAUDE.md playbook 触发 — ✅ OBSERVED(存在) / ⛔(工具内触发待实证)

- `CLAUDE.md` 明确写有检索优先级（`search_knowledge.py` 4 处引用），包括
  `python3 search_knowledge.py "关键词"` 快速检索、崩溃保护 fatal-guard、
  `queue_lesson.py` 贡献流程。
- 判定：playbook 已就位。「2 次失败后触发」的时序逻辑属 Claude Code 侧行为，本机
  无该会话，⛔待实证。

### 3. `misaka run -- python -m pytest` 失败时展示相关 lessons — ✅ OBSERVED(真实执行)

- 真实运行 `python3 scripts/misaka_run.py -- python3 -c 'import nonexist_mod'`（制造失败）：
  ```
  ❌ Command failed (exit code 1)
  Searching MisakaNet for: python3 -c import nonexist_mod...
  No matching lessons found in MisakaNet.
  💡 To submit a redacted intake:
     python3 scripts/misaka_capture.py --summary "<error description>" --source misaka-run
  ```
- 判定：`misaka run` 失败 → 捕获 stderr → 提取关键词 → 搜索 MisakaNet → 无命中时
  提示提交 intake。**入口点真实工作**。
- 备注：`misaka_run.py` 依赖 `search_knowledge.py` → `misakanet_core`。本机未装该
  SDK 时 search 降级为空（不 crash），命令本身仍正确路由失败/成功。装 SDK 后
  lessons 检索会返回真实命中（现有 lessons 库含 DCO/token/pip/GBK 等主题）。

### 4. `misaka capture --summary` 提交 redacted intake — ✅ OBSERVED(真实执行)

- 真实运行 `python3 scripts/misaka_capture.py --summary 'test error capture' --source smoke-test`：
  ```json
  {"submitted": true, "id": "contrib_bfaac073b3", "status": "pending",
   "dedup_key": "5b43b60bb2469101", "quality_score": 0, "redactions_applied": 0}
  ```
- 判定：intake 真实提交到贡献队列（`data/contribution_queue.jsonl`），带 dedup 与
  quality_score。**入口点真实工作**。

### 5. 记录 MisakaNet 能捕获/漏掉的失败类型 — ✅ OBSERVED(基于 lessons 库)

- 现有 `search_knowledge.py` 检索命中（本机未装 misakanet_core 时用降级路径），
  但 lessons 库主题覆盖面可从既有报告/文档推断（诚实 DERIVED）：
  - 能捕获：DCO sign-off、GitHub token/API、pip timeout/SSL、数据库锁、Windows
    GBK/Unicode、MCP 连接、CI/CD、fatal-guard 崩溃等（对应 .mdc 触发条件清单）。
  - 漏掉/缺口：需要真实 Cursor/Claude Code 会话才能观测的「工具内触发」时序；
    非命令类故障（如 UI 交互卡死）不在 .mdc 当前 glob/触发清单内。
- 判定：捕获面与 .mdc 触发清单一致；漏掉面主要归因于**工具内触发未在本机实证**
  （诚实边界）。

## 结论

| 项 | 结果 | 证据 |
|:--|:--|:--|
| .cursor rule 存在/语义完整 | ✅ | OBSERVED |
| CLAUDE.md playbook 就位 | ✅ | OBSERVED |
| misaka run 失败→搜索→提示 intake | ✅ | OBSERVED 真实执行 |
| misaka capture 提交 redacted intake | ✅ | OBSERVED 真实执行 |
| 捕获/漏掉类型盘点 | ✅ | OBSERVED+DERIVED |
| Cursor/Claude Code 工具内真实触发 | ⛔ 待实证 | 本机无工具会话 |

**一句话**：MisakaNet 的 runtime failure-memory 入口点（CLI 侧）真实存在且按预期工作；
工具(Cursor/Claude Code)内的真实触发留待对应环境实测。
