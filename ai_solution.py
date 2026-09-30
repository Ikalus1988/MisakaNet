```markdown
# 问题解答

## 问题
1. AgentCap支持的子命令是什么？  
2. macOS代码当前支持的机器可读XML输出选项是什么？

## 根因
需要明确AgentCap的子命令和codes命令的XML输出选项。

## 解决方案
AgentCap支持的子命令是`get`，用于按精确匹配查找能力。codes命令当前支持的机器可读XML输出选项是`--xml`。

## 验证
```bash
agent-cap get
# 验证输出：返回指定的能力。

codes --xml
# 验证输出：以XML格式输出系统版本信息。
```

该内容已放置于`lessons/core/ai_system.md`中。
```