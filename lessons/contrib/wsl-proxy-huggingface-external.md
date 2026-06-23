---{"title": "WSL Require代理Setup才能Access HuggingFace 和外部网络", "domain": "devops", "subdomain": "wsl", "source": "bootstrap", "status": "draft", "tags": ["project:self-grow-wiki", "severity:high", "platform:wsl", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03"}---

## Problem

WSL 内 Python 脚本无法Download HuggingFace 模型（sentence-transformers/BGE），
git clone HuggingFace 仓库也失败，只有 Windows 侧能访问外网。

## 根因

WSL2 Use NAT 网络，Default不继承 Windows 的代理Settings。
Windows 侧有梯子（HTTP 代理），但 WSL 不知道代理地址。

## Fix

在 ~/.bashrc 中Add：
```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export no_proxy=localhost,127.0.0.1,.local
```
端口 7890 是 Windows 侧梯子的 HTTP 代理端口（Clash/Clash Verge Default）。

## 验证

source ~/.bashrc 后，wget https://huggingface.co 返回 200，python Download模型成功。

## 场景

WSL2 + Windows 11，无企业代理，Use个人梯子（Clash Verge/CFW/v2rayN）。
