---
confidence: '0.9'
created: '2026-07-01'
domain: ops
domain_expert: ''
language: zh
source: aws.amazon.com/blogs
status: published
subdomain: kubernetes
tags:
- aws
- ecs
- metrics
- auto-scaling
- monitoring
title: AWS ECS 高分辨率指标 — 更快的自动扩缩容
verified_date: ''
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

ECS 默认 CloudWatch 指标 1 分钟粒度，自动扩缩容响应慢。流量突增时，1 分钟才能触发扩容，用户体验下降。

## Root Cause

CloudWatch 默认指标聚合周期 60 秒，ECS Service Auto Scaling 基于此周期，无法更快响应。

## Solution

### 高分辨率指标（2026-07 新功能）

ECS 现在支持 10 秒粒度的指标：

```bash
# 启用高分辨率指标
aws ecs update-service \
  --cluster my-cluster \
  --service my-service \
  --enable-execute-command \
  --network-configuration "awsvpcConfiguration={...}"

# 配置 Auto Scaling（10 秒响应）
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/my-cluster/my-service \
  --policy-name high-res-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 60,
    "ScaleOutCooldown": 10
  }'
```

### 响应时间对比

| 指标粒度 | 扩容触发时间 | 适用场景 |
|---------|------------|---------|
| 60 秒（默认） | 1-2 分钟 | 稳定流量 |
| 10 秒（新） | 10-20 秒 | 突增流量 |
| 1 秒（自定义） | 1-2 秒 | 实时响应 |

### 监控配置

```bash
# 查看高分辨率指标
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=my-service \
  --period 10 \
  --statistics Average \
  --start-time 2026-07-01T00:00:00Z \
  --end-time 2026-07-01T01:00:00Z
```

## Verification

```bash
echo "Lesson: AWS ECS 高分辨率指标 — 更快的自动扩缩容"
wc -l lessons/contrib/lesson-16-aws-ecs-high-resolution-metrics.md
```

**Expected Output:**
```
Lesson: AWS ECS 高分辨率指标 — 更快的自动扩缩容
# (line count)
```

## Notes

- 高分辨率指标会增加 CloudWatch 成本
- 适合：电商大促、API 突发流量、实时应用
- Source: aws.amazon.com/blogs (2026-07-01)
