---
title: "LLM cost telemetry undercounting: wrong model label + discarded retries invisible"
domain: llm
tags:
  - "telemetry"
  - "cost-tracking"
  - "openrouter"
  - "retry"
  - "streaming"
status: published
created: 2026-09-07
updated: 2026-09-07
source: "intake #1635 — model column records requested model instead of served model; discarded retries invisible in telemetry"
evidence_level: E3
summary_plain: "LLM成本遥测少计约一半：模型标签标错+重试/截断的调用不计入成本。"
trigger: "LLM cost telemetry undercounting model label retry discarded"
verify: "fake server测试：fallback模型→trace标served model；retry→两行trace+成本求和；stream截断→partial usage记录"
provenance:
  issue: "#1635"
  contributor: "Ikalus1988"
---

## Problem

LLM cost telemetry undercounts by approximately 2× due to two independent bugs:

1. **Wrong model label**: The trace's `model` column records the *requested* model, not the model the provider actually served. When OpenRouter's `models` fallback chain activates (e.g., requested `gpt-4` → served `claude-3-opus`), the cost metric is labeled with the wrong model.

2. **Discarded retries invisible**: Attempts that trigger retry (finish_reason=length, degeneration, mid-stream cutoff) return an error *before* the point where tokens/cost are recorded. The provider charges for both attempts, but only the second (successful) attempt appears in telemetry.

The net effect: cost metrics show roughly half the actual spend, with no runtime errors — a silent telemetry failure.

## Root Cause

### Model label mismatch

The Go client reads `ChatResult.Model` / `ChatStreamChunk.Model` from the SDK response, but the code never actually reads these fields. It uses the *requested* model name for the trace column and cost label. When the provider serves a different model from a fallback list, the label is wrong.

The fix is to add a separate `model_served` field and use it for cost metrics when it differs from the requested model.

### Cost recorded after error discard

The telemetry path records tokens/cost *after* the retry decision point. When a retry is triggered:

```
attempt 1: call → finish_reason=length → RETRY (error returned before cost recorded)
attempt 2: call → finish_reason=stop → cost recorded (only this attempt)
```

The provider charges for both attempts, but only attempt 2 appears in telemetry. The discarded attempt's tokens are lost.

Similarly for stream cutoff: the stream error handler returns before reaching the cost recording code.

### Condition bug: `callErr != nil` zeros cost

The existing code had `if callErr != nil { cost = 0 }`, which zeros the cost line even when `usage != nil` (meaning the provider DID charge). The correct condition is `callErr != nil && usage == nil` — only zero when there's truly no usage data.

## Solution

### 1. Separate `model_served` field

```go
// Before: only requested model
trace.Model = requestedModel
costLabel := requestedModel

// After: track served model separately
trace.Model = requestedModel
trace.ModelServed = result.Model  // from SDK response
if trace.ModelServed != "" && trace.ModelServed != requestedModel {
    costLabel = trace.ModelServed
}
```

### 2. Record cost at every discard point

Create a single helper that records both the cost metric and trace line with available usage and finish_reason. Call it at ALL discard points:

- Retry by finish_reason=length
- Retry by degeneration
- Final error
- Empty stream
- Partial stream cutoff

```go
func recordAttempt(usage *Usage, finishReason string, err error) {
    if usage != nil {
        metrics.RecordLLMCost(model, usage.TotalTokens, usage.Cost)
        trace.Log(tokens=usage.TotalTokens, cost=usage.Cost, status=finishReason)
    }
}
```

### 3. Per-attempt dedup flag

Add a flag per attempt so the external error handler doesn't write a second zeroed cost line for the same attempt.

### 4. Fix the zeroing condition

```go
// Before (wrong): zeros cost even when provider charged
if callErr != nil { cost = 0 }

// After (correct): only zero when no usage data
if callErr != nil && usage == nil { cost = 0 }
```

## Verification

Deterministic tests with a fake HTTP server:

1. **Fallback model**: Server responds with `"model": "other-model"` → trace records served model in separate field, cost metric labeled with served model.

2. **Retry by length**: First attempt `finish_reason=length`, second attempt `finish_reason=stop` → TWO trace lines (discarded one with its tokens/status `error`), cost metric = sum of both.

3. **Stream cutoff**: Stream cuts mid-way with partial usage → trace records partial tokens/cost, exactly ONE line per attempt.

```bash
# Run tests
go test ./internal/telemetry/ -v -run TestCostTracking
```
