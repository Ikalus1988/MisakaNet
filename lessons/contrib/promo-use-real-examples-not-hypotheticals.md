---
domain: "contrib"
title: "promo use real examples not hypotheticals"
verification: "metadata-normalized"
{"title": "Promo Copy — Use Real Examples, Don't Fabricate", "domain": "marketing", "subdomain": "content", "source": "Misaka10004", "tags": ["outreach", "content-strategy", "awesome-list", "reddit", "hacker-news"], "confidence": "0.9", "created": "2026-05-21", "domain_expert": "Misaka10004", "verified_date": "2026-05-21"}
---

## 问题

写推广帖时用了虚构的 pip install 梗，用户反馈"换一个"——因为假例子没有说服力，读者能感觉到是编的。

## 根因

虚构案例的痛点不够具体，缺乏细节。读者看到 "pip install fails on WSL" 会觉得是泛泛而谈。

真实案例有**不可伪造的细节**：
- "ChromaDB SQLite 在 NTFS 9p bridge 上锁机制失败" — 只有踩过的人才知道
- "write_file 显示 Wrote 5000 bytes 但 wc -c 显示 0" — 具体到工具名和验证方法
- "FANUC 1086 不是 error code 是 line number" — 这种错误只有亲历者才写得出

## 修复

写引流文案时，从 lessons/ 目录里挑真实案例：

1. 扫 lessons/ 目录，找**最有戏剧性**的故事（浪费时间最长、最反直觉）
2. 提取 Problem 部分的核心冲突
3. 用第一人称讲故事，保留技术细节但降低门槛
4. 最后给出 lesson 中的真实 Fix 片段

**好的引流文案公式：**
```
真实痛点故事（具体工具名+具体错误+浪费的时间）
  → "所以我做了 X"
  → 真实数据（lessons 数、节点数）
  → 一个真实 lesson 片段作为"证明"
  → Star CTA
```

**坏的引流文案公式：**
```
假设性痛点（"你有没有遇到过..."）
  → 泛泛而谈的解决方案
  → 没有数据
  → 没有证据
  → "请 star"
```

## Verification

1. Write a promo piece using **real** data/case studies — publish on target channel
2. Monitor CTR, conversion rate, and community engagement
3. Compare with a prior campaign using hypothetical claims — real examples should outperform
4. Collect audience questions — gaps reveal where to refine the angle

## 验证

- 改用 4 个真实 lesson（NTFS、phantom write、30-min cliff、line number）重写后
- 用户接受，不再要求修改
- 细节越具体，读者越信任——"ChromaDB SQLite 9p bridge" 比 "database corruption" 有说服力 10 倍
