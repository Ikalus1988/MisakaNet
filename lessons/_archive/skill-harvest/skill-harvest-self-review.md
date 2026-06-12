---
{"title": "Self Review", "domain": "general", "source": "skill-pipeline", "status": "draft", "tags": [], "created": "2026-05-09", "updated": "2026-05-09"}
---


## 背景

（此 lesson 从 skill `self-review` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Self-Review Skill

## 触发条件
- 每日定时：每天 00:05 和 09:05 各跑一次（紧跟早晚问候 cronjob）
- 手动触发：任务出错、踩坑、或你觉得需要复盘时说"复盘一下"
- Error 触发：任务执行中遇到非预期失败，主动写一条 review

## 流程

### Phase 1: Session Scan
用 `session_search` 扫描最近 1-3 天的 session：
```
session_search(limit=5)  # 获取最近 5 个 session
```

对每个 session 检查：
- 任务完成情况（preview + message_count）
- 有无错误/失败迹象
- 有无新的环境信息（工具路径、凭证、OS 变化）

### Phase 1.5: Skill/Lesson 结构健康检查（每周一次，或手动触发时必做）

扫描 `~/.hermes/skills/` 下所有 SKILL.md 和 `lessons/` 下所有 .md 文件，检查：

**Skills 检查清单：**
- description 字段是否为空或被垃圾内容污染（如 Hermes startup banner）
- 是否有完全空文件（SKILL.md 无内容）
- 是否只有 DESCRIPTION.md 无 SKILL.md（orphan plugin dirs）
- triggers 是否仍有效

**Lessons 检查清单：**
- 所有 .md 文件是否都被 index.md 收录
- index.md 的"最后更新"日期是否合理
- lesson 内容是否仍相关（可安全删除/归档旧的）

**输出格式：**
```
[技能健康] 检查 44 skills + 10 lessons →
  P0: 2 skills (description corrupted by banner)
  P1: 1 empty skill + 6 orphan dirs
  P2: 1 stale lessons index
```
发现 P0 问题直接修复，P1-P2 报告给用户。

### Phase 2: 提取"值得记住"的内容
归类进以下 4 个维度：

1. **环境变更** — 新的工具路径、凭证、OS 变化
2. **犯过的错** — 导致失败的操作、错误的假设
3. **解决过的坑** — 调试成功的方案，日后可复用
4. **待完成事项** — 任务没做完但有上下文残留的

### Phase 3: 更新记忆
用 `memory` 工具按需写入：
- `memory(target="memory")` — 环境事实、坑的解决方案
- `memory(target="user")` — 用户偏好变化、新的任务模式
- `skill_manage(action='patch')` — 更新已过期/有坑的 skill

### Phase 4: 输出一句话摘要
输出格式（一句话）：
```
[复盘] 过去24h：做了X件事，Y个坑（已解决/待处理），Z个记忆更新
```

## 错误触发专项
遇到非预期失败时（工具报错、超时、逻辑 bug），在当前 session 内立即：
1. 把错误现象和根因写入 memory
2. 如果是 skill 有坑，更新 skill
3. 生成一句"教训"，附在当前回复末尾

## 输出规范
- **结论优先** — 直接给结论，不废话
- **记忆更新** — 把新发现写入 memory
- **Skill 补丁** — 发现 skill 缺失/错误立即 patch


## 验证

（待补充）
