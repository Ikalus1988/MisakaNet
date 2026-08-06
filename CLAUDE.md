## 跨节点 Lessons (来自 MisakaNet)

首先用 search_knowledge.py 搜 lessons/ 和 reference/ 看是否有已知修复方案。
未命中时再走 queue_lesson.py 入库。

> 每次有价值的对话结束时，自问"有什么值得跨节点共享？"
> 如果有，运行: `python3 scripts/queue_lesson.py --title "..." --domain "..." --content "问题/修复/验证"`
> 或告诉用户："要把这个经验写成 lesson 吗？"

## 🛡️ 崩溃保护 (fatal-guard)

遇到 Node.js 进程静默崩溃时：

```bash
# 用 fatal-guard 包装任何进程
npx @misaka-net/fatal-guard -- <your-command>

# 崩溃 → 墓碑 JSON → draft lesson
fatal-guard -- node app.js 2>&1 | python3 scripts/tombstone_to_draft.py --stdin
```

> 崩溃事件通过 tombstone 协议自动转为 MisakaNet draft lesson，进入 bench-core 动态题库。
> 参见 README 产品矩阵 → 路线A→C 闭环。

## 核心规则

### 检索优先级

1. **快速检索**: `python3 search_knowledge.py "关键词"`
2. **只看 lessons**: `python3 search_knowledge.py "关键词" --lessons`
3. **只看 reference**: `python3 search_knowledge.py "关键词" --ref`

### 贡献流程

1. 每次有价值对话结束时，自问是否值得共享
2. 如果有，运行 queue_lesson.py 入库
3. 使用正确的 domain 和 tags

## 详细指南

- **检索与贡献**: 见 `docs/agents/retrieval-and-contribution.md`
- **知识库结构**: 见 `docs/agents/knowledge-structure.md`

## 优先技能路由

- **intuitive-init**: 初始化/刷新项目本地的 AGENTS.md / CLAUDE.md
- **intuitive-flow**: 从模糊想法到执行的完整开发流程
- **intuitive-doc**: 维护面向人类的文档
- **intuitive-refactor**: 有界的大规模重构
