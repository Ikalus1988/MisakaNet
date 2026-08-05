# Intuitive Flow 工作流设置完成

## 已完成的工作

### 1. 优化指导文件

- **AGENTS.md**: 从 274 行精简到 51 行，保留核心规则
- **CLAUDE.md**: 从 274 行精简到 34 行，移除冗长的 lessons 列表

### 2. 创建文档结构

```
docs/
├── agents/                    # 代理操作指南
│   ├── retrieval-and-contribution.md  # 检索与贡献指南
│   ├── knowledge-structure.md         # 知识库结构指南
│   └── node-injection.md              # 节点规则注入指南
├── plans/                     # 功能计划
│   └── example-feature.md            # 示例功能计划
└── human/                     # 人类文档
    └── intuitive-flow-setup.md       # 本文件
```

### 3. 创建状态文件

- **STATUS.md**: 记录项目当前状态、活跃功能、节点就绪情况

### 4. 创建规划目录

- **.planning/**: GSD 执行规划目录

## 文件大小对比

| 文件 | 原始大小 | 优化后大小 | 减少 |
|------|----------|------------|------|
| AGENTS.md | ~274 行 | 51 行 | 81% |
| CLAUDE.md | ~274 行 | 34 行 | 88% |

## 如何使用新工作流

### 检索知识

```bash
# 快速检索所有
python3 search_knowledge.py "你的关键词"

# 只看 lessons（踩坑记录）
python3 search_knowledge.py "关键词" --lessons

# 只看 reference（完整方案）
python3 search_knowledge.py "关键词" --ref
```

### 贡献新知识

```bash
# 踩坑记录（推荐）
python3 scripts/queue_lesson.py \
  -t "你的标题" -d domain \
  --tags "node:你的节点名,project:项目名" \
  "问题描述\n\n## 根因\n...\n\n## 修复\n...\n\n## 验证\n..."
```

### 开发流程

1. **模糊想法** → 使用 `intuitive-flow` 技能
2. **创建计划** → `docs/plans/<feature>.md`
3. **计划评审** → 使用 `autoplan` 技能
4. **执行开发** → 使用 `gsd-execute-phase` 技能
5. **代码清理** → 使用 `simplify` 技能
6. **验证完成** → 使用 `gsd-verify-work` 技能

### 详细指南

- **检索与贡献**: 见 `docs/agents/retrieval-and-contribution.md`
- **知识库结构**: 见 `docs/agents/knowledge-structure.md`
- **节点规则注入**: 见 `docs/agents/node-injection.md`
- **示例功能计划**: 见 `docs/plans/example-feature.md`

## 保持同步

```bash
# 每次会话开始时
cd ~/MisakaNet && git pull --ff-only
```

## 优先技能

| 技能 | 用途 |
|------|------|
| **intuitive-init** | 初始化/刷新项目本地的 AGENTS.md / CLAUDE.md |
| **intuitive-flow** | 从模糊想法到执行的完整开发流程 |
| **intuitive-doc** | 维护面向人类的文档 |
| **intuitive-refactor** | 有界的大规模重构 |
