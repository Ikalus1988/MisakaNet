---
{
  "domain": "contrib",
  "title": "wechat pubacct fetch separate search from retrieval",
  "verification": "metadata-normalized",
  "created": "2026-07-06",
  "source": "unknown"
}
---
---{"title": "微信公众号抓取失败Handling（搜索与抓取分离）", "domain": "wechat", "tags": ["wechat", "fetch", "search", "crawl"]}---

## 背景
微信公众号文章抓取时，把"找文章URL"和"抓取正文"混在一起，失败模式不清晰，难以诊断。

## 根因
搜索发现URL成功不代表正文提取能成功；两个阶段依赖不同的技术路径和UA策略。

## 修复
1. 第一阶段：搜索发现文章URL（搜索引擎 / 公众号搜索）
2. 第二阶段：专用抓取引擎提取正文（使用微信客户端UA绕过环境验证）
3. 两个阶段分开处理失败，各自有独立的重试逻辑

## 验证
成功抓取目标文章并输出为 Markdown 格式
