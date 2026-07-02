{"title": "Cloudflare Workflows — 持久化多步骤执行", "domain": "ops", "subdomain": "workflow", "tags": ["cloudflare", "workflows", "durable", "serverless", "state-machine"], "source": "blog.cloudflare.com", "status": "published", "confidence": "0.85", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

Serverless 函数是无状态的。多步骤流程（审批、数据处理、编排）需要跨步骤持久化状态，传统方式需要外部数据库或消息队列。

## Root Cause

Lambda/Cloudflare Workers 每次调用都是独立的，没有内置的状态持久化机制。

## Solution

### Cloudflare Workflows

```javascript
// 定义持久化工作流
export default {
  async run(event, step) {
    // Step 1: 持久化执行（自动重试、状态持久化）
    const userData = await step.do("fetch-user", async () => {
      return await fetch(`https://api.example.com/users/${event.userId}`);
    });

    // Step 2: 处理数据
    const processed = await step.do("process-data", async () => {
      return await processData(userData);
    });

    // Step 3: 保存结果
    await step.do("save-result", async () => {
      await saveToDatabase(processed);
    });

    // Step 4: 发送通知
    await step.do("send-notification", async () => {
      await sendEmail(processed.email, "Processing complete");
    });
  }
};
```

### 关键特性

| 特性 | 说明 |
|------|------|
| 自动重试 | 每个 step 自动重试，指数退避 |
| 状态持久化 | 步骤间状态自动保存 |
| 长时间运行 | 支持天/周/月级别的流程 |
| 内置错误处理 | 失败步骤可回滚 |

### 与 Lambda 对比

| 特性 | Lambda | Cloudflare Workflows |
|------|--------|---------------------|
| 状态持久化 | 需要外部 | 内置 |
| 长时间运行 | 15 分钟限制 | 无限制 |
| 重试逻辑 | 需要自己实现 | 内置 |
| 编排 | Step Functions（额外服务） | 内置 |

## Verification

1. 创建一个 4 步工作流
2. 模拟第 2 步失败
3. 验证自动重试
4. 验证状态在步骤间持久化

## Notes

- 适合：审批流程、数据处理管道、订单编排
- 不适合：实时响应（< 100ms）
- Source: blog.cloudflare.com (2026-06-25)
