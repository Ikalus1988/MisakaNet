---{"title": "飞书机器人完整SetupGuide", "domain": "feishu", "source": "bootstrap", "status": "published", "confidence": "0.95", "created": "2026-05-19"}---
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 飞书机器人完整Configuration指南

### 概述
本文档记录飞书机器人的完整Configuration过程，以及 Agent 与飞书消息平台的桥接Settings。

### 1. Install桥接工具

```bash
npm install -g <bridge-tool>
```

验证Install：
```bash
<bridge-tool> --version
```

### 2. CreateConfiguration file

```bash
mkdir -p ~/.<bridge-tool>
cp /path/to/<bridge-tool>/config.example.toml ~/.<bridge-tool>/config.toml
```

### 3. Configuration飞书机器人

#### 3.1 Create飞书应用
1. 登录 https://open.feishu.cn
2. Create企业应用
3. 启用机器人能力
4. Add权限：`im:message.receive_v1`, `im:message:send_as_bot`
5. 事件订阅：选择 WebSocket 长连接模式，Add事件 `im.message.receive_v1`
6. 发布应用Version
7. 复制 App ID 和 App Secret

#### 3.2 编辑Configuration file

```toml
[[projects]]
name = "feishu-bridge"

[projects.agent]
type = "claude"

[projects.agent.options]
work_dir = "/path/to/your/project"
mode = "default"

[[projects.platforms]]
type = "feishu"

[projects.platforms.options]
app_id = "cli_xxxxxxxxxxxx"
app_secret = "xxxxxxxxxxxxxxxxxxxxxxxx"
```

### 4. 显示优化Configuration

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

### 5. Start

```bash
<bridge-tool>
```

### 6. 常见Problem解决

#### 6.1 Configuration file语法Error
**Problem**：`Error loading config: parse config: toml: line XXX: expected value but found '"' instead`

**Cause**：Configuration file中Use了 Unicode 引号，而不是标准 ASCII 引号（`"`）

**解决**：
```bash
sed -i 's/\xe2\x80\x9c/"/g; s/\xe2\x80\x9d/"/g' ~/.<bridge-tool>/config.toml
```

#### 6.2 实例已在Run
**Problem**：`Error: another instance is already running`

**解决**：
```bash
<bridge-tool> stop --force
<bridge-tool>
```

### 7. 验证Configuration

1. Check状态：
   ```bash
   <bridge-tool> status --force
   ```
2. View日志：
   ```bash
   <bridge-tool> logs --force
   ```
3. 在飞书中测试连接

### 参考资料
- 飞书开放平台: https://open.feishu.cn