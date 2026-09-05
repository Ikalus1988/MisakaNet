# MisakaNet 双轴评审报告（2026-09-03 delta：question 路由 + 答案送达 + TDQS）

**日期**: 2026-09-03
**范围**: 当日改动（#1396 系列）——intake question/lesson 路由（workflow ×4）、kind 检测器（JS/Python 双实现）、D1 questions 持久化 + FAQ 检索、答案同步脚本、TDQS 补 annotations/outputSchema、审计脚本
**评审方法**: 主评审通读全部改动文件 + aider 0.86.2（MiniMax-M2.5）只读审查（10 文件，52k tokens）+ 自主实证复验（worker 109 测试、python 93 测试）
**测试基线**: worker 109（108 passed + 1 pre-existing skip）；pytest 相关集 93 passed（另有 test_http_utils 1 例为环境性失败：sandbox 存在 http_proxy → ProxyHandler 断言失败，与本次改动无关）

---

## 执行摘要

| 维度 | 评分 | 说明 |
|------|------|------|
| **架构（question 语义）** | ⭐⭐⭐⭐ | kind=question 从「被判坏的 lesson」到「一等公民」的收敛清晰：workflow 路由 → MCP 入口自动识别 → D1 持久化 → 拉取/FAQ 双送达 → answered 权威门，链路闭环 |
| **代码正确性** | ⭐⭐⭐⭐ | aider 发现表 12 项经复验仅 1 项为真（dedup trim 不一致，P0，已修）；另自查出 1 项 P1（FAQ 绕过 progressive disclosure，已修） |
| **一致性/去重** | ⭐⭐⭐ | kind 检测 JS/Python 双实现 + FNV-1a 双实现属结构性重复（有 parity 测试但无单一事实源）；audit/triage/sync 三处各写各的 issue 解析（footer 剥离逻辑重复） |
| **安全性** | ⭐⭐⭐⭐ | sync 用只读 GITHUB_TOKEN + CF token；工作流无越权写；question 表仅维护者 answered 可入（无自评） |
| **测试体系** | ⭐⭐⭐⭐ | 新增 12+ worker 用例与 26+ pytest 用例，覆盖路由/拉取/FAQ/parity；仍有缺口：sync 脚本本身无单测（依赖 CI E2E） |

## 轴 1：架构（今日 delta 视角）

- **亮点**：答案送达遵循竞品验证过的 pull 模型（无人推送）；D1 questions 与 lesson_drafts 语义分离正确（question 不铸 lesson 草稿）；权威门槛（answered 标签 + 标记评论提取）与 Sentinela「禁自评」一致。
- **A1（可接受）**：worker(JS) ↔ scripts(py) 双实现镜像（kind 表、FNV-1a、redact 由 `workers/lib/redact-patterns.json` 单源；kind 表与 hash 尚无单源文件——已有 parity 测试，建议后续把 QUESTION/FAILURE_HINTS 抽 JSON 单源）。
- **A2（P2）**：FAQ 合并每次 search 多一次 D1 `SELECT answered`——FAQ 行数小，可接受；量大后加 KV 短缓存。
- **A3（P2）**：sync 为 daily cron + 手动 dispatch；answered→D1 最长 24h 延迟（事件驱动 workflow 已建议未做）。

## 轴 2：代码（aider 发现表复验 + 自查）

| 优先级 | 问题 | 复验结论 |
|---|---|---|
| **P0（已修）** | dedup hash trim 不一致：worker 对 `kind:problem:error` 整体 trim，sync 脚本逐字段 strip——带首尾空白的 problem 在 answered 行回写 hash 后与重提不符 | 真问题。修复：worker `dedupSource` 改逐字段 `String(safeProblem).trim()`/`String(safeError).trim()`（与 sync 的 `.strip()` 对齐）；回归测试：带 padding 的同题重提命中 dedup ✅ |
| **P1（已修）** | FAQ 命中绕过 progressive disclosure：compact/summary 也携带最长 20k 的全文 answer，撑爆 token 预算 | 真问题（自查）。修复：`matchAnsweredQuestions` 接收 detail——仅 `detail='full'` 附全文，compact/summary 截 800 字 + issue_url 提示；测试断言 compact ≤900 / full ≥3000 ✅ |
| P1 | `inferIntakeKind`（worker problem+what_tried）与 `intake_pipeline.classify`（title/problem/error）检测文本不一致 | 部分误读：pipeline 的 question 判定只用显式 kind 字段，检测文本不影响 question 路由；风险低。建议后续统一检测输入（P2） |
| P2 | dedup 检查非原子（两并发同题提交可能双开 issue） | 属实但概率低；KV 无 CAS，接受。sync/人工可发现重复 |
| P2 | sync 脚本 answer 截断 20k 静默 | 可接受（回答极少超 20k）；schema answer 无长度限制为 TEXT |
| P2 | schema 已有 `idx_questions_dedup`（aider 报缺索引为误读） | 已确认存在 ✅ |
| — | aider「无 kind 校验」「KV key 用随机 hash」「redaction 顺序」等项 | 误读（whitelist 校验存在；dedupKey 用 content hash；先 redact 后 hash 为有意设计） |

## 方法论教训（本轮）

- aider `--yes --message "do not edit"` **并不保证只读**：模型仍尝试 apply edit（产物为 17 个以标题命名的垃圾文件，源码未被污染，已清理还原）。aider 无纯审查模式；其**发现表**仍有参考价值，但每条必须人工复验后采信。
- 教训：需要只读审查时不要喂 `--yes`+普通 message；先给明确 `--apply/--no-edit` 不可用则直接不依赖 aider 编辑。

## P0-P1 修复清单（本评审已实施）

1. `workers/register-proxy-sw.js` dedupSource 逐字段 trim（P0，与 sync 哈希对齐）
2. `workers/register-proxy-sw.js` FAQ answer 按 detail 裁剪（P1，progressive disclosure）
3. 回归测试 2 例（padded dedup、FAQ disclosure）→ worker 109 全绿、python 93 全绿
