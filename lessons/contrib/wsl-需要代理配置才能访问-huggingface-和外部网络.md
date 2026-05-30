---
title: WSL 需要代理配置才能访问 HuggingFace 和外部网络
domain: devops
subdomain: wsl
source: bootstrap
status: draft
tags: ["project:self-grow-wiki", "severity:high", "platform:wsl", "node:hermes_wsl"]
confidence: 0.8
created: 2026-05-03
---

## 问题

WSL 内 Python 脚本无法下载 HuggingFace 模型（sentence-transformers/BGE），
git clone HuggingFace 仓库也失败，只有 Windows 侧能访问外网。

## 根因

WSL2 使用 NAT 网络，默认不继承 Windows 的代理设置。
Windows 侧有梯子（HTTP 代理），但 WSL 不知道代理地址。

## 修复

在 ~/.bashrc 中添加：
```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
export no_proxy=localhost,127.0.0.1,.local
```
端口 7890 是 Windows 侧梯子的 HTTP 代理端口（Clash/Clash Verge 默认）。

## 验证

source ~/.bashrc 后，wget https://huggingface.co 返回 200，python 下载模型成功。

## 场景

WSL2 + Windows 11，无企业代理，使用个人梯子（Clash Verge/CFW/v2rayN）。
