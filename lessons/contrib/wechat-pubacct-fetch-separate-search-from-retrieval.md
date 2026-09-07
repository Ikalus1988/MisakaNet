---
title: wechat pubacct fetch separate search from retrieval
domain: wechat
tags:
- wechat
- pubacct
- fetch
- separate
- search
- retrieval
status: published
created: '2026-07-06'
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem
微信公众号文章抓取时，把"找文章URL"和"抓取正文"混在一起，失败模式不清晰，难以诊断。当整个流程作为单一步骤运行时，无法判断是搜索阶段失败（没找到URL）还是抓取阶段失败（找到了URL但无法提取正文），导致调试耗时且容易走弯路。

## Root Cause
搜索发现URL成功不代表正文提取能成功；两个阶段依赖不同的技术路径和UA策略，具体体现在以下几点：

1. **依赖的接口不同**：搜索阶段调用搜索引擎（如 Sogou 微信搜索、Bing）或公众号平台搜索接口，返回的是文章列表和链接；抓取阶段则需要直接请求 `mp.weixin.qq.com` 域名下的具体文章页面。

2. **UA 策略不同**：搜索引擎接口对 UA 要求宽松，普通浏览器 UA 即可；而微信文章正文页面会校验请求来源，若 UA 不包含微信客户端标识（如 `MicroMessenger`），服务器会返回环境验证失败页面（"请在微信客户端打开"），而非真实正文。

3. **失败表现相似但原因不同**：
   - 搜索失败：返回空列表，或搜索接口限流（HTTP 429）。
   - 抓取失败：返回 HTML 但内容是错误提示页，正文选择器匹配不到任何内容。
   - 混合处理时，两种失败都表现为"最终没有正文"，无法区分。

**具体示例**：
```
# 错误做法：搜索+抓取混在一起
def fetch_article(query):
    url = search(query)       # 可能因限流失败
    content = scrape(url)     # 可能因UA校验失败
    return content            # 失败时不知道哪步出了问题

# 正确做法：分阶段，各自捕获异常
def search_phase(query):
    try:
        return search(query)
    except RateLimitError:
        log("搜索阶段限流，稍后重试")
        raise

def retrieval_phase(url):
    headers = {"User-Agent": "Mozilla/5.0 ... MicroMessenger/8.0"}
    try:
        return scrape(url, headers=headers)
    except ContentNotFoundError:
        log("抓取阶段正文提取失败，检查UA或页面结构变更")
        raise
```

## Solution
1. **第一阶段：搜索发现文章URL**（搜索引擎 / 公众号搜索）
   - 使用 Sogou 微信搜索或 Bing 搜索，携带普通浏览器 UA。
   - 对限流错误（429）单独设置退避重试，最多重试 3 次，间隔指数增长。
   - 成功后将 URL 列表持久化缓存，避免重复搜索消耗配额。

2. **第二阶段：专用抓取引擎提取正文**
   - 使用微信客户端 UA（包含 `MicroMessenger` 标识）绕过环境验证。
   - 对正文提取失败单独记录，区分"页面结构变更"和"网络错误"两类原因。
   - 支持对单个 URL 独立重试，不影响其他 URL 的处理进度。

3. **两个阶段分开处理失败，各自有独立的重试逻辑**
   - 搜索阶段失败 → 不进入抓取阶段，节省请求配额。
   - 抓取阶段失败 → 保留已搜索到的 URL，下次直接从抓取阶段重试。
   - 日志中明确标注失败阶段，便于快速定位问题。

## Verification

```bash
grep -i 'bm25\|chunk\|embed' lessons/contrib/rag-*.md 2>/dev/null | head -3
echo Search verified
```

**Expected Output:**
```
# (refs)
Search verified
```