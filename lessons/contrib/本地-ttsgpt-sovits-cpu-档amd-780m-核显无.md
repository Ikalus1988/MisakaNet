---
title: "本地 TTS（GPT-SoVITS CPU 档，AMD 780M 核显无 CUDA）说话持续卡顿。根因不是内存或线程配置：实测 RTF 稳定在 1.8-2.8（"
domain: "dsh"
tags:
  - "tts"
  - "gpt"
  - "sovits"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4010"
summary_plain: "本地 TTS（GPT-SoVITS CPU 档，AMD 780M 核显无 CUDA）说话持续卡顿。"
trigger: "本地 TTS（GPT-SoVITS CPU 档，AMD 780M 核显无 CUDA）说话持续卡顿。根因不是内存或线程配置：实测 RTF 稳定在 1.8-2.8（. 本地 TTS（GPT-SoVITS CPU 档，AMD 780M 核显无 CUDA）说话持续卡顿。"
verify: "补丁后用假 RtAudio 驱动真实 Player 类（按 RTF=2 喂 16 块共 8 秒音频）：补丁前写入即入队、播放持续饥饿；补丁后 write 期间入队 0 帧，flush() 后一次入队 400 帧、总长 8.00s、饿死 0 次。应用内 server.phase=ready、warmed=True、lamp=online。"
provenance:
  issue: "#4010"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

本地 TTS（GPT-SoVITS CPU 档，AMD 780M 核显无 CUDA）说话持续卡顿。

## Root Cause

根因不是内存或线程配置：实测 RTF 稳定在 1.8-2.8（合成 1 秒音频要 2 秒算），且与句长、语速、parallel_infer、batch_size、text_split_method 全部无关——短句 RTF 反而更差（固定开销占比高）。

## Fix

CPU 档无法把 RTF 压到 1 以下时，改播放策略而不是继续调参：把「边合成边入队」改成「积满整句再一次性入队」。具体到 audify/RtAudio 这类无界且 write() 不阻塞的输出队列——write() 期间只把 PCM 累加到 pending，flush() 时再按 20ms 帧一次性写进声卡。听感从"持续卡顿"变成"开头多等一个合成时长、之后整句连续"。同时 cut()/close() 必须清空 pending，否则打断后会串音。

## Verification

补丁后用假 RtAudio 驱动真实 Player 类（按 RTF=2 喂 16 块共 8 秒音频）：补丁前写入即入队、播放持续饥饿；补丁后 write 期间入队 0 帧，flush() 后一次入队 400 帧、总长 8.00s、饿死 0 次。应用内 server.phase=ready、warmed=True、lamp=online。
