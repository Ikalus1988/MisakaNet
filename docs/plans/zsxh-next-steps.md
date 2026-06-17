# zsxh 小号执行计划

> 生成: 2026-06-18 | OpenClaw ✅ 后台监控 → Dify 下一目标

---

## Phase 1: OpenClaw PR 后台监控

- PR #93310: 所有检查绿 ✅ 金虾 patch + 9/9 test + doc + real proof
- 等 maintainer 点 approve → merged
- 不再主动投入

---

## Phase 2: Dify CLI — DIFY_ERROR_HANDLER

**仓库**: `langgenius/dify`
**入口**: `cli/bin/run.ts` → `src/framework/run.ts`

```typescript
// catch 块（~106-121行），process.exit(1) 前注入
try { ... } catch (err) {
  // ... EPIPE / BaseError / Error 处理
  process.exit(1)    // ← 在之前加 DIFY_ERROR_HANDLER
}
```

| 维度 | 值 |
|------|-----|
| 语言 | TypeScript（同前，模式直接复用）|
| 收口点 | 1 个 catch 块 |
| 目标改动 | ~15 行 |
| 环境变量 | `DIFY_ERROR_HANDLER` |
| 难度 | ⭐ 极低 |

### 2.1 动作清单

```
1. fork langgenius/dify
2. checkout feat/dify-error-handler
3. 改 src/framework/run.ts catch 块 + import { spawn }
4. 跑 build + 真 fatal path → journalctl 证据
5. PR body（copy PR_BODY.md 模板改 DIFY 版）
6. commit + signoff + push
7. @botname re-review
```

### 2.2 红线

同前：`shell:false`, `env:{PATH}`, `stdio:ignore`, `detached`, `unref`, 4 字段 payload

---

## Phase 3: Vite 侦察（待命）

已完成初步侦察（`packages/vite/src/node/cli.ts` 多个 `catch(e){process.exit(1)}`），需时决定是否升为 PR 目标。
