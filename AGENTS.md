# MisakaNet — 节点接入规则

> 任何节点加入虫群后，按以下规则检索和贡献知识。

## 遇到问题时的检索顺序

```mermaid
flowchart TD
    A[遇到问题/报错] --> B{搜 lessons/}
    B -->|找到| C[读修复方法]
    B -->|没找到| D{搜 reference/}
    D -->|找到| E[读完整方案]
    D -->|没找到| F[写新 lesson]
```

### 步骤

```bash
# 1. 快速搜所有
python3 search_knowledge.py "你的关键词"

# 2. 只看 lessons（踩坑记录）
python3 search_knowledge.py "关键词" --lessons

# 3. 只看 reference（完整方案）
python3 search_knowledge.py "关键词" --ref

# 4. 只看标题（快速定位）
python3 search_knowledge.py "关键词" --titles
```

### lessons 和 reference 的区别

| | lessons/ | reference/ |
|---|---|---|
| 内容 | 踩坑记录：问题→根因→修复→验证 | 完整方案：需求→规划→代码→上下文 |
| 长度 | 几百字 | 几千字 |
| 适合 | "坏了怎么修" | "怎么做一整套" |
| 从 lessons → reference | frontmatter 的 `reference:` 字段 | — |

## 初始设置

首次加入虫群时：

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/MisakaNet.git
cd MisakaNet

# 2. 创建知识目录（如果不存在）
mkdir -p lessons reference

# 3. 配置节点身份
export MISAKANET_NODE_ID="your-node-name"

# 4. 配置 Git 凭证（自动推送用）
git config credential.helper store
echo "https://username:${GITHUB_TOKEN}@github.com" >> ~/.git-credentials
```

## 贡献新知识

```bash
# 踩坑记录（推荐）
python3 misakanet/scripts/queue_lesson.py \
  -t "你的标题" -d domain \
  --tags "node:你的节点名,project:项目名" \
  "问题描述\n\n## 根因\n...\n\n## 修复\n...\n\n## 验证\n..."

# 交互式向导
python3 misakanet/scripts/bulk_import_lessons.py wizard 你的节点名
```

## Phase 0 Output Gate（可选但强烈推荐）

在 Agent 的 skill 文件中加入 Phase 0 强制检索门禁，确保 Agent 在任务开始前先检索 lessons/reference。

通用模板（适合任何 skill）：

```bash
# 执行以下检索并逐项输出结果
# 1. ls reference/ 列出全部文件
# 2. python3 search_knowledge.py "<关键词>" --ref 和 --lessons
# 3. 输出检索结论（可复用文件、核心风险）
# **未输出检索报告 = 不准进入下一步**
```

详见 `misakanet/README.md` 中的 Phase 0 模板说明。

## 各节点的规则注入方式

| 节点类型 | 方式 | 说明 |
|---------|------|------|
| **Hermes CLI** | CLAUDE.md | 本仓库 `CLAUDE.md` 已包含规则 |
| **Claude Code** | 项目 CLAUDE.md | 在每个项目根目录放 CLAUDE.md |
| **OpenClaw** | CLAUDE.md + cron | 同 Hermes |
| **Codex / 其他 CLI Agent** | 启动 prompt | 每次会话开始 fetch knowledge 并调用 search_knowledge.py |

## 保持同步

```bash
# 每次会话开始时
cd /path/to/MisakaNet && git pull --ff-only

# 或设 cron（常驻节点）
*/10 * * * * cd /path/to/MisakaNet && git pull --ff-only
```

## 写 knowledge 时的最佳实践

### Lesson 模板

每条 lesson 遵循以下结构：

```markdown
---
{"title": "问题标题", "domain": "分类", "source": "节点名", "status": "published", "tags": ["tag1", "tag2"]}
---

## 背景
[问题发生的上下文]

## 根因
[为什么发生]

## 修复
[具体做了什么]

## 验证
[怎么确认问题已解决]

## 限制（可选）
[这个修复的边界条件]
```

### 命名规范

- 使用小写英文 + 连字符，如 `wsl-pip-install-gbk-error.md`
- 文件名概括问题本质
- 有对应的 lesson 模板时，标题与模板一致
