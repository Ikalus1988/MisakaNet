# Lesson Quality Checklist

> 每个新的或修改的 lesson 在提交 PR 前，按此清单逐项检查。
> 合并门禁：**所有 Must 项通过** + **至少 4 个 Should 项通过**。

## Must（必须满足）

### 结构与内容

- [ ] **标题**：英文，kebab-case 文件名，4-120 字符，准确描述问题
- [ ] **Frontmatter**：JSON 格式，包含 `title`、`domain`、`tags`、`status`、`confidence`、`created`、`source`
- [ ] **Problem 段落**：明确描述症状和场景，不模糊
- [ ] **Root Cause 段落**：给出技术根因，不跳过
- [ ] **Solution 段落**：步骤化，带命令/配置/代码
- [ ] **Verification 段落**：有可执行的验证步骤（命令、测试、预期输出）

### 格式规范

- [ ] **代码块**：标注语言（` ```python `、` ```bash `、` ```yaml `）
- [ ] **路径**：用 `<placeholder>` 而非硬编码绝对路径
- [ ] **文件编码**：UTF-8，无 BOM
- [ ] **行尾**：LF（Unix），非 CRLF

### 正确性

- [ ] **命令可复现**：所有命令行参数、配置项在标准环境下可运行
- [ ] **引用存在**：引用的文件、URL、issue、PR 均可访问
- [ ] **无敏感信息**：无 API key、token、密码、内网 IP

## Should（建议满足）

- [ ] **Tags 完整**：3-10 个 tag，每个 >= 2 字符，小写
- [ ] **Domain 明确**：属于 `rag` / `devops` / `fanuc` / `network` / `feishu` / `tts` / `mcp` / `agent-network` / `marketing` / `audio` 之一
- [ ] **Notes 段落**：包含边界条件、注意事项、相关 lessons 引用
- [ ] **related lessons**：引用其他 lesson 时用相对路径
- [ ] **适用环境说明**：若与环境相关，标注 `platform:wsl` / `platform:linux` / `platform:docker` 等
- [ ] **来源标注**：`source` 字段填写贡献者标识而非泛称
- [ ] **无超长行**：每行 <= 120 字符（代码块除外）
- [ ] **英文用语**：术语统一（如 "root cause" 不混用 "reason"）

## Quality Score 参考

当 Quality Score 算法上线后，CI 会自动评分。当前人工预检可参考：

| 维度 | 权重 | 说明 |
|------|------|------|
| `root_cause_clarity` | 0.5 | 根因是否明确、有技术细节 |
| `verify_completeness` | 0.3 | 验证步骤是否可独立重复 |
| `domain_coverage` | 0.2 | 是否涵盖多环境/多版本 |
| **Score** | = 0.5×clarity + 0.3×completeness + 0.2×coverage |

Score < 0.6 → 需标记 `needs-review`，不应合并。

## 提交前自检流程

```text
1. 从 TEMPLATE.md 复制模板
2. 填写全部 Must 字段
3. 运行 python3 -c "import json; json.load(open('your-lesson.md'))" 校验 frontmatter
4. 在本地跑一次 search_knowledge.py 确认能被检索到
5. 对照上表逐项打勾
6. 提交 PR
```

## Review 标准（维护者用）

| 等级 | 条件 | 动作 |
|------|------|------|
| ✅ approve | Must 全过 + Should >= 5 | 可直接合并 |
| 👀 needs-fix | 1-2 个 Must 未过 | 要求修改后重新 review |
| ❌ reject | >= 3 个 Must 未过，或包含敏感信息 | 关闭 PR 并说明原因 |
