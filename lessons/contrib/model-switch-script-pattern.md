---{"title": "多模型Switch脚本模式 — 双 Agent 模型管理", "confidence": "0.7", "created": "2026-05-02", "domain": "devops", "source": "bootstrap", "status": "draft", "tags": ""}---

# 多模型Switch脚本模式 — 双 Agent 模型管理

> Domain: devops | Tags: model-switching, proxy, config-management

## 问题

不同 AI Agent 使用不同的配置文件/代理通道，各自需要独立的模型管理方案。手动改配置容易出错（改错文件、两侧不一致）。
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 方案

每个 Agent 各自维护一个独立的切换脚本，各管各的配置。

### 脚本 A — 给 Agent A 用

`~/switch-agent-a` — 一键切换 Agent 的模型+代理上游。

```bash
switch-agent-a list              # 可用模型
switch-agent-a status            # 当前配置
switch-agent-a set-model <name>  # 切到指定模型
```

自动做三件事：
1. 更新 Agent A 的配置文件
2. 同步配置到跨平台路径（如 WSL + Windows 双环境）
3. 重启本地代理换上游

### 脚本 B — 给 Agent B 用

`~/switch-agent-b` — 一键切换 Agent B 的 model/provider/base_url。

```bash
switch-agent-b list              # 可用模型
switch-agent-b status            # 当前配置
switch-agent-b set-model <name>  # 切到指定模型
```

### 常用组合

```bash
# Agent A 跑模型 X，Agent B 跑模型 Y（节省配额）
switch-agent-a set-model model-x
switch-agent-b set-model model-y

# 互换
switch-agent-a set-model model-y
switch-agent-b set-model model-x
```

### 相关文件

- `~/switch-agent-a` — Agent A 切换脚本
- `~/switch-agent-b` — Agent B 切换脚本
- `~/.agent-a/config.yaml` — Agent A 配置
- `~/.agent-b/config.yaml` — Agent B 配置