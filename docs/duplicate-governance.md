# Duplicate Lesson Governance

> 如何处理重复或相似的 lesson

---

## 为什么需要这个文档

MisakaNet 的 lesson 来自真实调试 session，不可避免会出现：
- 同一问题的不同表述
- 相似问题的不同解决方案
- 已有 lesson 的更新版本
- 跨领域的问题重叠

明确的治理规则可以：
- 防止知识库膨胀
- 保持 lesson 质量
- 减少维护者负担
- 为贡献者提供清晰指导

---

## 重复类型

| 类型 | 描述 | 示例 |
|------|------|------|
| **Exact duplicate** | 完全相同的 lesson | 两人同时提交同一 fix |
| **Near-duplicate** | 相同问题，略有不同表述 | "DCO fails" vs "DCO sign-off error" |
| **Superseded** | 新版本替代旧版本 | 旧 fix 有 bug，新 fix 更好 |
| **Overlapping** | 相关但不完全相同 | 同一类问题的不同实例 |
| **Cross-domain** | 不同领域但相似模式 | DCO on Windows vs DCO on Linux |

---

## 处理动作

### 1. Merge（合并）

**适用场景：** 两个 lesson 内容互补，合并后更完整

**操作：**
- 保留更完整的版本
- 从另一个 lesson 提取有价值的补充内容
- 删除被合并的 lesson
- 更新 `data/lessons.json`

**示例：**
```
lesson-a: DCO fix for Windows (详细步骤)
lesson-b: DCO fix for Windows (额外的 troubleshooting)

→ 合并为 lesson-a，添加 lesson-b 的 troubleshooting 部分
```

### 2. Link（链接）

**适用场景：** 两个 lesson 相关但独立，互相引用更有价值

**操作：**
- 在两个 lesson 中添加 "See also" 部分
- 链接到相关 lesson
- 保留两个 lesson

**示例：**
```markdown
## See also
- [DCO Auto-Fix Workflow](../core/dco-auto-fix-workflow.md) - 自动修复工具
- [DCO on Windows](../contrib/error-dco-signoff-windows.md) - Windows 特定问题
```

### 3. Supersede（替代）

**适用场景：** 新 lesson 完全替代旧 lesson

**操作：**
- 在旧 lesson 开头添加重定向说明
- 指向新 lesson
- 保留旧 lesson（避免断链）
- 更新 `data/lessons.json`

**示例：**
```markdown
> ⚠️ **This lesson has been superseded by**
> [New DCO Fix](../contrib/dco-fix-v2.md) - 包含更多场景和自动修复

---

(original content below)
```

### 4. Reject（拒绝）

**适用场景：** 提交的 lesson 与现有 lesson 完全重复

**操作：**
- 关闭 PR
- 评论说明已有 lesson 的位置
- 建议贡献者贡献不同内容

**评论模板：**
```
感谢贡献！但这个 lesson 与现有内容重复：
- [Existing Lesson](link) - 已覆盖相同问题

建议：
1. 查看我们的 [contribution guidelines](CONTRIBUTING.md)
2. 考虑贡献不同领域的 lesson
3. 如果现有 lesson 有遗漏，请在现有 lesson 上补充
```

### 5. Ask Reproduction（要求复现）

**适用场景：** 提交的 lesson 描述模糊，无法确认是否重复

**操作：**
- 要求提供更详细的复现步骤
- 等待补充信息后再决定

**评论模板：**
```
感谢贡献！为了更好地评估这个 lesson：
1. 能否提供更详细的错误信息？
2. 能否提供最小复现步骤？
3. 这个问题在哪些环境下出现？

补充信息后我们会重新评估。
```

---

## 决策流程

```
收到新 lesson PR
        ↓
    检查是否重复
        ↓
   ┌────┴────┐
   │         │
  不重复    重复
   │         │
 正常审核   ├─ exact duplicate → Reject
           ├─ near-duplicate → Merge or Link
           ├─ superseded → Supersede
           ├─ overlapping → Link
           └─ uncertain → Ask Reproduction
```

---

## 维护者检查清单

处理重复 lesson 时：

- [ ] 搜索现有 lessons（`python scripts/search_knowledge.py "关键词"`）
- [ ] 检查 `data/lessons.json` 中的相似标题
- [ ] 评估内容重叠程度
- [ ] 选择合适的处理动作
- [ ] 更新相关 lesson（如果 Merge 或 Link）
- [ ] 更新 `data/lessons.json`（如果删除或添加）
- [ ] 在 PR 中清晰说明处理理由

---

## 参考

- Memoria 的 governance / cooldown 思路
- [Lesson Quality Scoring](lesson-quality-scoring.md)
- [Contribution Guidelines](../CONTRIBUTING.md)

---

*文档创建时间：2026-08-12*
