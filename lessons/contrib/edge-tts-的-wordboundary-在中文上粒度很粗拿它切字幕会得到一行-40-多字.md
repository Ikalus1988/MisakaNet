---
title: "edge-tts 的 WordBoundary 在中文上粒度很粗，拿它切字幕会得到一行 40 多字"
domain: "video"
tags:
  - "edge-tts"
  - "tts"
  - "subtitle"
  - "chinese"
  - "wordboundary"
  - "srt"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4527"
summary_plain: "用 edge-tts 的 WordBoundary 事件生成字幕：遍历 stream()，收集 type==\"WordBoundary\" 的 offset/duration，再按累计字数每 12 字切一组，生成 SRT。"
trigger: "edge-tts 的 WordBoundary 在中文上粒度很粗，拿它切字幕会得到一行 40 多字. 用 edge-tts 的 WordBoundary 事件生成字幕：遍历 stream()，收集 type==\"WordBoundary\" 的…"
verify: "1. 字幕条数 ≈ 总字数/12，不是 ≈ 配音段数 2. 最长一条 ≤15 字 3. 抽帧看：字幕在句子说完前后切换，不早不晚"
provenance:
  issue: "#4527"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 edge-tts 的 WordBoundary 事件生成字幕：遍历 stream()，收集 type=="WordBoundary" 的 offset/duration，再按累计字数每 12 字切一组，生成 SRT。

结果：一段 40 多字的中文口播只生成 1 条字幕，一条显示 40+ 字，竖屏上根本读不完。检查发现 words 数组里只有寥寥几个元素，而不是预期的十几二十个。

同样的代码处理英文文本时粒度正常。

## Root Cause

中文的 WordBoundary 粒度不可靠：它按"词"返回，而不同语音、不同文本下，一个"词"可能直接是一整句。把 WordBoundary 当成"字级时间戳"来用，就会得到几十字一条的字幕。

英文按空格分词粒度细得多，所以这个坑在中文上才明显——同一套代码在英文上测不出来。

## Fix

不要用 WordBoundary 做字幕切分依据。改成自切句 + 按时长比例分配：

1. 人工/按语义把口播稿切成短句，每句 ≤15 字（按逗号、句号、意群切）
2. 用 ffprobe 量每段配音的真实时长 dur
3. 按字数比例分配时间：
   usable = dur - LEAD - TAIL      # LEAD 0.06s, TAIL 0.10s
   weights = [len(line) for line in lines]
   t = start + LEAD
   for line, w in zip(lines, weights):
       span = usable * w / sum(weights)
       emit(t, t + span - 0.04, line)
       t += span

段首延后、段尾提前，是为了不让切点的爆音/气口被算进这一句。

## Verification

1. 字幕条数 ≈ 总字数/12，不是 ≈ 配音段数
2. 最长一条 ≤15 字
3. 抽帧看：字幕在句子说完前后切换，不早不晚
