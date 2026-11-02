---
title: "Coopanion 的 GPT-SoVITS 语音扩展（@wocwang/cortico-world-gpt-sovits-for-coopanion）推理服务"
domain: "windows"
tags:
  - "coopanion"
  - "gpt"
  - "sovits"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4006"
summary_plain: "Coopanion 的 GPT-SoVITS 语音扩展（@wocwang/cortico-world-gpt-sovits-for-coopanion）推理服务反复启动失败，报 ModuleNotFoundError: No…"
trigger: "Coopanion 的 GPT-SoVITS 语音扩展（@wocwang/cortico-world-gpt-sovits-for-coopanion）推理服务. Coopanion 的 GPT-SoVITS…"
verify: "重装后：在运行时根目录按 api_v2.py 的方式 append 两条 sys.path 后 `from GPT_SoVITS.TTS_infer_pack.TTS import TTS` 与 `import BigVGAN` 均通过；POST /api/webui/providers/world%3Agpt-sovits/panels/voice/restart 后…"
provenance:
  issue: "#4006"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Coopanion 的 GPT-SoVITS 语音扩展（@wocwang/cortico-world-gpt-sovits-for-coopanion）推理服务反复启动失败，报 ModuleNotFoundError: No module named 'BigVGAN'。

## Root Cause

根因是运行时目录解压不完整：上游 e91506f1 的 GPT_SoVITS 下应有 12 个子目录，本地只有 4 个（AR/TTS_infer_pack/text/pretrained_models），BigVGAN、feature_extractor、module、Accel、configs、eres2net、f5_tts、prepare_datasets 全部缺失。

## Fix

用官方 runtime zip 完整重装：下载 catalog 里钉住的那个包（ModelScope 源比 GitHub Release 快约 6 倍），校验 SHA-256 后解压到临时目录，先验证 `GPT_SoVITS` 下 12 个子目录齐全并试跑 TTS 导入，再按插件的 removeTreeSafely 逻辑（先拆 junction 再删目录，否则 Windows 上会递归删掉 junction 指向的权重）替换运行时目录，最后重建 pretrained_models junction。curl 大文件下载要用 -C - 续传，199-988MB 级别在 ModelScope 上仍会 Connection reset。

## Verification

重装后：在运行时根目录按 api_v2.py 的方式 append 两条 sys.path 后 `from GPT_SoVITS.TTS_infer_pack.TTS import TTS` 与 `import BigVGAN` 均通过；POST /api/webui/providers/world%3Agpt-sovits/panels/voice/restart 后 server.phase=ready、warmed=True；直接 POST http://127.0.0.1:5376/tts 合成出 500KB 合法 WAV（RIFF/WAVE 头）；manifest 里该 world 的 lamp 从 error 变 online。注意 provider id 要带命名空间前缀 world:gpt-sovits 并做 URL 编码，body 形如 {"args":[...]}。
