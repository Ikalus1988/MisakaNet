# DeepSeekHarness × MisakaNet Integration Guide

> MisakaNet 作为恢复层，为 DeepSeekHarness 提供失败经验记忆能力。

---

## 为什么这样接

DeepSeekHarness 的官方思路是：**同一份 contract，分发成 Python / CLI / MCP / Skill 四种包装。**

MisakaNet 不应该改成另一个 harness，而应该做一个**很薄的兼容适配层**，让 harness 能调用 MisakaNet 的失败经验检索能力。

**核心判断：**
- DeepSeekHarness = 执行层（运行代码、调用工具、管理会话）
- MisakaNet = 恢复层（搜索失败经验、提供修复建议、记录使用反馈）
- 两者是互补关系，不是替代关系

**接法：**
- 不改 MisakaNet 核心 contract
- 不 fork DeepSeekHarness
- 只做 adapter + skill + smoke 三层薄封装

---

## 接了什么

### 1. MCP Adapter（首选集成路径）

**文件：** `scripts/mcp_deepseek_adapter.py`

将 MisakaNet 的 4 个 MCP 工具映射到 DeepSeekHarness 的命名约定：

| DeepSeekHarness 工具 | 委托到 | 功能 |
|---|---|---|
| `deepseek.recovery.search` | `misakanet_search` | 搜索失败经验 |
| `deepseek.recovery.get_lesson` | `misakanet_get_lesson` | 获取 lesson 详情 |
| `deepseek.recovery.submit_feedback` | `misakanet_submit_usage` | 记录使用反馈 |
| `deepseek.recovery.status` | `misakanet_usage_status` + 健康检查 | 查询状态 |
| `deepseek.recovery.doctor` | 新增 | 健康检查 |
| `deepseek.recovery.smoke` | 新增 | 最小验证 |

**配置方式：**

```json
{
  "mcpServers": {
    "misakanet-recovery": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_deepseek_adapter.py"]
    }
  }
}
```

### 2. SKILL.md（次选集成路径）

**文件：** `SKILL.md`（repo root）

告诉模型何时使用 MisakaNet：

- **触发条件：** errors, exceptions, CI failures, tool failures, regressions
- **恢复流程：** search → apply fix → submit feedback
- **工具绑定：** 4 个 MCP 工具 + 使用示例
- **域过滤：** devops, python, rag, mcp, feishu, fanuc

### 3. CLI Smoke（验证闭环）

**文件：** `scripts/misakanet_cli.py`

三个最小验证命令：

| 命令 | 功能 | Exit Code |
|---|---|---|
| `doctor` | 健康检查（数据文件、搜索引擎、lessons 目录） | 0=healthy, 1=degraded |
| `smoke` | 最小搜索链路（search + get_lesson） | 0=pass, 1=fail |
| `validate` | 配置 + 索引 + 工具可用性 | 0=pass, 1=fail |

**用法：**

```bash
python3 scripts/misakanet_cli.py doctor    # 健康检查
python3 scripts/misakanet_cli.py smoke     # 最小验证
python3 scripts/misakanet_cli.py validate  # 完整检查
```

**输出：** JSON（机器可读，harness 可消费）

---

## 怎么验证

### 验证清单

```bash
# 1. 健康检查
python3 scripts/misakanet_cli.py doctor
# 期望: "overall": "healthy"

# 2. 最小搜索
python3 scripts/misakanet_cli.py smoke
# 期望: "overall": "pass", search 返回结果

# 3. 工具可用性
python3 scripts/misakanet_cli.py validate
# 期望: "overall": "pass", 4 MCP + 6 adapter tools

# 4. MCP server 启动
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | python3 scripts/mcp_deepseek_adapter.py
# 期望: 返回 serverInfo with version
```

### 测试结果（当前状态）

| 检查项 | 状态 |
|---|---|
| doctor | ✅ healthy (289 lessons, BM25 engine) |
| smoke | ✅ pass (search: 3 results, get_lesson: 3832 chars) |
| validate | ✅ pass (4 MCP + 6 adapter tools + SKILL.md) |
| MCP adapter initialize | ✅ v1.0.0 |
| MCP adapter tools/list | ✅ 6 tools |

---

## 失败时怎么降级

### 降级策略

| 故障场景 | 降级路径 | 用户感知 |
|---|---|---|
| SAG-Lite FTS 关键字冲突 | 回退到 BM25 搜索 | 搜索结果可能不同，但可用 |
| BM25 不可用 | 回退到 fallback keyword search | 搜索精度下降，但可用 |
| 搜索引擎全部不可用 | 返回 error + 引导 | 用户看到错误提示和修复建议 |
| Lesson 路径不存在 | 返回 error + 搜索建议 | 引导用户用 search 发现正确路径 |
| MCP server 启动失败 | CLI smoke 检测 | doctor/smoke 报告 degraded |

### 降级实现

**搜索降级链：**

```
SAG-Lite (FTS) → BM25 (inverted index) → fallback (keyword match)
```

每一层都有独立的错误处理，上一层失败自动回退到下一层。

**Adapter 错误处理：**

```python
def handle_deepseek_search(args):
    try:
        result = handle_search(args)
    except Exception as e:
        # SAG-Lite FTS 可能失败（SQLite 关键字冲突）
        result = {
            "results": [],
            "source": "error",
            "error": str(e),
            "hint": "Search engine error — try a different query",
        }
    return result
```

**CLI Exit Codes：**

| Code | 含义 | harness 应该怎么做 |
|---|---|---|
| 0 | healthy / pass | 正常使用 |
| 1 | degraded / fail | 降级使用，报告问题 |
| 2 | broken / critical | 停止使用，通知用户 |

---

## 文件清单

```
MisakaNet/
├── SKILL.md                              # 失败记忆技能定义
├── scripts/
│   ├── mcp_server.py                     # 核心 MCP server（4 tools）
│   ├── mcp_deepseek_adapter.py           # DeepSeekHarness adapter（6 tools）
│   └── misakanet_cli.py                  # CLI smoke（doctor/smoke/validate）
└── docs/
    └── integration/
        ├── deepseek-harness.md           # 集成概览
        ├── deepseek-harness-guide.md     # 本文档
        └── skill-md.md                   # SKILL.md 使用说明
```

---

## 设计原则

1. **MisakaNet = 恢复层** — 不是模型对话层
2. **Adapter = 命名层** — 不复制逻辑
3. **Core = 所有逻辑** — adapter 委托到现有 MCP server
4. **可移植** — adapter 可用于任何 harness，不只是 DeepSeekHarness
5. **降级优先** — 每一层都有 fallback，不会完全失败
6. **机器可读** — JSON 输出，exit codes，harness 可消费

---

## 后续演进

| 阶段 | 内容 | 状态 |
|---|---|---|
| v1 | MCP adapter + SKILL.md + CLI smoke | ✅ 完成 |
| v2 | 映射配置化（如果 DeepSeekHarness 合约变化） | 待定 |
| v3 | 更多 harness 支持（Cursor, Continue, etc.） | 待定 |
