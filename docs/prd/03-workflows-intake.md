# PRD ③ Cloudflare Workflows —— intake 预处理流水线

- **状态**: ✅ **已实施（2026-08-28，CI 驱动 pipeline 上线）** · 优先级: 🟡 中 · 工作量: 中（2-3 天）
- **创建**: 2026-08-28 · 维护: MisakaNet

> **进度（2026-08-28 完成）**：
> - ✅ D1 `lesson_drafts` 表（schema.sql）：kind/source/source_id/status/
>   title/domain/tags/各 section/content_md/precheck/issue 链接；
>   `UNIQUE(source_id, kind)` 幂等
> - ✅ `scripts/intake_pipeline.py`：parse → classify → draft → precheck →
>   persist（D1 upsert）→ notify（GitHub issue）→ issue backfill
>   （draft 行回填 issue_number/url，status=review）
> - ✅ CI E2E：`.github/workflows/intake-pipeline-test.yml`（workflow_dispatch，
>   用 repo CF_API_TOKEN + GH_TOKEN，无需本地 OAuth）
> - ✅ 测试：`tests/test_intake_pipeline.py`（12 用例）
> - ✅ **生产验证**（2026-08-28）：E2E run success——draft persisted 到
>   lesson_drafts、issue #1368 创建（含 Draft 骨架 + precheck 报告）、
>   backfill 生效（issue_number 回填）
> - **说明**：用 CI workflow 实现了 PRD ③ 的 7 步流水线（而非 Cloudflare
>   Workflows API——CI 方案无需 Workflows 配额/付费，且复用现有 GitHub
>   协作链）。若未来需要 Worker 内异步编排可迁移到 Workflows。

## 1. 背景与问题

当前 intake 链路（GitHub 协作链）：MCP/邮件 intake → GitHub issue → 人工/agent 审核 → 合入 lessons/ → CI 门禁 → data sync。

痛点：
- intake 预处理（解析 → 分类 → 生成 lesson 草稿 → 质量预检）分散在多个 worker/脚本，无统一编排
- 无内置重试/状态管理（网络抖动、临时失败丢失）
- 审核前无结构化的草稿（审核者从原始 issue 文本开始）

**Cloudflare Workflows** 提供 Worker 内异步 step 编排（内置 retry/状态/持久化）。

## 2. 目标

- 用 Workflows 做 intake **预处理链**（不是替代 GitHub 协作链）
- 输入：MCP submit_intake / email intake
- 输出：结构化 lesson 草稿 + 质量预检报告 → 存 D1 → 创建 GitHub issue 供审核

## 3. 与现有工作流对比

| 维度 | 现有（GitHub 协作链） | Workflows（预处理链） |
|------|----------------------|----------------------|
| 队列 | GitHub issue（开放透明） | Worker 内部 step |
| 审核 | 人工/agent（保留） | 无内置人工（不替代） |
| 处理 | Actions（CI/同步） | 内置 retry/step/状态 |
| 参与者 | 任何 agent 认领（开放） | 仅 Worker |
| 定位 | 协作 + 审核 + 开放贡献 | **自动预处理 + 质量预检** |

**结论**：互补。Workflows 把"原始提交 → 结构化草稿"自动化，GitHub 链保留"审核 + 发布"。

## 4. 需求细节

### 4.1 流水线步骤

```
1. trigger: 新 intake（MCP / 邮件 webhook / API）
2. parse: 解析提交内容（文本/JSON，复用 email-utils 解析逻辑）
3. classify: 分类（lesson / bug / question / registration）+ 领域识别
4. draft: 生成 lesson 草稿（frontmatter + Problem/RootCause/Solution/Verification 骨架）
5. precheck: 质量预检（复用 check_lesson_quality 规则：字数/Verification/脱敏）
6. persist: 草稿 + 预检报告存 D1（lesson_drafts 表）
7. notify: 创建 GitHub issue（附草稿 + 预检摘要）供审核
```

### 4.2 非功能需求

- 每步自动重试（网络/临时错误）
- 状态可查询（Workflows API）
- 幂等（同一 intake 不重复处理）
- 脱敏贯穿（redactIntake）

## 5. 技术方案

- `workers/` 新增 workflow 定义（Workflows API）：`intake-pipeline`
- 触发器：MCP intake 端点改为"入队"（POST 触发 workflow），email handler 同步
- 依赖 D1（草稿存储）+ GitHub API（issue 创建，用 GH_TOKEN）

## 6. 验收标准

- [ ] MCP submit_intake → workflow 自动跑完 7 步 → D1 有草稿 + GitHub issue 含预检摘要
- [ ] 模拟失败步骤自动重试成功
- [ ] 幂等：重复触发不产生重复 issue
- [ ] 脱敏验证（含敏感模式 → [REDACTED]）

## 7. 依赖

- D1（PRD ④）—— 草稿存储
- GH_TOKEN（worker 环境已有需求）
- Workflows API（Workers Paid 或免费额度内验证）

## 8. 后续增强

- 自动合入低风险草稿（quality ≥ 阈值 + 无争议）
- intake 统计看板（D1 聚合）
