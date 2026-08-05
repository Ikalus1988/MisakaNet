# OpenClaw Error Handler PR — 完整方案

> 最终更新：2026-06-16 | 决策：方案A (redacted-only)

## 最终设计 (方案A)

```typescript
function runExternalErrorHandler(context: FatalErrorHookContext): void {
  const handler = process.env.OPENCLAW_ERROR_HANDLER?.trim();
  if (!handler) return;
  try {
    const payload: Record<string, unknown> = {
      schemaVersion: 1,
      reason: context.reason,
      timestamp: new Date().toISOString(),
      pid: process.pid,
    };
    const child = spawn(handler, [JSON.stringify(payload)], {
      stdio: ["ignore", "inherit", "inherit"],
      detached: true,
      shell: false,
    });
    child.on("error", () => { });
    child.unref();
  } catch (err) {
    console.error("[fatal-error-hooks] OPENCLAW_ERROR_HANDLER failed:", String(err));
  }
}
```

## 决策历史

| 版本 | 决策 | 日期 |
|------|------|------|
| Gemini 原版 | `shell: true` + stdin pipe + RAW 字段 | 2026-06-14 |
| minimax M3 审计 | 发现 7 问题（2 阻塞：shell 注入 + flush race） | 2026-06-15 |
| C方案 (redact-by-default) | `shell: false` + argv[1] + RAW opt-in | 2026-06-15 |
| **方案A (redacted-only)** | 移除 RAW=1，payload 固定 4 字段 | **2026-06-16** |

## 为什么放弃 RAW=1

1. **argv 安全** — 4 field payload（schemaVersion/reason/timestamp/pid）不含任何敏感信息，走 argv 完全安全
2. **可测试性** — OpenClaw build 需要 ≥12GB RAM（当前环境 11GB），RAW 路径无法在真实运行时验证
3. **简洁性** — 删除 ~15 行 includeRaw gate + 条件分支
4. **可扩展性** — 后续若有社区需求，可以 follow-up PR 加回 RAW opt-in

## 修复的坑

| 问题 | Gemini 原版 | 修复 |
|------|-------------|------|
| `shell: true` 命令注入 | 攻击者可执行任意命令 | `shell: false`，只接受可执行文件路径 |
| stdin flush 时序竞争 | `process.exit` 在 handler 读完前关闭 pipe | argv[1] 传 JSON，原子传递 |
| 无 schemaVersion | 未来加字段破坏 handler | `schemaVersion: 1` |
| 静默吞错 | `catch {}` | `console.error` |
| 虚假证明 | PR body 写伪造的 `--version` 输出 | proof.js 真实隔离测试输出 |
| RAW=1 未测试 | RAW 路径无法在 11GB 环境编译验证 | 已移除 |

## 交付物

| 文件 | 说明 |
|------|------|
| `fatal-error-hooks-rawless.ts` | 最终版代码（方案A） |
| `PR_BODY.md` | PR 正文（6-field 诚实版） |
| `INSTRUCTIONS.md` | 操作步骤 + 红线 |
| `proof.js` | 隔离测试脚本 |
| `oc-error-forwarder.js` | 崩溃转发器参考实现 |
