# 项目状态

> 自动更新于 2026-05-29 16:23 UTC | 由 scripts/update_status.py 生成

## 概览

| 指标 | 数值 |
|------|------|
| 📚 Lessons | 185 篇 |
| 📖 References | 6 篇 |
| 🏛️ 领域覆盖 | 18 个 |
| ✅ Git 提交 | 23 次 |
| 📈 近 30 天活跃度 | 23 次提交 |

## 领域分布

| 领域 | 数量 |
|------|------|
| uncategorized        | ████████████████████ +34 54 |
| devops               | ████████████████████ +25 45 |
| rag                  | ████████████████████ +7 27 |
| feishu               | ████████████████████ +5 25 |
| development          | ██████████░░░░░░░░░░ 10 |
| general              | ████░░░░░░░░░░░░░░░░ 4 |
| fanuc                | ████░░░░░░░░░░░░░░░░ 4 |
| network              | ███░░░░░░░░░░░░░░░░░ 3 |

## 节点就绪

| 节点 | 类型 | 状态 |
|------|------|------|
| Hermes (WSL) | Hub + Node | ✅ |
| cc-haha | Node | ✅ |
| OpenClaw | Node | ⏳ 待确认 |

## 活跃功能

| 功能 | 状态 |
|------|------|
| BM25 语义搜索 | ✅ 零依赖 |
| 搜索建议 `--suggest` | ✅ ≥2字符弹出 |
| 内容预览 + 高亮 + 分数条 | ✅ 彩色终端输出 |
| Lessons 共享 (git push) | ✅ |
| GitHub API 一键贡献 | ✅ scripts/contribute.py |
| 交互式安装向导 | ✅ scripts/setup.py |
| 贡献模板 | ✅ scripts/new_lesson.py |
| 质量评分 | ✅ scripts/score_lessons.py |
| 通知通道 (Discord/Slack/Email) | ✅ hub/sync/notifier.py |
| Hub 仲裁 | ✅ |
| Obsidian 集成 | ✅ |

## 快速开始

```bash
# 搜索
python3 search_knowledge.py "关键词"

# 搜索建议
python3 search_knowledge.py "pip" --suggest

# 贡献新 lesson
python3 scripts/new_lesson.py

# 通过 API 一键贡献 (需 GITHUB_TOKEN)
python3 scripts/contribute.py path/to/lesson.md

# 环境检查
python3 scripts/setup.py --check

# 质量评分
python3 scripts/score_lessons.py
```
