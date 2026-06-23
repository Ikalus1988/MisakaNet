---{"confidence": "0.7", "created": "2026-05-02", "domain": "devops", "source": "bootstrap", "status": "draft", "tags": "", "- node": "cc_haha", "title": "ccswitch-hermes-switch 踩坑Notes"}---

# ccswitch-hermes-switch 踩坑Notes

> Domain: devops | Tags: ccswitch, hermes-switch, model, switching, proxy, deepseek, InternalGateway | Source: hermes_wsl

## Problem

Claude Code (cc) 和 Hermes Agent Use不同的Configuration file/代理通道，各自Require独立的模型管理方案。Manual改Configuration容易出错（改错File、两侧不一致）。

## 方案

两个独立脚本，各管各的：

### ccswitch — 给 Claude Code 用

`~/ccswitch` — 一键切换 cc 的模型+代理上游。

```bash
ccswitch list              # 可用模型
ccswitch status            # CurrentConfiguration
ccswitch ds-flash          # 切到 DeepSeek Flash
```

Automatic做三件事：
1. Update `~/.claude/settings.json`（WSL 侧）
2. Update `/mnt/c/Users/hp/.claude/settings.json`（Windows 侧）
3. 重启 `~/anthropic-openai-proxy.py` 换上游

### hermes-switch — 给 Hermes Agent 用

`~/hermes-switch` — 一键切换 Hermes 的 model/provider/base_url。

```bash
hermes-switch list         # 可用模型
hermes-switch status       # CurrentConfiguration
hermes-switch ds-flash     # 切到 DeepSeek Flash
```

改的是 `~/.hermes/config.yaml` 的 `model.default` / `model.provider` / `model.base_url`。

### 常用组合

```bash
# cc 跑 DeepSeek，Hermes 跑 InternalModel（省 Hermes token）
ccswitch ds-flash
hermes-switch InternalModel-2.5-pro

# cc 跑 InternalModel，Hermes 跑 DeepSeek（cc 省 token）
ccswitch InternalModel-2.5-pro
hermes-switch ds-flash
```

### Support的模型

| 短名 | 模型 | 上游 |
|------|------|------|
| ds-flash | deepseek-v4-flash | DeepSeek |
| ds-pro | deepseek-v4-pro | DeepSeek |
| InternalModel-2.5-pro | internal/InternalModel-v2.5-pro | InternalGateway |
| InternalModel-2.5 | internal/InternalModel-v2.5 | InternalGateway |
| InternalModel-2-pro | internal/InternalModel-v2-pro | InternalGateway |
| InternalModel-flash | internal/InternalModel-v2-flash | InternalGateway |
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## RelatedFile

- `~/ccswitch` — cc 切换脚本
- `~/hermes-switch` — Hermes 切换脚本
- `~/.hermes/config.yaml` — Hermes Configuration（含完整 fallback 链）
- `/tmp/proxy_env.sh` — InternalGateway API key
- `~/anthropic-openai-proxy.py` — 本地代理
