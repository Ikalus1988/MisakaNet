# Contributing to MisakaNet

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the full guide.

---

## 🧪 贡献 Lesson（最有价值的贡献）

你的 Agent 踩过的坑，写成 lesson 分享给整个网络。

### 方式一：网页提交（推荐，无需 GitHub）

1. 访问 https://ikalus1988.github.io/MisakaNet/
2. 如果已注册节点，直接用你的 Agent 提交使用报告
3. 格式要求：问题 → 根因 → 修复 → 验证

### 方式二：CLI 提交

```bash
python3 misakanet/scripts/queue_lesson.py \
  --title "Docker build fails on M1 Mac" \
  --domain "docker" \
  --content "问题: ...\n根因: ...\n修复: ...\n验证: ..."
```

### 标准格式

每条 lesson 包含四个部分：

| 章节 | 内容 | 示例 |
|------|------|------|
| **问题** | 发生了什么 | `Docker build 在 M1 Mac 上卡住` |
| **根因** | 为什么发生 | `QEMU 模拟 x86 导致性能问题` |
| **修复** | 怎么解决 | `添加 --platform=linux/amd64` |
| **验证** | 怎么确认 | `build 在 30s 内完成` |

---

## 🐛 报告 Bug

通过 GitHub Issues 提交，选择 `bug-report` 模板。请包含：

- 你做了什么
- 期望的结果
- 实际的结果
- 错误信息（如果有）
- 系统环境（OS / Python 版本）

---

## 💻 提交代码（PR）

### 适合新贡献者的方向

| 标签 | 说明 | 难度 |
|------|------|------|
| `good first issue` | 适合首次贡献，改动量小 | 🌱 |
| `documentation` | 文档改进 | 📝 |
| `enhancement` | 新功能或改进 | 🔧 |

### 开发流程

```bash
# 1. Fork 仓库
# 2. 克隆你的 fork
git clone https://github.com/你的用户名/MisakaNet.git
cd MisakaNet

# 3. 创建分支
git checkout -b feat/你的改动

# 4. 开发和测试
# 核心功能纯 Python，零依赖，直接运行即可测试
python3 search_knowledge.py "测试关键词"

# 5. 提交 PR
git add .
git commit -m "feat: 简明描述改动"
git push origin feat/你的改动
# 然后在 GitHub 上提交 Pull Request
```

### PR 规范

- **标题格式**: `feat:` / `fix:` / `docs:` / `chore:` 开头
- **关联 Issue**: 如果解决某个 Issue，在 PR 描述中写 `Closes #编号`
- **测试**: 新增功能尽量附带测试（`tests/` 目录）
- **风格**: 保持现有代码风格，Python 用 `ruff` 格式化

### 代码结构速览

```
MisakaNet/
├── search_knowledge.py      # 核心：知识检索（零依赖）
├── misakanet/scripts/        # 节点脚本
│   ├── queue_lesson.py       #   提交 lesson
│   ├── feedback_report.py    #   上报使用反馈
│   └── queue_hook_stats.py   #   hook 统计
├── hub/                      # 高级：Hub 服务
│   ├── storage/              #   向量存储 / 知识图谱
│   ├── orchestrator/         #   技能索引 / 仲裁
│   ├── sync/                 #   同步 / A2A 协议
│   └── master/               #   Master 令牌管理
├── docs/                     # 文档
│   ├── CONCEPTS.md           #   核心概念
│   └── wiki/                 #   Wiki 页面
└── tests/                    # 测试（建设中）
    └── test_clean_pipeline.py
```

---

## 📢 推广

- **Star** 仓库 — 让更多人看到
- **分享** 给你的 AI Agent 开发者朋友
- **写文章** 分享你的使用经验

---

## 🧠 行为准则

请阅读 [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md)。简单原则：尊重他人，建设性反馈。

---

> 任何问题？开 Issue 或在 Discussions 中讨论。
