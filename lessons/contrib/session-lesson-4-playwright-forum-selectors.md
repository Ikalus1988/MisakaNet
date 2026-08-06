---
title: Playwright Forum Selectors — WoltLab/IPS/Common Patterns
domain: ops
subdomain: scraping
tags: ["playwright", "scraping", "selectors", "forum", "automation"]
source: practical-experience
status: published
confidence: 0.85
created: 2026-07-02
verified_date: 
domain_expert: 
---

## Problem

不同论坛使用不同的 CMS（WoltLab、IPS Community、Discourse），HTML 结构各异。写选择器需要逐个分析。

## Root Cause

每个论坛 CMS 有自己的 CSS 类名和 DOM 结构。没有统一的选择器标准。

## Solution

### 论坛 CMS 识别

```javascript
// 快速识别 CMS
const cms = await page.evaluate(() => {
  if (document.querySelector('.wbbThread')) return 'WoltLab';
  if (document.querySelector('.ipsDataItem')) return 'IPS Community';
  if (document.querySelector('.topic-list')) return 'Discourse';
  if (document.querySelector('[data-thread-id]')) return 'Custom';
  return 'Unknown';
});
```

### WoltLab (robot-forum.com)

```javascript
// 帖子列表
const threads = await page.evaluate(() => {
  const results = [];
  document.querySelectorAll('ol.wbbThread').forEach(item => {
    const titleEl = item.querySelector('.columnSubject h3 a');
    const stats = item.querySelectorAll('.columnStats .statsDataList');
    const replies = stats[0] ? parseInt(stats[0].querySelector('dd').textContent) : 0;
    const views = stats[1] ? parseInt(stats[1].querySelector('dd').textContent) : 0;
    const resolved = item.dataset.isDone === '1';  // 关键：data-is-done 属性
    const dateEl = item.querySelector('woltlab-core-date-time');
    
    if (titleEl) {
      results.push({
        title: titleEl.textContent.trim(),
        href: titleEl.href,
        replies, views, resolved,
        date: dateEl ? dateEl.getAttribute('date') : ''
      });
    }
  });
  return results;
});
```

### IPS Community (mrplc.com)

```javascript
const threads = await page.evaluate(() => {
  const results = [];
  document.querySelectorAll('.ipsDataItem').forEach(item => {
    const titleEl = item.querySelector('.ipsDataItem_title a');
    const meta = item.querySelector('.ipsDataItem_meta');
    if (titleEl) {
      results.push({
        title: titleEl.textContent.trim(),
        href: titleEl.href,
        meta: meta ? meta.textContent.trim() : ''
      });
    }
  });
  return results;
});
```

### 通用提取策略

```javascript
// 策略 1：按链接模式匹配
const links = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('a[href*="/thread/"]'))
    .map(a => ({ title: a.textContent.trim(), href: a.href }));
});

// 策略 2：按文本内容匹配
const text = await page.evaluate(() => document.body.innerText);
const titles = text.match(/\d+ replies.*?\n(.+)/g);

// 策略 3：按 data 属性匹配
const items = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('[data-thread-id], [data-topic-id]'))
    .map(el => ({ id: el.dataset.threadId || el.dataset.topicId, text: el.innerText.substring(0, 100) }));
});
```

### 等待策略

```javascript
// 等待内容加载
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
await page.waitForTimeout(3000);  // 等待 JS 渲染

// 等待特定元素
await page.waitForSelector('.wbbThread', { timeout: 10000 });

// 等待网络空闲（SPA）
await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
```

## Verification

1. 识别目标论坛的 CMS 类型
2. 使用对应的选择器提取帖子列表
3. 验证提取的数据完整性（标题、回复数、日期）
4. 测试翻页（如果有）

## Notes

- WoltLab 的 `data-is-done` 属性标识已解决帖子
- IPS Community 的 `.ipsDataItem` 是通用容器
- 先用 `page.evaluate(() => document.body.innerText)` 快速预览内容
- Source: practical-experience
