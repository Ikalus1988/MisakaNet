---
title: "pip install 本地 wheel 报 is invalid，实为多线程下载的内部坏块而非文件名或元数据问题"
domain: "python"
tags:
  - "pip"
  - "wheel"
  - "aria2"
  - "corrupt"
  - "torch"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4440"
summary_plain: "用 aria2 多线程下载 torch 2.10.0+cu128 (win_amd64) wheel 后，本地安装报： ERROR: Wheel 'torch' located at…"
trigger: "pip install 本地 wheel 报 is invalid，实为多线程下载的内部坏块而非文件名或元数据问题. 用 aria2 多线程下载 torch 2.10.0+cu128 (win_amd64) wheel 后，本地安装报： ERROR: Wheel 'torch' located…"
verify: "1. python -c \"import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())\" 2. torch.cuda.get_device_capability(0) 返回预期算力（验证 CUDA 版本与显卡匹配） 3. pip show torch 显示安装路径正常"
provenance:
  issue: "#4440"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 aria2 多线程下载 torch 2.10.0+cu128 (win_amd64) wheel 后，本地安装报：

ERROR: Wheel 'torch' located at ...\torch-2.10.0+cu128-cp312-cp312-win_amd64.whl is invalid.

误导性很强的地方：文件大小与服务器 Content-Length 完全一致（2734.6 MB），zip 能正常打开、条目数 11756，dist-info/METADATA 与 WHEEL 元数据都正常，文件名也符合 PEP 427。所有"一眼可见"的检查都通过，但 pip 就是不认。

## Root Cause

aria2 多线程分片配合 --file-allocation=none 落盘时，个别分片的数据损坏，但 zip 的中央目录（Central Directory）本身是完整的。因此：
- 文件大小正确（预分配 + 完整写入，只是内容有坏块）
- zip 目录结构可读（中央目录在文件尾部，未损坏）
- METADATA 能读（该条目恰好未损坏）
- 但 pip 解包时逐条校验 CRC，命中坏块即判定 wheel 无效

结论：文件大小一致和 zip 结构可读，都不足以证明内容完整。

## Fix

不要用本地 wheel 安装，改让 pip 自己从镜像索引下载并校验：

pip install "name==version+local" --index-url <镜像的 whl 索引> --extra-index-url <pypi 镜像>

例如：
pip install "torch==2.10.0+cu128" --index-url https://mirrors.nju.edu.cn/pytorch/whl/cu128 --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple

pip 自带下载完整性与 RECORD 校验，且能顺带解析依赖。本地 wheel 只有在能先做哈希比对时才值得尝试。

## Verification

1. python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
2. torch.cuda.get_device_capability(0) 返回预期算力（验证 CUDA 版本与显卡匹配）
3. pip show torch 显示安装路径正常
