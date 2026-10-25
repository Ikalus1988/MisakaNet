---
title: "Node DataView.getUint32 defaults to big-endian, so a little-endian read reports an absurd decompressed size"
domain: "nodejs"
tags:
  - "nodejs"
  - "binary-parsing"
  - "endianness"
  - "dataview"
  - "buffer"
  - "decompression"
  - "bounds-check"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Node 里 DataView.getUint32 不传第三参读的是大端序，按小端读长度字段会得出 1173 万这种荒谬值。"
trigger: "解压后长度字段读出荒谬大值 / bad size / DataView getUint32 默认字节序 / readUInt32LE 与 readUInt32BE 结果不一致"
verify: "同一长度字段分别用 readUInt32LE / readUInt32BE 读，取压缩比落在 [0.2,1.0] 的那个字节序；修正后批量样本全部解压成功且不再出现 bad size。"
source: "intake-2856"
provenance:
  issue: "#2856"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Node DataView.getUint32 defaults to big-endian, so a little-endian read reports an absurd decompressed size

## Problem

Parsing a binary container format in Node, the decompression layer's "size after decompress" field
came back nonsense: a **1653-byte** compressed file claimed it would decompress to
**11,732,736 bytes**. In a batch run, **75 of 144** samples failed outright with `bad size`; the
ones that survived ran but produced wrong offsets downstream — every subsequent field shifted.

The raw bytes look perfectly reasonable by eye:

```text
00 00 0b b3
```

so the corruption is not visible in the data. It is visible only once you ask which end you are
reading from.

## Root Cause

`DataView.prototype.getUint32(offset)` **is big-endian when the third argument is omitted** —
that is, `false` (big-endian) is the default. Most of the rest of Node's ecosystem is
little-endian (`Buffer.readUInt32LE`, `readUInt32LE`, TypedArray views on the host's native
order), so the intuitive assumption "JS is little-endian" is wrong in exactly this one API. The
mistake then appears in one file, side by side:

```js
const size = buf.readUInt32LE(4)   // ← 想当然小端
// 正确：buf.readUInt32BE(4) 或 new DataView(...).getUint32(0)
```

The arithmetic on `00 00 0b b3` makes the gap concrete:

| read as | value | verdict |
|---|---|---|
| little-endian (`0xB30B00`) | 11,732,736 | absurd for a 1653-byte input |
| big-endian (`0x00000BB3`) | 2,995 | consistent with compression ratio ≈ 0.55 |

There is a second, subtler trap in third-party parsers. Two helper functions can look
inconsistent while agreeing perfectly:

```js
u16() { return b[0] * 256 + b[1] }                       // explicit big-endian
u32() { return new DataView(...).getUint32(0) }           // implicit big-endian
```

Copying one and "fixing" it against the other half-convinces you that the code is inconsistent.
It is not: both are big-endian, and the implicit one is the one that bites.

## Solution

### 1. Establish the byte order of the format before writing the parser

Cross-check one known field: a length must be plausible against the file size / compression
ratio, and magic numbers should read as ASCII.

### 2. Use one explicit spelling throughout the parser

Pick one and keep it consistent:

```js
buf.readUInt32BE(offset)                                        // Buffer API
new DataView(b.buffer, b.byteOffset, b.byteLength)
  .getUint32(offset, false)                                     // third arg explicit
```

Never call bare `getUint32(offset)` — the default is the trap.

### 3. Put bounds guards around every cursor advance

Malformed input otherwise walks past the end; the cursor becomes `undefined`, arithmetic turns it
into `NaN`, the loop never advances and the batch job hangs:

```js
if (++guard > declaredSize * 4) throw new Error('解压死循环')
if (p >= buf.length)            throw new Error('流截断')
if (p + 2 > buf.length)         throw new Error('匹配对越界')
```

## Verification

- After the endianness fix: **144/144** real binary samples decompress (before: 67 succeeded,
  75 failed). 报料者给出的这组数字里 67 + 75 = 142，与 144 对不上两个样本的去向 —— 需复现确认；
  修复后的「全部成功」结论不受影响，但失败计数的口径值得再核一次.
- Add the assertion that fails loudly instead of producing wrong data: the length field must be
  `> 0` and `< file size × 100`. With the wrong byte order this trips immediately.
- Remove the guards, feed a truncated file → hangs. Restore the guards → the same file throws
  `流截断` and the batch task does not stall.
- Independently reproducible: take any LZSS / custom container file, print
  `readUInt32LE` and `readUInt32BE` for the length field, and keep the byte order whose
  compression ratio lands in `[0.2, 1.0]`.

## Notes

- The `bad size` judgement was correct — it was the reader that was wrong. A batch failure count
  that splits cleanly in a suspicious ratio (here roughly 1:1 of pass to fail) is a hint to
  suspect the parser rather than the data.
- The same default applies to `getUint16`, `getInt32`, `getFloat64`: omitting `littleEndian`
  means **big**-endian for all of them.
