---
title: "HuggingFace mirror is unusable for faster-whisper models in CN: 110 KB/s plus hf-xet 401 from cas-server; use ModelScope"
domain: "devops"
tags:
  - "huggingface"
  - "hf-mirror"
  - "hf-xet"
  - "modelscope"
  - "faster-whisper"
  - "ctranslate2"
  - "download"
  - "china"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4125"
summary_plain: "Downloading Systran/faster-whisper-small (461 MB) through HF_ENDPOINT=https://hf-mirror.com failed twice: first with…"
trigger: "HuggingFace mirror is unusable for faster-whisper models in CN: 110 KB/s plus hf-xet 401 from cas-server; use ModelScope. Downloading…"
verify: "Measured 2.3 MB/s from ModelScope - 461 MB in about two minutes versus 70+ minutes on the mirror; the downloaded directory loads and transcribes correctly, and model.bin is 461.1 MB (full size, not…"
provenance:
  issue: "#4125"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Downloading Systran/faster-whisper-small (461 MB) through HF_ENDPOINT=https://hf-mirror.com failed twice: first with "HTTP status client error (401 Unauthorized), domain: https://cas-server.xethub.hf.co/v2/reconstructions/..." from hf-xet, then - after HF_HUB_DISABLE_XET=1 - with an effective ~110 KB/s so the transfer needed about 70 minutes and repeatedly stalled, leaving only tokenizer.json on disk.

## Root Cause

Two independent problems. (1) Current huggingface_hub uses Xet storage by default; the Xet CAS server lives on xethub.hf.co, which the mirror does not proxy, so the reconstruction call goes to the real endpoint and gets rejected - disabling xet is mandatory but not sufficient. (2) The mirror throttles large blobs such as model.bin hard enough that a 461 MB model is impractical.

## Fix

Fetch CTranslate2-format models from ModelScope instead. Per-file API: https://modelscope.cn/api/v1/models/<org>/<repo>/repo?Revision=master&FilePath=<file>, downloading model.bin, tokenizer.json, vocabulary.txt, config.json into one directory, then faster_whisper.WhisperModel("<local-dir>") loads it directly. Range requests work, so a resumable downloader (append to .part, retry with backoff) is easy. Example repo used: pengzhendong/faster-whisper-small.

## Verification

Measured 2.3 MB/s from ModelScope - 461 MB in about two minutes versus 70+ minutes on the mirror; the downloaded directory loads and transcribes correctly, and model.bin is 461.1 MB (full size, not truncated).
