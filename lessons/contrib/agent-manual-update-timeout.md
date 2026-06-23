---{"title": "Agent ManualUpdateSteps（update Timeout Handling）", "domain": "devops", "source": "bootstrap", "status": "draft", "confidence": "0.8", "created": "2026-05-03"}---
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## Agent ManualUpdateSteps（update 超时处理）

### Problem
Agent 框架在Via内置UpdateCommandUpdate时，因网络Cause或镜像源Problem，可能出现 update 超时，导致无法Automatic完成Update。

### Solution

#### Steps 1: CheckCurrentVersion
```bash
<agent> --version
```

#### Steps 2: ManualDownload最新Version
```bash
# Agent ManualUpdateSteps（update Timeout Handling）
wget https://github.com/<org>/<agent>/releases/latest/download/<agent>-latest.tar.gz
```

#### Steps 3: ManualInstall
```bash
# 解压并替换
tar -xzf <agent>-latest.tar.gz
cp <agent> /usr/local/bin/
```

#### Steps 4: 清理旧缓存
```bash
rm -rf ~/.<agent>/cache/*
```

#### Steps 5: 验证
```bash
<agent> --version
```

### Note事项
- Update前备份Configuration file
- 如果Use包管理器Install，优先Use包管理器Update
- ManualUpdate后可能Require重新ConfigurationEnvironment variable

### 通用性
此方案适用于大多数基于 GitHub Release 分发的 Agent 框架。如Use Docker 部署，Recommended直接拉取新镜像。