# zsxh 小号执行计划

> 生成: 2026-06-18 | 全线出击：OpenClaw ✅ → Playwright 🎯 + Vite 🎯

---

## Phase 1: OpenClaw PR 后台监控

- PR #93310: 所有检查绿 ✅ 金虾
- 等 maintainer 点 approve
- 不再主动投入

---

## Phase 2: Playwright — 主攻 🎯

**仓库**: `microsoft/playwright`
**入口**: `packages/playwright-core/src/cli/program.ts`

```
cliProgram().catch(logErrorAndExit)
  → gracefullyProcessExitDoNotHang(1)
```

**收口点**: `logErrorAndExit(e: Error)` 函数 + `.catch()` 链

| 维度 | 值 |
|------|-----|
| 语言 | TypeScript |
| 收口 | `logErrorAndExit` + 多处 `.catch()` 链 |
| 目标改动 | ~15 行注入 `PLAYWRIGHT_ERROR_HANDLER` |
| 难度 | ⭐⭐ |

### 动作清单

```
1. fork microsoft/playwright
2. 找 logErrorAndExit → 在调用前注入 env handler
3. 改 + build + 真 fatal path proof
4. PR body（OpenClaw v6 模板改 Playwright 版）
5. commit + signoff + push
6. @botname re-review
```

---

## Phase 3: Vite — 正式 PR 🎯

**仓库**: `vitejs/vite`
**入口**: `packages/vite/src/node/cli.ts`

```
catch(e) { process.exit(1) }  ← 散布在各命令 action 中
```

**策略**: 环境变量 `VITE_ERROR_HANDLER`，开箱即用，零侵入。

| 维度 | 值 |
|------|-----|
| 收口点 | 多个 `catch` 块中的 `process.exit(1)` |
| 目标改动 | ~15 行 |
| 话术 | "社区对全局错误接管通常关注侵入性和扩展性 — 环境变量方案零侵入" |
| 难度 | ⭐ |

### 动作清单

```
1. fork vitejs/vite
2. 在 catch 块注入 VITE_ERROR_HANDLER
3. build + 真 fatal path proof
4. PR body（OpenClaw v6 模板改 Vite 版）
5. commit + signoff + push
6. 等社区 review
```

---

## Phase 4: E2B — 下一个目标 🎯

**仓库**: `e2b-dev/E2B`
**入口**: `packages/cli/src/index.ts` → `main()`

```
async function main() { await prog.parseAsync() }  // 无 try/catch
main()  // 裸跑，unhandled rejection 不收口
```

**方案**: 包 `main()` + 监听 `unhandledRejection`，注入 `E2B_ERROR_HANDLER`。

| 维度 | 值 |
|------|-----|
| 反 AI 政策 | ✅ 无 |
| 语言 | TypeScript（commander）|
| 收口点 | 1 处 — 包 `main()` |
| 目标改动 | ~15 行 |
| 难度 | ⭐ 极低（比 Vite 还简单）|

### 动作清单

```
1. fork e2b-dev/E2B
2. 包 main() + 加 unhandledRejection handler
3. build + 真 fatal path proof
4. PR body（OpenClaw v6 改 E2B 版）
5. commit + signoff + push
6. 等 review
```

---

## Phase 5: tsdown 跟进

- tsdown PR #1 — 等 ClawSweeper/Codex review

---

## 红线（所有目标通用）

`shell:false` | `env:{PATH}` | `stdio:ignore` | `detached` | `unref` | 4 字段 payload
