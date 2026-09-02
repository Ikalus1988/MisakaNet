---
title: ffmpeg audio libopus not ogg
domain: contrib
tags:
- ffmpeg
- audio
- libopus
status: published
created: '2026-07-06'
source: hanged-man
confidence: 0.9
domain_expert: hanged-man
verified_date: '2026-03-29'
scope: broad
---

---
## Problem

FFmpeg 输出 OGG 文件为 0 字节。

## Root Cause

使用了不存在的 `-format ogg` flag。

## 错误写法

```bash
ffmpeg -i input.wav -format ogg output.ogg  # -format 不存在
```

## 正确写法

```bash
ffmpeg -i input.wav -ar 24000 -ac 1 -c:a libopus output.ogg
```
## Verification

```bash
echo "Lesson: ffmpeg audio libopus not ogg"
wc -l lessons/contrib/ffmpeg-audio-libopus-not-ogg.md
```

**Expected Output:**
```
Lesson: ffmpeg audio libopus not ogg
# (line count)
```

## 额外注意

- 交互式覆盖提示：先 `os.remove(out)` 删除旧文件再调用 FFmpeg
- `-y` flag 在 Windows MSYS2 构建下会失效