---
title: "Node.js built-in zstd decompression silently returns only the first frame"
domain: "nodejs"
tags:
  - "nodejs"
  - "zstd"
  - "compression"
  - "session-log"
  - "silent-truncation"
  - "dsh"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "多帧 zstd 文件用 Node 内置解压只出第一帧、还不报错，得自己扫帧边界逐帧解。"
trigger: "zstdDecompressSync returns only first frame multi-frame zstd file createZstdDecompress no error"
verify: "扫描出的帧数与文中 28 B5 2F FD 魔数出现次数相等（本例 1461），且逐帧解出的记录数 14438 而非每文件 1 条"
source: "intake-3266"
provenance:
  issue: "#3266"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Node.js built-in zstd decompression silently returns only the first frame

## Problem

Reading DSH session logs (`session.v4.jsonl.zstd`) with Node's built-in zstd support produced one
record per file instead of the whole log. There was **no error at all** — decompression "succeeded",
it just returned less data than the file contains.

Both APIs behaved the same way:

```js
const zlib = require("zlib");
zlib.zstdDecompressSync(buf);                                 // only frame 1
require("stream").pipeline(fs.createReadStream(p), zlib.createZstdDecompress(), out); // only frame 1
```

Measured numbers from the report: 24 `.zstd` files (~4 MB on disk) yielded **24 records total** —
exactly one `session` header per file — where the plaintext should have been ~60 MB / 14438 JSONL
records. The file itself was intact: the zstd magic `28 B5 2F FD` occurs **1461** times in it, i.e.
it is a concatenation of 1461 frames (frames are appended as the session is written), not a
corrupted one.

## Root Cause

A zstd *frame* is the compression unit; a *file* may hold many frames back to back. Node's
decompressor decodes one frame per call/stream and treats the end of that frame as the end of the
input, so every byte after the first frame is dropped.

It stays silent because, from the decoder's point of view, frame 1 decompressed **completely and
correctly** — a valid success. Truncation at a frame boundary is therefore not detectable as an
error: the only signal is a suspiciously small output (here: one record per file).

The misdiagnosis path matters as much as the bug. The first instinct was "the log file is
corrupt", which is refuted cheaply by counting frame magics in the raw bytes — 1461 occurrences
means many frames, not damage.

## Solution

Do not decompress the file as one stream. Scan the frame boundaries yourself and call the
decompressor once per frame.

### Frame walk

1. A frame starts with the 4 magic bytes `28 B5 2F FD`.
2. Read the 1-byte **Frame_Header_Descriptor**:

   | Field | Bits | Use |
   |---|---|---|
   | `Frame_Content_Size_flag` | 6-7 | size of the content-size field that follows (0/1/2/3 → 0/2/4/8 bytes) |
   | `Single_Segment_flag` | 5 | if 0, one **Window_Descriptor** byte follows the descriptor |
   | `Checksum_flag` | 2 | if 1, a 4-byte checksum trails the last block |
   | `Dictionary_ID_flag` | 0-1 | 0/1/2/3 → 0/1/2/4 byte dictionary id |

3. Skip the optional `Window_Descriptor`, dictionary id and content-size bytes; the payload now
   begins at a **block header**: 3 bytes, little-endian —
   `Last_Block` (bit 0), `Block_Type` (bits 1-2), `Block_Size` (bits 3-23).
   Payload length is `Block_Size`, except `Block_Type == 1` (RLE), whose payload is **1 byte**
   regardless of `Block_Size`.
4. Repeat block headers until `Last_Block` is set, then skip 4 bytes if `Checksum_flag` was set.
   That offset ends the frame.
5. `zlib.zstdDecompressSync(buf.subarray(start, end))` on `[start, end)`; continue at `end`.

A reference implementation of exactly this scan exists in DSH itself, as `scanZstdFrames` in
`<dsh-app>/resources/app.asar` under `dsh-session-persistence-jsonl/zstd`.

```text
while (pos < buf.length):
    assert buf[pos..pos+4] == 28 B5 2F FD
    start = pos
    pos = walk_header_and_blocks(buf, pos)   # steps 2-4
    out.push(zstdDecompressSync(buf.subarray(start, pos)))
```

Note the two easy-to-miss cases: the RLE block payload is 1 byte, not `Block_Size`; and the
checksum cannot be skipped based on a guess — it is only present when the descriptor says so.

## Verification

- 1461 frames scanned, **0 bad frames**; total plaintext ~60 MB / **14438** JSONL records.
- Cross-check: the scanned frame count equals the number of `28 B5 2F FD` magic occurrences in the
  raw file (both 1461). If these two disagree, the walk is wrong.
- Content sanity: record-type distribution is plausible —
  `tool/call` 2214, `assistant/message` 1709, `step/start` 1709.

## Notes

- The fix is a workaround for the *single-frame* behaviour observed with `zstdDecompressSync` and
  `createZstdDecompress`; the Node version is not stated in the report, so confirm on your own
  runtime before assuming the whole multi-frame case is unsupported there.
- The same silent-truncation shape applies to any "one frame is a valid input" decoder: `.gz`
  concatenation, `.xz` streams, and single-shot archive readers. Whenever a decoder returns fewer
  rows than the file should contain, check whether the container holds more than one stream before
  blaming corruption.
- The reporter did not state the exact Node version, the decode time, or memory use; those need
  reproduction if they matter for your case.
