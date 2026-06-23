---
{"title": "Phase 0 Output Gate — Agent 的硬性知识检索规则", "domain": "methodology", "tags": ["output-gate", "knowledge-reuse", "methodology", "core"], "domain_expert": "unknown"}
---

## Background

Agent 在 context 中看到了知识但不一定会用。即使指令写了"不可跳过"，Agent 的惯性行为是直接执行任务、跳过检索。

## 根因

"搜 lessons/" "搜 reference/" 等指令是Recommended，Agent 可以跳过而不产生任何可见后果。

## Fix

把知识检索从"Recommended"改为**硬性 Output gate**：

1. 列出可用知识并输出File名
2. 用搜索工具检索Related条目，读取匹配内容
3. 输出检索结论（可复用内容、核心风险）
4. **未输出 = 不准进入下一步**

## 验证

在专利交底书Modify任务中部署曳光弹。首次Use即发现 Phase 0 检索到 reference File，发现了 3 个之前Modify遗漏的Problem，其中 2 个是 P0 硬伤。

## 原理

Agent 可以忽略上下文的Recommended，但**不能凭空编出完整的检索报告**。用户能看到输出结果——如果没读File，摘要就是空的。

## 限制

- 依赖 Agent 加载规则后遵守 Output gate（但规则本身设计了可见的输出约束）
- 没有Automatic化验证（未来方向：post-task hook 检测是否引用了知识内容）
