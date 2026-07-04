{"title": "Agent 手动Update步骤（update Timeout Handling）", "domain": "devops", "source": "bootstrap", "status": "published", "confidence": "0.8", "created": "2026-05-03"}

---{"title": "Agent 手动Update步骤（update Timeout Handling）", "domain": "devops", "source": "bootstrap", "status": "published", "confidence": "0.8", "created": "2026-05-03"}---
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## Agent 手动更新步骤（update 超时处理）

## Problem
Agent 框架在通过内置更新命令更新时，因网络原因或镜像源问题，可能出现 update 超时，导致无法自动完成更新。

### 解决方案

#### 步骤 1: 检查当前版本
```bash
<agent> --version
```

#### 步骤 2: 手动下载最新版本
```bash
# Agent 手动Update步骤（update Timeout Handling）
wget https://github.com/<org>/<agent>/releases/latest/download/<agent>-latest.tar.gz
```

#### 步骤 3: 手动安装
```bash
# 解压并替换
tar -xzf <agent>-latest.tar.gz
cp <agent> /usr/local/bin/
```

#### 步骤 4: 清理旧缓存
```bash
rm -rf ~/.<agent>/cache/*
```

#### 步骤 5: 验证
```bash
<agent> --version
```

### 注意事项
- 更新前备份配置文件
- 如果使用包管理器安装，优先使用包管理器更新
- 手动更新后可能需要重新配置环境变量

### 通用性
此方案适用于大多数基于 GitHub Release 分发的 Agent 框架。如使用 Docker 部署，建议直接拉取新镜像。

## Root Cause

See problem description above for technical details.
