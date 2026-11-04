---
title: "Whisper transcribes its own initial_prompt when the audio is near-silence — gate on audio energy first"
domain: "llm"
tags:
  - "whisper"
  - "faster-whisper"
  - "asr"
  - "hallucination"
  - "vad"
  - "silence"
  - "initial_prompt"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-11-05"
source: "intake-4124"
summary_plain: "A 13.8 s short video with almost no speech (background music only) came back from faster-whisper with exactly one…"
trigger: "Whisper transcribes its own initial_prompt when the audio is near-silence — gate on audio energy first. A 13.8 s short video with almost no speech (background…"
verify: "Same silent clip after the fix: 0 characters, marked \"no dialogue\", no ASR hallucination. Control clip with real speech (13.5 s) still produced 6 segments / 48 characters, with segments aligned to…"
provenance:
  issue: "#4124"
  related: "#4221"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A 13.8 s short video with almost no speech (background music only) came back from faster-whisper with exactly one line: "请加标点符号。" - which is the initial_prompt that was passed in. Character count looked non-zero, so a pipeline that only checks "did we get text" happily treats it as real content. Silently poisoning downstream summarisation.

## Root Cause

Whisper is trained to produce fluent text and will fall back to the prompt when the input has no usable speech. faster-whisper's vad_filter only drops digital silence; background music is loud enough to survive VAD, so silent-speech clips still get decoded and the decoder emits the prompt. The model has no notion of "there was nothing to transcribe".

## Fix

Three layers, cheap before expensive: (1) Voice gate BEFORE transcription - decode the first 30 s to 16 kHz mono wav, compute RMS over 0.25 s windows with stdlib wave (no numpy needed), and skip ASR entirely when the fraction of windows above about -32 dB is low (measured 0.07 on this clip). (2) Post-filter segments whose text contains the initial_prompt (hard text match) and drop segments with segment.avg_logprob < -0.35. **Do not gate on segment.no_speech_prob**: measured 2026-11-04 on a 220 s talking-head clip it spans 0.03-0.97 on segments that are genuine speech, so a 0.6 gate deleted 11 of 14 real segments (262 chars left of 1083), while a music-only clip scored a flat 0.876. compression_ratio does not separate them either (1.08-1.33 vs 1.19). Log the raw segment count and the per-reason drop counts, so a byte-short transcript can be told apart from a filtered one. (3) Merge adjacent duplicate segments within 3 s (VAD often splits one sentence into two).

## Verification

Same silent clip after the fix: 0 characters, marked "no dialogue", no ASR hallucination. Control clip with real speech (13.5 s) still produced 6 segments / 48 characters, with segments aligned to the burned-in subtitles. So the gate removes hallucinations without eating real speech.

## Errata (2026-11-05)

The first version of this lesson recommended segment.no_speech_prob > 0.6. That threshold is wrong and
was removed after a stale-lesson report measured it (#4221, faster-whisper small/int8, zh, vad_filter=True):

| clip | segment.no_speech_prob | segment.avg_logprob |
|---|---|---|
| 220 s talking head (real speech) | 0.03-0.97 on genuine speech | -0.06 to -0.16 |
| 24 s music only | 0.876 flat | -0.50 |
| 14 s near-silence | - | one prompt-echo segment |

At `segment.no_speech_prob > 0.6` the 220 s clip lost 11 of 14 real segments. The gate that works is
segment.avg_logprob < -0.35 (with segment.no_speech_prob left at 0.99 as a near-dead safety net), which keeps
14 segments / 1083 chars on the speech clip and drops all 8 music segments and the silence segment.
