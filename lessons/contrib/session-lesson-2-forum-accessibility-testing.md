{"title": "Forum Accessibility Testing — Systematic Reachability Check", "domain": "ops", "subdomain": "scraping", "tags": ["scraping", "accessibility", "forum", "testing", "network", "automation"], "source": "practical-experience", "status": "published", "confidence": 0.9, "created": "2026-07-02", "verified_date": "", "domain_expert": ""}

## Problem

批量抓取前不知道哪些论坛可达。盲目尝试浪费时间，需要系统化的可达性测试。

## Root Cause

不同论坛有不同的反爬策略（Cloudflare、登录墙、API 限制），网络环境也影响可达性（GFW、DNS 污染）。

## Solution

### 三级测试流程

```bash
# Level 1: HTTP 状态码
for site in "news.ycombinator.com" "dev.to" "lobste.rs" "juejin.cn" "reddit.com"; do
  code=$(curl -sL --max-time 5 -o /dev/null -w "%{http_code}" "https://$site/" -H "User-Agent: Mozilla/5.0")
  echo "$site: $code"
done

# Level 2: API 可用性
curl -sL --max-time 8 "https://hn.algolia.com/api/v1/search?query=test&hitsPerPage=1" | head -100
curl -sL --max-time 8 "https://dev.to/api/articles?per_page=1" -H "User-Agent: Mozilla/5.0" | head -100
curl -sL --max-time 8 "https://lobste.rs/hottest.json" | head -100

# Level 3: Playwright 渲染
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://target-site.com', { waitUntil: 'domcontentloaded', timeout: 15000 });
  await page.waitForTimeout(3000);
  const text = await page.evaluate(() => document.body.innerText.substring(0, 500));
  console.log(text);
  await browser.close();
})().catch(e => console.error(e.message));
"
```

### 可达性分类

| 分类 | HTTP Code | API | Playwright | 处理方式 |
|------|-----------|-----|------------|---------|
| 完全可达 | 200 | ✅ | ✅ | 优先用 API |
| API 可达 | 200 | ✅ | — | 用 API |
| 爬虫可达 | 200 | ❌ | ✅ | 用 Playwright |
| 反爬阻断 | 403/429 | ❌ | ❌ | 需要代理或绕过 |
| 网络阻断 | 000/timeout | ❌ | ❌ | 需要代理 |
| 需登录 | 200 | ❌ | 需登录 | 提取 cookie 或跳过 |

### 常见阻断模式

| 模式 | 诊断 | 解决 |
|------|------|------|
| GFW SNI 阻断 | TLS 握手超时 | 代理 |
| Cloudflare | 403 + challenge page | Playwright + 等待 |
| API 限流 | 429 Too Many Requests | 降低频率 |
| 登录墙 | 200 但内容为空 | 提取浏览器 cookie |

## Verification

1. 运行 Level 1 测试 → 记录所有站点状态
2. 对可达站点运行 Level 2 测试 → 记录 API 可用性
3. 对 API 不可用但 HTTP 可达的站点运行 Level 3 测试
4. 输出可达性报告

## Notes

- 先测试可达性，再写抓取逻辑
- Reddit/SO/V2EX 在中国大陆被墙，不要浪费时间尝试
- Source: practical-experience
