---
title: "Paddle/PaddleSci 训练（train_auto_paddle.py，FFN 逐点 MLP 模式）在容器内刚开始训练约 16 秒后进程被杀，退出码"
domain: "dsh"
tags:
  - "paddle"
  - "paddlesci"
  - "train"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5179"
summary_plain: "Paddle/PaddleSci 训练（train_auto_paddle.py，FFN 逐点 MLP 模式）在容器内刚开始训练约 16 秒后进程被杀，退出码 137：`Training failed with exit code…"
trigger: "exit code 137 training OOM paddle ffn per-point mlp killed STARTING TRAINING"
verify: "容器内重跑训练并加 batch_size=1 与缩小 hidden_dims 后，进程不再以 137 被杀、进入正常训练迭代；原先默认配置必复现 137。 容器内重跑训练加 batch_size=1 且缩小 hidden_dims：进程不再以 137 被杀，正常进入训练迭代；默认配置必复现 137"
provenance:
  issue: "#5179"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Paddle/PaddleSci 训练（train_auto_paddle.py，FFN 逐点 MLP 模式）在容器内刚开始训练约 16 秒后进程被杀，退出码 137：`Training failed with exit code: 137`。日志止于 "STARTING TRAINING"，之后无任何训练输出。

## Root Cause

Exit code 137 = 128 + 9 (SIGKILL)，由容器 cgroup OOM-killer 触发（内存耗尽）。此时数据已成功加载（Solver 已构造、打印了 STARTING TRAINING），进程死在 solver.train() 的前向传播阶段。FFN 对非结构网格（如 ElastoPlastoDynamics2D）采用逐点 MLP：batch (B,N,C) reshape 为 (B*N,C) 后过全连接网络，单层激活张量 = B*N×hidden_dims[0]。当网格顶点数 N 大（数万+）、hidden_dims 宽（默认 [512,256,128]，某些域甚至为 [8192,4096,2048]）时，多层前向+反向需保留全部中间激活，叠加数据集全量驻留内存（load_data + to_pandas 全量读入，max_cases 默认 null 无上限），峰值内存瞬间超限被杀为 137。

## Fix

缩小单步峰值内存：大幅减小 DATALOADER.batch_size（如 1）；显式缩小 FFN hidden_dims（如 model.FFN.hidden_dims=[32,16]）或对逐点网格域（tensile2d/elastoplastodynamics2d）在 create_model_from_config 补 hidden_dims 降级保护（tensile2d 分支已有，elastoplastodynamics2d 分支缺失）；对超大数据集改用流式/分批加载，避免全量 load_data + to_pandas 常驻内存。

## Verification

容器内重跑训练并加 batch_size=1 与缩小 hidden_dims 后，进程不再以 137 被杀、进入正常训练迭代；原先默认配置必复现 137。

容器内重跑训练加 batch_size=1 且缩小 hidden_dims：进程不再以 137 被杀，正常进入训练迭代；默认配置必复现 137
