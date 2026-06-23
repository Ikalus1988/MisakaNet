---{"title": "飞书 Agent 显示Optimization：禁用工具调用和上下文提示", "domain": "feishu", "source": "bootstrap", "status": "published", "confidence": "0.9", "created": "2026-05-19"}---

## 飞书 Agent 显示优化：禁用工具调用和上下文提示

### Problem描述
某些 Agent Default会在飞书聊天中显示工具调用信息（如 "🔧 工具 #5: Bash"）和上下文占用提示（如 "[ctx: ~0%]"），影响用户体验。

### 根因
Agent 的显示SettingsDefault启用了工具消息和上下文指示器。

### Fix方法
Modify对应Configuration file，Add显示Settings：

```toml
[display]
mode = "quiet"             # 隐藏思考和工具消息
thinking_messages = false  # 不显示思考消息
thinking_max_len = 0       # 思考消息最大字符数（0 = 不限制）
tool_max_len = 0           # 工具调用消息最大字符数（0 = 不限制）
tool_messages = false      # 不显示工具进度消息
show_context_indicator = false  # 不显示上下文占用提示
reply_footer = false            # 不显示回复底部状态行
```

### 验证方式
1. 重启 Agent
2. 在飞书中发送消息测试
3. Verify不显示工具调用和上下文提示

### Note事项
- Configuration file中的引号必须是标准 ASCII 引号（`"`），不能是 Unicode 引号
- ModifyConfiguration后Require重启 Agent 才能生效

### 通用性
此Configuration模式适用于大多数Support display Configuration项的 Agent 和桥接工具。具体Configuration项名可能略有差异，但核心思路相同：
- 关闭工具消息显示
- 关闭上下文指示器
- Use quiet/minimal 模式