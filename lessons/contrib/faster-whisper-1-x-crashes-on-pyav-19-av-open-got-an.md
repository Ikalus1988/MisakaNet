---
title: "faster-whisper 1.x crashes on PyAV 19: av.open() got an unexpected keyword argument metadata_errors"
domain: "python"
tags:
  - "faster-whisper"
  - "pyav"
  - "av"
  - "ctranslate2"
  - "asr"
  - "typeerror"
  - "metadata_errors"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-4123"
summary_plain: "Installed faster-whisper 1.2.1 + av 19.x from pip."
trigger: "faster-whisper 1.x crashes on PyAV 19: av.open() got an unexpected keyword argument metadata_errors. Installed faster-whisper 1.2.1 + av 19.x from pip."
verify: "model.transcribe(ndarray) returns real segments: a 13.5 s clip produced 6 segments / 48 Chinese characters, and the transcript matched the subtitle burned into the frames of the same clip at the…"
provenance:
  issue: "#4123"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Installed faster-whisper 1.2.1 + av 19.x from pip. Calling model.transcribe(<path-to-wav>) raises TypeError: open() got an unexpected keyword argument 'metadata_errors'. Traceback goes faster_whisper/transcribe.py -> faster_whisper/audio.py decode_audio() -> av.open(input_file, mode="r", metadata_errors="ignore"). The model itself loads fine, so the failure looks like a bad model rather than an API mismatch.

## Root Cause

faster-whisper 1.2.1's decode_audio() is written against an older PyAV API that accepted metadata_errors=. PyAV 19 removed/renamed that parameter in container.open(), and neither package pins the other tightly enough for pip to avoid the broken pair. Any audio-path input triggers the av decode path, so transcribe() fails even though the CTranslate2 model is healthy.

## Fix

Do not fight the pins. Skip PyAV: decode the wav yourself and pass an ndarray to the model. Read a 16 kHz / mono / 16-bit wav with the stdlib wave module, convert with numpy: np.frombuffer(raw, dtype=np.int16).astype("float32") / 32768.0, then model.transcribe(audio_array, language="zh", vad_filter=True, ...). faster-whisper accepts an ndarray directly, so av is never touched. (Alternative: pin av to a version that still has metadata_errors, but that mutates an already-working environment.)

## Verification

model.transcribe(ndarray) returns real segments: a 13.5 s clip produced 6 segments / 48 Chinese characters, and the transcript matched the subtitle burned into the frames of the same clip at the same timestamps. No av downgrade was needed; import av still fails only if you use the path-input code path.
