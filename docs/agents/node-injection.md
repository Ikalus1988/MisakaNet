# 节点规则注入指南

## 各节点的规则注入方式

| 节点类型 | 方式 | 说明 |
|---------|------|------|
| **Hermes CLI** | CLAUDE.md | 本仓库 `CLAUDE.md` 已包含规则 |
| **cc-haha** | PostToolUseFailure 钩子 | Bash 失败时自动 grep lessons/ |
| **原生 Claude Code** | 项目 CLAUDE.md | 在每个项目根目录放 CLAUDE.md |
| **云 Agent** | 启动 prompt / SOUL.md | 每次会话开始 fetch lessons 并调用 search_knowledge.py |
| **OpenClaw** | CLAUDE.md + cron | 同 Hermes |

## Hermes CLI 配置

Hermes CLI 会自动读取本仓库的 CLAUDE.md 文件，包含以下规则：

1. **检索优先级**: 遇到问题时先搜 lessons/，再搜 reference/
2. **贡献流程**: 有价值对话结束后自问是否值得共享
3. **同步机制**: 每次会话开始时 git pull --ff-only

## cc-haha 配置

cc-haha 使用 PostToolUseFailure 钩子，在 Bash 失败时自动提示 lessons：

```bash
# 钩子会自动执行
python3 search_knowledge.py "错误关键词" --lessons
```

## 原生 Claude Code 配置

在每个项目根目录放置 CLAUDE.md 文件，包含：

1. **检索规则**: 遇到问题时的检索顺序
2. **贡献规则**: 有价值对话结束后共享经验
3. **同步规则**: 每次会话开始时同步知识库

## 云 Agent 配置

每次会话开始时执行：

```bash
cd ~/MisakaNet && git pull --ff-only
python3 search_knowledge.py "当前话题" --lessons
```

## OpenClaw 配置

同 Hermes CLI，使用 CLAUDE.md + cron 定时同步：

```bash
# cron 配置
*/10 * * * * cd ~/MisakaNet && git pull --ff-only
```

## 保持同步

```bash
# 每次会话开始时
cd ~/MisakaNet && git pull --ff-only

# 或设 cron（Hermes/cc-haha 等常驻节点）
*/10 * * * * cd ~/MisakaNet && git pull --ff-only
```
