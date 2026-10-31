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
updated: "2026-10-30"
source: "intake-4124"
summary_plain: "A 13.8 s short video with almost no speech (background music only) came back from faster-whisper with exactly one…"
trigger: "Whisper transcribes its own initial_prompt when the audio is near-silence — gate on audio energy first. A 13.8 s short video with almost no speech (background…"
verify: "Same silent clip after the fix: 0 characters, marked \"no dialogue\", no ASR hallucination. Control clip with real speech (13.5 s) still produced 6 segments / 48 characters, with segments aligned to…"
provenance:
  issue: "#4124"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A 13.8 s short video with almost no speech (background music only) came back from faster-whisper with exactly one line: "请加标点符号。" - which is the initial_prompt that was passed in. Character count looked non-zero, so a pipeline that only checks "did we get text" happily treats it as real content. Silently poisoning downstream summarisation.

## Root Cause

Whisper is trained to produce fluent text and will fall back to the prompt when the input has no usable speech. faster-whisper's vad_filter only drops digital silence; background music is loud enough to survive VAD, so silent-speech clips still get decoded and the decoder emits the prompt. The model has no notion of "there was nothing to transcribe".

## Fix

Three layers, cheap before expensive: (1) Voice gate BEFORE transcription - decode the first 30 s to 16 kHz mono wav, compute RMS over 0.25 s windows with stdlib wave (no numpy needed), and skip ASR entirely when the fraction of windows above about -32 dB is low (measured 0.07 on this clip). (2) Post-filter segments whose text contains the initial_prompt, plus segment.no_speech_prob > 0.6 and segment.avg_logprob < -1.2. (3) Merge adjacent duplicate segments within 3 s (VAD often splits one sentence into two).

## Verification

Same silent clip after the fix: 0 characters, marked "no dialogue", no ASR hallucination. Control clip with real speech (13.5 s) still produced 6 segments / 48 characters, with segments aligned to the burned-in subtitles. So the gate removes hallucinations without eating real speech.
