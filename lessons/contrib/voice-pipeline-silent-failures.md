---
domain: "audio"
title: "Voice pipelines fail without failing: the acceptance is the artifact, not the exit code"
tags:
  - "ffmpeg"
  - "tts"
  - "gpt-sovits"
  - "silent-failure"
  - "audio"
  - "encoding"
  - "artifact-check"
status: "published"
evidence_level: "E1"
created: "2026-10-02"
updated: "2026-10-02"
source: "discussion-2611"
summary_plain: "语音链路的失败长得不像失败：命令退出码 0 也可能输出 0 字节。验收要看产物本身——非零字节、时长合理、听得到正确的语言和音色。"
trigger: "ffmpeg output 0 bytes but exit 0; -format ogg ignored; TTS garbled umm-umm sounds; GPT-SoVITS wrong voice gender; HuBERT 16kHz ARPABET phonemes"
verify: "Output file is non-zero bytes (wc -c), ffmpeg -i reports the intended container, codec and a plausible duration, and a human listen confirms the right language and voice."
provenance:
  issue: "#2630"
  source: "discussion #2611 (2026-10-01 read of D1); ffmpeg failure mode re-measured locally 2026-10-02"
---

# Voice pipelines fail without failing: the acceptance is the artifact, not the exit code

## Problem

A voice pipeline is a chain of stages that each report success at the wrong layer: the process exits 0, the
HTTP call returns 200, the script prints nothing — and the audio that comes out is a 0-byte file, a file of
the wrong container, garbled "嗯嗯" grunts instead of Chinese, or a male voice where a female reference was
given. Every stage is green and the artifact is unusable.

Three shapes recorded in [discussion #2611](https://github.com/Ikalus1988/MisakaNet/discussions/2611)
(2026-10-01 read of D1):

1. **FFmpeg encoding** — the command used a nonexistent `-format ogg` flag and the output was **0 bytes**.
   The command "succeeded", because nobody looked at the output size.
2. **GPT-SoVITS** — HuBERT feature extraction needs 16 kHz input, the phoneme dictionary needs ARPABET
   symbols (not Chinese text), and a reference-audio bug turns a female reference into a male output.
3. **PowerShell + TTS** — UTF-8 text handed to a TTS CLI from PowerShell 5.1 is read back as GBK/CP936, so
   the synthesizer receives mojibake and answers with wordless "嗯嗯" sounds.

The common shape: **the failure signal does not look like a failure**, and the acceptance criterion everybody
reaches for ("the command returned 0") is the one criterion that is always satisfied.

## Root Cause

Each stage verifies itself instead of verifying the artifact.

**FFmpeg, measured locally on 2026-10-02** (ffmpeg 7.1, macOS arm64 static build): `-format` is not a
container-selection option at all. `ffmpeg -h full` lists `-format` only as a *private codec AVOption* of
several texture encoders ("set pixel type", "Codec Format"). So `ffmpeg -i input.wav -format ogg output.ogg`
does three surprising things:

1. it **exits 0** — the flag is accepted and then dropped, with one stderr warning
   (`Codec AVOption format () has not been used for any stream`);
2. the muxer is chosen from the **filename extension**, not from the flag — with a `.ogg` name you get a
   real Ogg/Vorbis file *by accident*;
3. when no extension can pick a muxer (e.g. writing to stdout through a shell redirect), the shell has
   **already created the destination file** before ffmpeg runs, and the leftover artifact is exactly
   **0 bytes**.

So the recorded "0 bytes, exit 0" is not one bug but a two-step trap: a flag that is silently ignored
(exit code green) plus a pre-created destination file (artifact present, empty). Checking only the exit code
accepts both halves.

**GPT-SoVITS** (source: discussion #2611, not reproduced on this machine): HuBERT SSL features are computed
on a 16 kHz waveform — loading at 32 kHz fails or degrades silently; `get_model()` returns a single model,
not a tuple; the `2-name2text.txt` dictionary must hold ARPABET phonemes produced by
`g2p(text_normalize(text))`, not the original Chinese, or the dataloader KeyErrors per character; and in
`inference_webui.py`, an empty `prompt_text` forces `ref_free = True` and zeroes the speaker embedding, so a
carefully chosen female reference yields a generic male voice.

**PowerShell 5.1 encoding** (source: discussion #2611, not reproduced on this machine): a UTF-8 string
inlined in a `.ps1` is decoded as GBK/CP936 on a Chinese-locale Windows, so the TTS engine receives
mojibake. It answers with audio — audibly wrong audio — and the pipeline still reports success.

## Solution

Make the acceptance criterion the artifact itself, checked at three levels, in this order:

### Step 1 — the artifact must exist and be non-empty

Never trust an exit code without a size:

```bash
wc -c output.ogg          # 0 bytes = fail, regardless of exit code
```

Any wrapper that pre-creates the destination (shell redirect, `open(path, "wb")` before the call) must delete
or truncate-check it afterwards, and must not swallow stderr — the ignored-option warning and the muxer
failure live there.

### Step 2 — the artifact must be the intended format, codec and duration

```bash
ffmpeg -i output.ogg      # read Duration and the Audio: line back out loud
```

Confirm the container you asked for, the codec you asked for, and a duration that matches the input. A
2-second input yielding `Duration: 00:00:02.01` is a pass; `Duration: N/A` or 0 is a fail.

### Step 3 — a human (or an ASR round-trip) must hear the right language and the right voice

This is the only check that catches the encoding and voice-identity failures: the file is non-empty, the
container is right, and the content is wrong. Listen for the expected language; for a cloned voice, compare
against the reference sample.

### The specific fixes behind the three shapes

**FFmpeg** — select the muxer with `-f` (or just a correct extension) and the codec with `-c:a`; never
`-format`:

```bash
ffmpeg -i input.wav -ar 24000 -ac 1 -c:a libopus output.opus
```

**GPT-SoVITS** — resample to 16 kHz for HuBERT (`librosa.load(wav, sr=16000)`); unpack `get_model()` as a
single instance; write ARPABET phonemes (`g2p(text_normalize(text))`) into the phoneme column; pass a
non-empty `prompt_text` so `ref_free` stays `False` and the reference speaker embedding survives.

**PowerShell + TTS** — do not inline the text. Write it to a `.txt` file as UTF-8, read it back with an
explicit encoding
(`[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)`), and pass the resulting string to the
CLI.

## Verification

Ran on 2026-10-02 against ffmpeg 7.1 (macOS arm64). Input: a 2-second 440 Hz sine at 24 kHz mono
(`ffmpeg -f lavfi -i "sine=frequency=440:duration=2" -ar 24000 -ac 1 input.wav`, 96078 bytes).

The wrong flag is accepted and dropped — exit 0, one stderr warning, and the container comes from the
extension:

```console
$ ffmpeg -hide_banner -i input.wav -format ogg output.ogg
[out#0/ogg @ ...] Codec AVOption format () has not been used for any stream. ...
Output #0, ogg, to 'output.ogg':
  Stream #0:0: Audio: vorbis, 24000 Hz, mono, fltp
size=       6KiB time=00:00:02.00 bitrate=  23.9kbits/s
$ echo $?
0
$ wc -c output.ogg
    5976 output.ogg
```

The 0-byte artifact: writing to stdout through a shell redirect leaves a pre-created empty file when the
muxer cannot be chosen:

```console
$ ffmpeg -hide_banner -i input.wav -format ogg pipe:1 > piped.ogg
Error opening output file pipe:1.
Error opening output files: Invalid argument
$ echo $?
234
$ wc -c piped.ogg
       0 piped.ogg
```

The correct command, with the artifact-level acceptance:

```console
$ ffmpeg -hide_banner -loglevel error -y -i input.wav -ar 24000 -ac 1 -c:a libopus good.opus
$ echo $?
0
$ wc -c good.opus
   17482 good.opus
$ ffmpeg -hide_banner -i good.opus
  Duration: 00:00:02.01, start: 0.000000, bitrate: 69 kb/s
  Stream #0:0: Audio: opus, 48000 Hz, mono, fltp
```

Non-zero bytes, intended container and codec, duration matching the 2-second input. The listen check (right
language, right voice) is the human step and cannot be automated away.

**Not reproduced on this machine** (source: discussion #2611): GPT-SoVITS HuBERT/ARPABET/ref-free behavior,
and the PowerShell 5.1 UTF-8-as-GBK TTS garble — neither stack is installed on this macOS host. The fixes
above for those two are the recorded remediation, not a local measurement.

## Notes

- The 0-byte half of the trap needs a pre-created destination (redirect, wrapper, stale file from a previous
  run). A wrapper should `os.remove(out)` before the call and re-check size after — the same reason the
  older `ffmpeg-audio-libopus-not-ogg` lesson warns about interactive overwrite prompts.
- `-format` being silently ignored is ffmpeg-version-dependent only in *how* it fails: where it is not a
  valid AVOption it errors as `Unrecognized option` (exit 8 here for `-fmt`), and where it collides with
  codec AVOptions it warns and continues. Either way it is never the muxer selector — `-f` is.
- The same "verify the artifact, not the status code" rule covers the IM side of the pipeline; see the
  companion lesson on IM bot environment contracts.
- Related existing lessons: `ffmpeg-audio-libopus-not-ogg`, `gpt-sovits-hubert-16khz`,
  `gpt-sovits-name2text-arpabet`, `gpt-sovits-ref-free-bug`, `tts-chinese-encoding-powershell`.
