---{"title": "cc-connect 飞书显示Optimization：禁用工具调用和上下文提示", "domain": "feishu", "subdomain": "cc-connect", "source": "bootstrap", "status": "published", "confidence": "0.9", "created": "2026-05-19"}---

## cc-connect 飞书显示优化：禁用工具调用和上下文提示

### Problem描述
cc-connect Default会在飞书聊天中显示工具调用信息（如 "🔧 工具 #5: Bash"）和上下文占用提示（如 "[ctx: ~0%]"），影响用户体验。

### 根因
cc-connect 的显示SettingsDefault启用了工具消息和上下文指示器。

### Fix方法
Modify `~/.cc-connect/config.toml` Configuration file，Add显示Settings：

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
1. 重启 cc-connect：`cc-connect stop --force && cc-connect`
2. 在飞书中发送消息测试
3. Verify不显示工具调用和上下文提示

### Note事项
- Configuration file中的引号必须是标准 ASCII 引号（`"`），不能是 Unicode 引号（`"` `"`）
- ModifyConfiguration后Require重启 cc-connect 才能生效
- Use `cc-connect stop --force` 停止正在Run的实例

### RelatedFile
- Configuration file：`~/.cc-connect/config.toml`
- 日志View：`cc-connect logs --force`
- 状态View：`cc-connect status --force`
