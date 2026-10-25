---
domain: "frontend"
title: "antd Upload fires onChange once per file per batch, so one drop becomes N business units"
tags:
  - "antd"
  - "upload"
  - "dragger"
  - "onchange"
  - "batch-boundary"
  - "rc-upload"
  - "react"
  - "uid-dedup"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3330"
summary_plain: "一次拖入 N 个文件 antd 会回调 N 次 onChange，不是一次；按一次回调建一个业务单元，就会得到 N 个几乎相同的单元。"
trigger: "antd Upload onChange 一次选择 N 个文件回调 N 次，Dragger 多选/拖入"
verify: "选入含 N 个文件的一批后业务单元数 == 1 且单元内文件数 == N；再选另一批 M 个后单元数为 2，两个单元的文件集合不相交。"
provenance:
  issue: "#3330"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# antd Upload fires onChange once per file per batch, so one drop becomes N business units

## Problem

A React application used antd `Upload` (also `Dragger`) and treated **one `onChange` call as one
business unit** — the intended semantic being "one drop / one multi-select = one backup, one task".
That mapping is wrong: for N files selected or dropped **in one gesture**, antd calls `onChange`
**N times**, not once, and every call carries the **full, accumulated** `fileList` (it accumulates
across batches and is never cleared for you).

Measured by the reporter:

- select **2** files → **2** units, each containing both files;
- select **147** files → **147** units.

So units produced from one gesture are near-identical and mutually containing — each unit includes the
files of all earlier callbacks in the same batch — and the real difference between the user's
submissions is washed out. The reported symptom, verbatim:

```
一次选择 N 个文件产生 N 个业务单元
```

The antd / rc-upload versions in use were **not reported (报料者未给出，需复现确认)**.

## Root Cause

The behaviour is deliberate, and the source says so. Inside antd's `Upload`, `onBatchStart` first adds
the **whole batch** to the list, then repeats the callback per file — the in-source comment is
verbatim:

```
Repeat trigger onChange event for compatible
```

i.e. one `onChange` per file is kept for **backwards compatibility** with consumers that only ever
looked at a single file. The real batch boundary lives in `rc-upload`'s `onBatchStart`, but antd
**does not expose it as a user prop** — it consumes it internally. Application code therefore never
receives a batch-level signal at all; the only batch-correlated thing it can observe is the **set of
file `uid`s created for that gesture**.

Diagnosis path, worth recording because two plausible hypotheses were wrong first:

1. "the synthetic `drop` event didn't fire" — replaced the drop with a native `file input`, symptom
   unchanged, so the event was not the problem;
2. "the component is mounted twice" — ruled out;
3. read the antd `Upload` source, found the comment above, and accepted the per-file callback as
   documented behaviour rather than a bug to work around.

The transferable statement: **a per-item callback is not a batch event, no matter how much it looks
like one when the batch has size 1.** In development, single-file picks make the two indistinguishable.

## Solution

Do not use `onChange` as the batch boundary. Merge by `file.uid`, which is generated **once per file**
in `onBatchStart` and is therefore stable across the N `onChange` calls of that batch:

- keep a `Set` of already-processed `uid`s;
- on every `onChange`, take only the **newly appeared** `uid`s;
- push the new files into a *pending batch*, and coalesce the callbacks of one gesture with
  `setTimeout(0)` — collect everything that arrives in the same tick, then create **one** unit;
- when the business state is cleared/reset, reset the `uid` set **and** the pending batch, or the next
  gesture inherits stale dedup state.

Sketch of the fix the reporter describes (illustrative, not their verbatim code):

```js
const seen = useRef(new Set());
const pending = useRef([]);
const timer = useRef(null);

const onChange = ({ fileList }) => {
  const fresh = fileList.filter((f) => !seen.current.has(f.uid));
  if (fresh.length === 0) return;
  fresh.forEach((f) => seen.current.add(f.uid));

  pending.current.push(...fresh);
  clearTimeout(timer.current);
  timer.current = setTimeout(() => {
    const batch = pending.current;   // everything one gesture produced
    pending.current = [];
    createUnit(batch);               // exactly one business unit per real batch
  }, 0);
};
```

Result with that mapping: one gesture selecting N files → **1** unit; two gestures (with a wait
between them) → **2** units.

## Verification

- Select a batch of N files: **business-unit count == 1** and **files in that unit == N**.
  Assertion shape: `units.length === 1 && units[0].files.length === N`.
- Then select a second batch of M files: **unit count == 2**, and the two units' file sets are
  **disjoint** (neither contains the other's files).
- The earlier "N files → N homogeneous units" phenomenon is gone: no unit contains an earlier batch's
  files, and no two units from the same gesture exist.
- The reporter reports the 2-file and 147-file counts as the failing baseline; the post-fix run
  output and the assertion harness were **not reported (报料者未给出，需复现确认)**.

## Notes

- The two assertions matter together: unit-count-only would pass if you simply debounced everything
  into one ever-growing unit; disjointness is what proves the batch boundary is real.
- `setTimeout(0)` is a heuristic for "same gesture". It is fine for interactive uploads (all callbacks
  of one drop land in the same task queue flush) but it is not a contract — if the batch boundary must
  be exact, read `onBatchStart` from `rc-upload` directly or keep a server-assigned batch id.
- `file.uid` is the only stable per-gesture key antd gives you. Names, sizes and `lastModified` are
  all user data and can repeat across batches, so deduplicating on them will silently merge two
  genuinely different submissions.
- Related shape: any library that calls a "changed" handler per item while you treat it as
  "the collection changed" — table row selection, multi-file pickers, bulk paste handlers. The
  question to ask of every such API is "what is the smallest event that corresponds to one user
  gesture, and is it exposed?"
- Evidence level is E1: reporter-measured counts and the antd source comment, not reproduced in this
  repository.
