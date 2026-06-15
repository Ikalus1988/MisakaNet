# OpenClaw PR — 提交流程 (方案A: redacted-only)

## 前置准备

```bash
# 1. Fork https://github.com/OpenClaw/OpenClaw (已做: zsxh1990/openclaw)
# 2. Clone + 切分支
git clone https://github.com/zsxh1990/openclaw.git
cd openclaw
git checkout feat/openclaw-error-handler-env  # 分支已存在
# 或:
git checkout -b feat/openclaw-error-handler-env
```

## 代码改动

### `src/infra/fatal-error-hooks.ts`

将文件内容替换为 `docs/openclaw-pr/fatal-error-hooks-rawless.ts`。

改动要点（与当前 654d82a44f 版的 diff）：
- **删除** `OPENCLAW_ERROR_HANDLER_RAW` env var 读取
- **删除** `includeRaw` / `error` / `isError` / payload 扩展块
- **payload 固定 4 字段**: schemaVersion, reason, timestamp, pid
- **JSDoc 简化**: 去掉 RAW 说明

## 编译 + 测试

```bash
# 编译 (需要 ≥12GB RAM，如无法编译可跳过)
# pnpm build  # 当前环境 11GB 可能 OOM

# 测试 — 运行隔离 proof
node docs/openclaw-pr/proof.js
```

把 `proof.js` 的实际终端输出贴进 PR body 的 **Evidence after fix** 段。

## 提交

```bash
git add src/infra/fatal-error-hooks.ts
git commit -s -m "feat(infra): add structured custom error handler via OPENCLAW_ERROR_HANDLER"
git push origin feat/openclaw-error-handler-env --force
```

PR body 用 `docs/openclaw-pr/PR_BODY.md` 完整替换。

---

## 红线 (DO NOT CROSS)

- ❌ 正文不出现 MisakaNet
- ❌ 不等待 handler 退出（`detached: true` + `child.unref()`）
- ❌ handler 失败不抛异常
- ❌ `shell: false` 绝不要改成 `shell: true`
- ❌ 不在 PR body 里伪造 `--version` 输出 —— 用 proof.js 的真实输出
- ❌ 不在代码里加 RAW/name/message/stack 字段（后续 PR 可加）
