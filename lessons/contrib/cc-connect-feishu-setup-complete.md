---
title: cc-connect 飞书机器人完整配置指南
domain: feishu
subdomain: cc-connect
source: bootstrap
status: published
confidence: 0.95
created: 2026-05-19
---

## cc-connect 飞书机器人完整配置指南

### 概述
cc-connect 是一个连接 AI 编码代理（如 Claude Code）与消息平台（如飞书）的桥接工具。本文档记录完整的配置过程和常见问题解决方案。

### 1. 安装 cc-connect

```bash
npm install -g cc-connect
```

验证安装：
```bash
cc-connect --version
```

### 2. 创建配置文件

```bash
mkdir -p ~/.cc-connect
cp /path/to/cc-connect/config.example.toml ~/.cc-connect/config.toml
```

### 3. 配置飞书机器人

#### 3.1 创建飞书应用
1. 登录 https://open.feishu.cn
2. 创建企业应用
3. 启用机器人能力
4. 添加权限：`im:message.receive_v1`, `im:message:send_as_bot`
5. 事件订阅：选择 WebSocket 长连接模式，添加事件 `im.message.receive_v1`
6. 发布应用版本
7. 复制 App ID 和 App Secret

#### 3.2 编辑配置文件

```toml
[[projects]]
name = "cc-connect-feishu"

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/path/to/your/project"
mode = "default"

[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_xxxxxxxxxxxx"
app_secret = "xxxxxxxxxxxxxxxxxxxxxxxx"
```

### 4. 显示优化配置

禁用工具调用和上下文提示：

```toml
[display]
mode = "quiet"
thinking_messages = false
thinking_max_len = 0
tool_max_len = 0
tool_messages = false
show_context_indicator = false
reply_footer = false
```

### 5. 启动 cc-connect

```bash
cc-connect
```

### 6. 常见问题解决

#### 6.1 配置文件语法错误
**问题**：`Error loading config: parse config: toml: line XXX: expected value but found '"' instead`

**原因**：配置文件中使用了 Unicode 引号（`"` `"`），而不是标准 ASCII 引号（`"`）

**解决**：
```bash
sed -i 's/\xe2\x80\x9c/"/g; s/\xe2\x80\x9d/"/g' ~/.cc-connect/config.toml
```

#### 6.2 cc-connect 已在运行
**问题**：`Error: another cc-connect instance is already running`

**解决**：
```bash
cc-connect stop --force
cc-connect
```

#### 6.3 飞书机器人无反应
**问题**：发送消息后机器人无反应

**检查项**：
1. 飞书开放平台事件订阅是否配置正确
2. 是否启用了 `im.message.receive_v1` 事件
3. 是否选择了 WebSocket 长连接模式
4. 应用是否已发布

### 7. 验证配置

1. 检查 cc-connect 状态：
   ```bash
   cc-connect status --force
   ```

2. 查看日志：
   ```bash
   cc-connect logs --force
   ```

3. 在飞书中测试：
   - 搜索机器人名称
   - 发送消息测试
   - 确认不显示工具调用和上下文提示

### 8. 相关文件

- 配置文件：`~/.cc-connect/config.toml`
- 会话数据：`~/.cc-connect/sessions/`
- API socket：`~/.cc-connect/run/api.sock`

### 9. 参考资料

- cc-connect GitHub: https://github.com/chenhg5/cc-connect
- 飞书开放平台: https://open.feishu.cn
