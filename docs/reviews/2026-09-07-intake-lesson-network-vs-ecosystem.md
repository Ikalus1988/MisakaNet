# Review: failure→lesson 网络 vs 生态 / PR-Agent / pr-genius（2026-09-07）

> 目的：P0（failure_harvest）实现前的第一性原理竞品评审。
> 结论：**通过（有条件）**——整体不与现有开源方案/PR-Agent/pr-genius 重复；组件层明确"借鉴不重造"；范围裁剪见 §6。

## 1. 需求还原
把"每次失败的修复知识"变成：**可检索、带证据分级、跨项目共享、agent 自己在生产中采集与消费的开放课程网络**。

## 2. 生态对照（引用）
| 方案 | 做什么 | 重叠 | 差异 |
|---|---|---|---|
| Sentry ([grouping/fingerprints](https://docs.sentry.dev/product/issues/grouping-and-fingerprints/)) | 错误指纹/聚类/去重 → 工单给人 | 聚类/指纹语义 | 产出 bug 工单给人；我们产出给 agent 的修复课程 |
| runbook-copilot ([repo](https://github.com/weihong363/runbook-copilot)) | RAG 查已有 runbook | 检索已有知识给建议 | 不累积；不产课程；面向人 |
| HolmesGPT ([CNCF](https://github.com/cncf/sandbox/issues/392)) | AI 排查告警 → 诊断 | 诊断失败 | 单域诊断；无跨项目课程库 |
| Junto / agent-external-memory ([repo](https://github.com/tlemmons/junto-memory), [issue](https://github.com/openclaw/openclaw/issues/75611)) | 多 agent 通用记忆共享 | "共享记忆" | 无质量策展（不去重/验证据/防噪音/分级） |
| 社区失败记忆模板（CLAUDE.md 等） | 单项目私有失败笔记 | 记录失败 | 私有、无共享、无批量转化、命中差（过窄根源） |
| PR-Agent / Qodo ([解析](https://blog.csdn.net/sinat_28461591/article/details/147914402), [AutoFix](https://dev.to/priyanshu123coder/building-autofix-agent-autonomous-cicd-failure-remediation-with-trueforge-qodo-5735)) | 代码审查 + CI 失败自动修复 | 都在 CI 失败处出声 | 单仓库私有改代码；我们跨项目知识不改码 |

## 3. 与 PR-Agent：补集，需划评论位
- PR-Agent：单仓库、审代码、提/实施修复（专家审你）。
- 我们：跨项目、检索"别人已验证"的失败课程（同行经验库），不改码。
- 划界：MisakaNet 评论仅 hit/新颖两类、低频、suggest-only；与 PR-Agent 审查评论信息不同源，可共存。

## 4. 与自家 pr-genius：评审层 vs 知识层（补集 + 协同）
- pr-genius（zsxh1990/pr-genius v1.7.2，PR opened/synchronize）：规则+证据审计 **PR 形态**（issue 链接/规模/pattern），产出审计评论，缩短 review ~50%。
- MisakaNet：**失败知识**（谁踩过/怎么修/是否值得沉淀）。
- 协同：课程转正 PR 本就走 pr-genius + lesson-gate 审；历史 lesson（pr-genius-issue-evaluator-for-intake）表明 pr-genius 可做 intake/候选质量初筛 → 与 harvest 聚类互补（harvest 归堆、pr-genius 挑优）。
- 不重复：pr-genius 无跨项目失败知识面；MisakaNet 不审 PR 形态。

## 5. 区分度
① 面向 agent 语义的失败课程 + 人可读；② 生产闭环（agent 采→机转→机查）；③ 可靠性工程化（噪音/栈感知/去重/证据分级/基准护栏）；④ 跨项目开放 intake + 节点。边界：闭环仍人在环批量审；词表驱动；单维护者节点起步。

## 6. 范围裁剪（实现守则）
- 采集层：只做 intake/CI 事件接入，不自研事件平台（对齐 Sentry fingerprint 语义即可）。
- 检索层：沿用现成 BM25/RRF；增量只在 failure_patterns 签名索引（#1527）。
- 不做：时序事件库/通用 LLM 记忆/代码自动修复（分别留给 Sentry/Junto/Qodo）。
- 评论位：MisakaNet = 低频 suggest-only 知识链接，与 pr-genius/PR-Agent 文案分工。

## 7. 结论
通过（有条件）。P0 最小实现 = `scripts/failure_harvest.py`（失败事件→指纹簇→lesson 骨架草稿，落 `lessons/drafts/`，与 fatal-guard 草稿生命周期一致），组件注明借鉴来源、不做轮子。
