---
title: "V100 Strata MoE serving: SM70 decode kernels, CPU prefill share, and IQ3_XXS quant switch"
domain: llm
tags:
  - v100
  - strata
  - moe
  - quantization
  - iq3-xxs
  - sm70
  - prefill
  - ttft
  - decode
status: published
evidence_level: E1
created: '2026-10-29'
summary_plain: "MoE decode on two V100s: an SM70 kernel table, CPU prefill sharing and an IQ3_XXS quant took it from 53.6 to 84.5 tok/s."
trigger: "Strata engine on Volta sm_70 GPUs: decode stuck near 45-60 tok/s, cold TTFT ~10s on 10k-token prompts"
verify: "SSE probe over 1200+ generated tokens: decode mean 84.5 tok/s (was 53.6), 10.5k cold TTFT 8.28s, expert cache hit 94-96%"
provenance:
  issue: "4021"
---

# V100 Strata MoE serving: SM70 decode kernels, CPU prefill share, and IQ3_XXS quant switch

## Problem

Qwen3.8-Flash-Next MoE (48 expert layers) served on 2x V100 32GB via the **Strata** engine:
decode stuck at 45-58 tok/s, cold TTFT ~10s on 10k-token prompts, short prompts ~1.8s.

Generic vLLM / TensorRT-LLM guides do not apply here: Strata is a separate engine, and vLLM supports
Volta (sm_70) poorly. So the usual advice — upgrade kernels, enable paged attention, use the vendor's
tuning guide — has no branch that reaches this deployment.

## Root Cause

Three independent bottlenecks, none of which is visible from a profiler alone:

1. **Default CUDA kernels are not tuned for sm_70 on IQ4_XS MoE decode.** The engine ships a kernel
   table per architecture and falls back to a generic one when the arch is not selected.
2. **Prefill runs GPU-only**, so a long cold prompt pays the full GPU prefill while CPU and RAM sit
   idle — that is where the ~10s cold TTFT comes from.
3. **Serving the 88 GB IQ4_XS when a 71 GB IQ3_XXS of the same model is already on disk.** Decode
   speed is roughly inversely proportional to active expert bytes read per token, so the heavier
   quant caps the ceiling regardless of tuning.

A fourth hypothesis was measured and **rejected**: ECC on/off changed nothing (58.1 vs 58.3 tok/s,
inside noise). The workload is bandwidth-bound, not ECC-bound.

## Solution

All three changes are environment variables in the server config's `env` dict, and all three need a
**full server restart** — the engine reads them once at startup.

### Step 1 — select the sm_70 kernel table

```
STRATA_SM70_TABLE=1
```

Bitwise-identical output; decode **+12.4%**. Because the output does not change, this is the safest of
the three to apply first.

### Step 2 — let the CPU share prefill

```
STRATA_PREFILL_CPU_SHARE=auto
```

The CPU takes the expert shares on chunks under 1024 tokens:

| case | before | after |
|---|---|---|
| short cold TTFT | 1.80s | **1.18s** (-34%) |
| 10.5k cold TTFT | 10.49s | 9.65s |

The last bits differ (KL ≤ 0.026). That is a real, bounded change in output — worth knowing before
enabling it where byte-identical logits matter.

### Step 3 — switch the quant, and mind which packer you use

Pack IQ3_XXS with **`tools/iq_pack.py`** — **not** `strata_pack.py`, which asserts Q2_0 experts and
crashes on IQ2_XS experts:

```
AssertionError: IQ2_XS
```

That failed run leaves a **0-byte `experts.bin`** behind, and the engine prefers it over the GGUF on
later restarts — so the crash comes back as a silent wrong-model load rather than as an error. Delete it.

Low-RAM mode then needs no `experts.bin` at all: the engine maps the GGUF directly through
`native_experts.txt` (engine ≥ 0.1.31).

## Verification

An SSE probe that streams 1200+ generated tokens and measures first-token time and tokens/s, **cold and
warm**:

- decode **53.6 → 84.5 tok/s** mean (warm 91.4; 75-82 under real traffic);
- 10.5k cold TTFT **8.28s**;
- engine log steady state 75-82 tok/s under a real 70-95k-token harness;
- MTP draft acceptance 71-82%; expert cache hit 94-96%.

Confirm the env vars actually reached the process:

```bash
tr '\0' '\n' < /proc/<pid>/environ | grep -a STRATA
```

## When this does not apply

The numbers are from one model on two V100s; a different MoE with a different active-expert count will
land on different constants. The three *mechanisms* (arch kernel table, CPU prefill share, quant size
driving bytes per token) are the transferable part, and the ECC result is the useful negative one:
before tuning ECC, measure whether the workload is actually ECC-bound.
