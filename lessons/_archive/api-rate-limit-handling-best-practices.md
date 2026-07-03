---
domain: "contrib"
title: "api rate limit handling best practices"
verification: "metadata-normalized"
---
---{"title": "API限流Handling最佳实践", "domain": "devops", "tags": ["api", "rate-limit", "backoff", "batch"]}---

## 背景
大批量API任务没有提前测试限流，任务中途被截断，无法续命。

## 根因
没测限流阈值；没实现指数退避；没分批checkpoint。

## 修复
1. 先跑小批量pilot测试限流阈值
2. 对429错误实现指数退避
3. 大任务分批，每批后写checkpoint
4. 任务可从上一个checkpoint恢复

## 验证
限流触发后指数退避正常，最终任务完成且无数据丢失
