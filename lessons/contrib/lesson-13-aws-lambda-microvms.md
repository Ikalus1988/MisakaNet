---
title: "AWS Lambda MicroVMs — 隔离沙箱与 Firecracker"
domain: "ops"
subdomain: "serverless"
tags: ["aws", "lambda", "microvm", "firecracker", "sandbox", "isolation"]
source: "aws.amazon.com/blogs"
status: "published"
confidence: "0.9"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---


## Problem

AI 编码助手、交互式代码环境、漏洞扫描器等需要为每个用户提供隔离的执行环境。VM 隔离强但启动慢（分钟级），容器快但共享内核需要大量加固。

## Root Cause

没有既安全隔离又快速启动的执行环境。传统选择是安全（VM）和速度（容器）的二选一。

## Solution

### AWS Lambda MicroVMs

基于 Firecracker（Lambda 底层技术）的轻量 VM：

| 特性 | VM | 容器 | MicroVM |
|------|-----|------|---------|
| 隔离级别 | 强 | 弱（共享内核） | 强（独立内核） |
| 启动时间 | 分钟 | 秒 | 毫秒 |
| 状态管理 | 有状态 | 无状态 | 有状态 |
| 暂停/恢复 | 不支持 | 不支持 | 支持 |

### 使用场景

```python
# Lambda MicroVM 函数示例
import boto3

lambda_client = boto3.client('lambda')

# 创建 MicroVM 函数
response = lambda_client.create_function(
    FunctionName='user-code-sandbox',
    Runtime='python3.12',
    Handler='index.handler',
    Code={'ZipFile': open('code.zip', 'rb').read()},
    Architectures=['arm64'],
    # MicroVM 配置
    SnapStart={'ApplyOn': 'PublishedVersions'},
    Timeout=300,
    MemorySize=512,
)

# 用户代码在隔离环境中执行
def handler(event, context):
    # 这段代码在独立的 MicroVM 中运行
    # 即使恶意代码也无法逃逸
    user_code = event['code']
    exec(user_code)
```

### Firecracker 技术

- 15 万亿+ 月度 Lambda 调用使用的底层技术
- 轻量 VMM（Virtual Machine Monitor）
- 毫秒级启动，最小内存 128MB
- REST API 控制生命周期

## Verification

1. 创建 Lambda 函数
2. 启用 SnapStart
3. 测量冷启动时间（应该 < 200ms）
4. 测试状态恢复（暂停/恢复）

## Notes

- MicroVMs 是 Lambda 的新原语，不是独立产品
- 适合多租户场景：AI Agent、代码沙箱、游戏服务器
- Source: aws.amazon.com/blogs (2026-06-22)
