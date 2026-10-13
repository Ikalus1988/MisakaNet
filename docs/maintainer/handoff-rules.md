# Handoff 文件的规则（owner 已定，2026-10-13）

四条规则来自 phase 22 遗留的四个问题。**这是决定，不是提案**。四条全部已定，数值只有一处（800，见下），由门禁从本文件读取。

| # | 问题 | 决定 |
|---|---|---|
| 1 | 按天/阶段拆文件，还是继续单文件追加？ | **拆** |
| 2 | 阶段编号与节号要不要连续？ | **不需要** |
| 3 | 单文件有没有尺寸上限？ | **有：800 行**（2026-10-13 定为 800） |
| 4 | 旧阶段要不要归档？ | **要** |

## 落地前必须先知道的一件事：引用是承重的

`tests/test_handoff_citations_resolve.py` 要求**每一处 handoff 引用都指向真实存在的 handoff**。
实测（2026-10-13）有 **12 个仓库文件**按文件名引用 `handoff-2026-*`，其中**两个是线上工作流**：

```
.github/workflows/approval-watch.yml      CHANGELOG.md        ROADMAP.md
docs/agents/repo-operations.md            docs/maintenance.md
docs/maintainer/setup-health-ci.md        docs/maintainer/state-of-the-repo.md
docs/maintainer/backlog-and-growth-2026-09-20.md
docs/maintainer/capability-inventory-automation-2026-09-18.md
docs/maintainer/dco-experience-issue-1498.md
docs/field-reports/agent-integration-matrix-2026-09-16.md
packages/misakanet-setup/README.md
```

所以规则 1 的正确形状是**向后新增，不是重命名既有的**：既有文件留在原路径（12 处引用继续成立），
新阶段写进新文件。要重命名就必须同步那 12 处 —— 而那正是这道门禁存在的理由，它记录的原案是
`handoff-2026-09-24.md` 从未提交、却有 4 处承重引用指向它。

## 尺寸上限：800 行（已定）

现状：`handoff-2026-10-07.md` **2381 行 / 22 个阶段 / §1–§87**，一个文件装着 10-07 → 10-13 六天。

**上限 `800` 行**（约两天一个文件）：按天平均 ≈ 400 行，而 2381 行已经超过"一次读完"的尺度，
而它正是唯一被反复整体读取的交接件。超限即开新文件 `handoff-<当天日期>.md`。

由 `tests/test_handoff_size_limit.py` 执行：它从这个文件里读数字，所以数值只存在一处。

## 规则 2 的推论（写下来免得下次又问）

编号**不必连续**：每个文件可以从自己的 §1 开始，阶段号也不必与文件序对齐。这一条与
**引用门禁不冲突** —— 门禁校验的是**文件是否存在**，不是节号是否唯一。但**同一文件内**的
`§N` 交叉引用仍须自洽（本文件内 `覆盖 §86.6` 这类写法要指向真实存在的节）。
