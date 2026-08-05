# OpenClaw Error Handler PR — 交付物

**最终方案**: 方案A — redacted-only (4 字段，无 RAW)
**commit**: `fc62dd311a` (pushed to zsxh1990/openclaw)
**PR**: [#93310](https://github.com/openclaw/openclaw/pull/93310)
**状态**: 等待 CI / ClawSweeper re-review

## 文件索引

| 文件 | 说明 |
|------|------|
| `fatal-error-hooks-rawless.ts` | 最终版源码（替换 fork 的 `src/infra/fatal-error-hooks.ts`） |
| `PR_BODY.md` | PR 正文（6-field 格式，evidence 为真实终端输出） |
| `openclaw-fatal-hook-proof.mjs` | Proof 脚本（文件名含 "openclaw"，过 ClawSweeper policy） |
| `README.md` | 本文件 |
