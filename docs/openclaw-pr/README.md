# OpenClaw Error Handler PR — 交付物

> 对应设计文档: `../pr-openclaw-error-handler.md`

## 决策总结

**最终方案**: 方案A — redacted-only (移除 RAW=1)
**审计链**: Gemini → minimax M3 → C方案 → **方案A**
**状态**: ⏳ 待 amend + force-push + PATCH PR body

### 已修复的关键问题

| 问题 | 修复 |
|------|------|
| `shell: true` 命令注入 | → `shell: false`，只接受可执行文件路径 |
| stdin flush 时序竞争 | → argv[1] 传 JSON，原子传递 |
| 无 schemaVersion | → `schemaVersion: 1` |
| 静默吞错 | → catch 打 `console.error` |
| 伪造的 `--version` 证据 | → proof.js 真实隔离测试输出 |
| RAW=1 未测试 | → 已移除，留后续 PR |

### 文件索引

| 文件 | 说明 |
|------|------|
| `fatal-error-hooks-rawless.ts` | 最终版代码（删除 RAW=1） |
| `PR_BODY.md` | PR 正文（6-field 诚实版，无伪造输出） |
| `INSTRUCTIONS.md` | 操作步骤 + 红线 |
| `INSTRUCTIONS.7z` | 加密版操作步骤 |
| `proof.js` | 隔离测试脚本（spawn 行为验证） |
| `oc-error-forwarder.js` | 崩溃转发器参考实现 |
| `PR_Gemini.md` | Gemini 原版（有 bug，存档参考） |
| `PR_minimax M3.md` | M3 审计报告（发现 7 个问题） |

## 执行路径

```bash
# 1. Clone fork + 切分支
git clone https://github.com/zsxh1990/openclaw.git
cd openclaw
git checkout feat/openclaw-error-handler-env

# 2. 替换源码
cp /path/to/fatal-error-hooks-rawless.ts src/infra/fatal-error-hooks.ts

# 3. 运行 proof
node /path/to/proof.js

# 4. Commit + push
git add src/infra/fatal-error-hooks.ts
git commit -s -m "feat(infra): add structured custom error handler via OPENCLAW_ERROR_HANDLER"
git push origin feat/openclaw-error-handler-env --force

# 5. PATCH PR body
# 用 PR_BODY.md 全文替换 PR #93310 的 body
```

**红线**:
- ❌ 正文不出现 MisakaNet
- ❌ 不等待 handler 退出（`detached: true` + `child.unref()`）
- ❌ handler 失败不抛异常
- ❌ `shell: false` 绝不要改成 `shell: true`
- ❌ 不在 PR body 里伪造 `--version` 输出
- ❌ 不加 RAW/name/message/stack 字段
