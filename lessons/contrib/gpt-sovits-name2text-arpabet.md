---
title: gpt sovits name2text arpabet
domain: contrib
tags:
- sovits
- name2text
- arpabet
status: published
created: '2026-07-06'
source: hanged-man
confidence: 0.9
domain_expert: hanged-man
verified_date: '2026-04-06'
scope: narrow
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

---
## Problem

训练时数据加载器逐字查 phoneme 词典，全部 KeyError。

## Root Cause

2-name2text.txt 第二列误写为中文原文，正确应为 ARPABET 音素符号（空格分隔）。

## 正确格式

```
basename	{w o2 h en3 AA ai4 ...}	{type}	{language}
```

注意：
- 中文→ARPABET：用 `g2p(text_normalize(text))`
- **必须先 `text_normalize` 再 g2p**，中文标点（`，` `。`）需先规范化为 ASCII 标点
- 音频文件必须加 `.wav` 扩展名，无扩展名的 WAV ffmpeg 无法识别
## Verification

```bash
echo "Lesson: gpt sovits name2text arpabet"
wc -l lessons/contrib/gpt-sovits-name2text-arpabet.md
```

**Expected Output:**
```
Lesson: gpt sovits name2text arpabet
# (line count)
```

## Lessons Learned

音素训练数据格式必须严格按文档，词典只认音标不认文字。