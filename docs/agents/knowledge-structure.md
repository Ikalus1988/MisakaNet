# 知识库结构指南

## 目录结构

```
MisakaNet/
├── lessons/                  # 跨节点共享知识（踩坑记录）
├── reference/                # 完整方案文档
├── misakanet/                # 通信模块
│   ├── scripts/
│   │   ├── queue_lesson.py       # 写 lesson
│   │   ├── search_knowledge.py   # 检索知识
│   │   └── ...
│   └── schema/
├── storage/
│   ├── knowledge_graph.py   # 知识图谱
│   └── vector_store.py      # 向量存储
└── docs/agents/              # 代理操作指南
    ├── retrieval-and-contribution.md
    ├── knowledge-structure.md
    └── node-injection.md
```

## lessons/ 目录

存放踩坑记录，格式：
- 文件名：`领域-问题描述.md`
- 内容：问题→根因→修复→验证
- 长度：几百字

## reference/ 目录

存放完整方案，格式：
- 文件名：`项目-方案描述.md`
- 内容：需求→规划→代码→上下文
- 长度：几千字

## 检索系统

### search_knowledge.py

```bash
# 检索所有
python3 search_knowledge.py "关键词"

# 只看 lessons
python3 search_knowledge.py "关键词" --lessons

# 只看 reference
python3 search_knowledge.py "关键词" --ref

# 只看标题
python3 search_knowledge.py "关键词" --titles
```

### 索引机制

- lessons/ 和 reference/ 通过 inotify 热加载
- 知识图谱存储在 storage/knowledge_graph.py
- 向量存储在 storage/vector_store.py

## 节点注入规则

| 节点类型 | 方式 | 说明 |
|---------|------|------|
| **Hermes CLI** | CLAUDE.md | 本仓库 `CLAUDE.md` 已包含规则 |
| **cc-haha** | PostToolUseFailure 钩子 | Bash 失败时自动 grep lessons/ |
| **原生 Claude Code** | 项目 CLAUDE.md | 在每个项目根目录放 CLAUDE.md |
| **云 Agent** | 启动 prompt / SOUL.md | 每次会话开始 fetch lessons 并调用 search_knowledge.py |
| **OpenClaw** | CLAUDE.md + cron | 同 Hermes |
