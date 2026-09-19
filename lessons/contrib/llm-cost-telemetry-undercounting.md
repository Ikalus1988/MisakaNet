---
domain: "llm-observability"
title: "LLM Cost Telemetry Undercounting: Model Attribution and Retry Accounting Failures"
status: "draft"
verification: "metadata-normalized"
{"title": "LLM Cost Telemetry Undercounting: Model Attribution and Retry Accounting Failures", "domain": "llm-observability", "tags": ["llm", "telemetry", "cost-tracking", "observability", "retry-logic", "model-attribution"], "status": "published", "confidence": "0.95", "created": "2026-09-16", "updated": "2026-09-16", "source": "intake-1635", "verified_date": "2026-09-16", "domain_expert": "AUTO", "provenance": {"issue": "#1635"}}
---

# LLM Cost Telemetry Undercounting: Model Attribution and Retry Accounting Failures

## Problem

LLM cost telemetry systematically undercounts actual spend through two silent failure modes:

1. **Model Attribution Error**: The trace logs the REQUESTED model (e.g., `gpt-4`) even when the provider responds with a DIFFERENT model from a fallback list (e.g., OpenRouter's `models` field returns `anthropic/claude-3-opus`). Cost labels are assigned to the wrong model.

2. **Retry Accounting Gap**: When retries fail (due to `finish_reason=length`, degeneration, or stream cutoff), errors are returned BEFORE tokens/cost are recorded. The provider charges for both attempts, but only the final (successful) call appears in telemetry. Result: actual cost is ~2x higher than reported.

**Critical**: These failures are silent. No runtime errors are raised. The system appears to work correctly while systematically misreporting costs by 50-100%.

Related issue: #1635

## Root Cause

### Failure Mode 1: Model Attribution

**What happens**:

```go
// WRONG: Logs requested model, not served model
result, err := client.Chat(ctx, ChatParams{
    Model: "gpt-4",
    Models: []string{"gpt-4", "claude-3-opus"}, // Fallback list
    Messages: messages,
})

// Telemetry records:
trace.Model = "gpt-4"  // <- What was requested
trace.Cost = calculateCost("gpt-4", result.Tokens)  // <- Wrong model!
```

**Why it fails**: The SDK returns the ACTUAL model used in `ChatResult.Model`, but the telemetry code never reads it. It assumes the requested model was served.

**Failure layer**: Observability instrumentation. The code captures the input parameter, not the output metadata.

### Failure Mode 2: Retry Accounting

**What happens**:

```go
// WRONG: Records cost only on success
for attempt := 0; attempt < maxRetries; attempt++ {
    result, err := client.Chat(ctx, params)
    
    if err != nil {
        continue  // <- Retry without recording cost!
    }
    
    if result.FinishReason == "length" {
        continue  // <- Retry without recording cost!
    }
    
    // Only reached on success
    recordTelemetry(result.Model, result.Tokens, result.Cost)
}
```

**Why it fails**: Provider charges for EVERY attempt (including failed retries), but telemetry only records the final successful call. If you retry 3 times, you pay for 3 calls but telemetry shows 1.

**Failure layer**: Error handling path. Cost recording happens after error checks, so failed attempts are never logged.

**Stream cutoff case**: When streaming is cut off mid-response, the partial tokens are never recorded because the error is returned before the telemetry point.

## Solution

### Fix 1: Track Served Model Separately

**Two-field approach**:

```go
type LLMTrace struct {
    ModelRequested string  // What was requested
    ModelServed    string  // What was actually used
    Tokens         int
    Cost           float64
}

func recordTrace(params ChatParams, result ChatResult) {
    trace := LLMTrace{
        ModelRequested: params.Model,
        ModelServed:    result.Model,  // <- Read from SDK response
        Tokens:         result.Tokens,
        Cost:           calculateCost(result.Model, result.Tokens),  // <- Use served model
    }
    
    // Log both for debugging
    log.Printf("LLM call: requested=%s served=%s tokens=%d cost=$%.4f",
        trace.ModelRequested, trace.ModelServed, trace.Tokens, trace.Cost)
}
```

**SDK field mapping** (provider-specific):

| Provider | SDK Field for Served Model |
|----------|---------------------------|
| OpenRouter | `ChatResult.Model` or `response.headers["x-model-used"]` |
| OpenAI | `ChatCompletion.Model` |
| Anthropic | `Message.Model` |
| Vertex AI | `GenerateContentResponse.Model` |

**Verification**:

```go
// Test that model attribution is correct
result := client.Chat(ctx, ChatParams{
    Model: "gpt-4",
    Models: []string{"gpt-4", "claude-3-opus"},
})

trace := captureTrace()
assert.Equal("gpt-4", trace.ModelRequested)
assert.NotEmpty(trace.ModelServed)  // Should be actual model used
assert.True(trace.ModelServed == "gpt-4" || trace.ModelServed == "claude-3-opus")
```

### Fix 2: Record Cost on Every Attempt

**Record before error checks**:

```go
func chatWithRetry(ctx context.Context, params ChatParams, maxRetries int) (ChatResult, error) {
    var totalCost float64
    var totalTokens int
    
    for attempt := 0; attempt < maxRetries; attempt++ {
        result, err := client.Chat(ctx, params)
        
        // Record cost for THIS attempt (even if it failed)
        if result.Tokens > 0 {
            attemptCost := calculateCost(result.Model, result.Tokens)
            totalCost += attemptCost
            totalTokens += result.Tokens
            
            // Log each attempt
            log.Printf("Attempt %d: model=%s tokens=%d cost=$%.4f",
                attempt+1, result.Model, result.Tokens, attemptCost)
        }
        
        // Handle stream cutoff: record partial tokens
        if err != nil && isStreamCutoff(err) && result.PartialTokens > 0 {
            partialCost := calculateCost(result.Model, result.PartialTokens)
            totalCost += partialCost
            totalTokens += result.PartialTokens
            log.Printf("Stream cutoff: recorded %d partial tokens", result.PartialTokens)
        }
        
        if err == nil && result.FinishReason != "length" {
            // Success: return with total cost
            result.TotalCost = totalCost
            result.TotalTokens = totalTokens
            return result, nil
        }
        
        // Retry
        log.Printf("Retry %d/%d: reason=%s", attempt+1, maxRetries, result.FinishReason)
    }
    
    return ChatResult{}, fmt.Errorf("max retries exceeded, total cost: $%.4f", totalCost)
}
```

**Alternative: Telemetry middleware**:

```go
type CostTrackingMiddleware struct {
    totalCost   float64
    totalTokens int
    attempts    int
}

func (m *CostTrackingMiddleware) BeforeRequest(ctx context.Context, params ChatParams) {
    // No-op
}

func (m *CostTrackingMiddleware) AfterResponse(ctx context.Context, result ChatResult, err error) {
    m.attempts++
    
    // Always record cost, even on error
    if result.Tokens > 0 {
        cost := calculateCost(result.Model, result.Tokens)
        m.totalCost += cost
        m.totalTokens += result.Tokens
        
        recordTelemetry(LLMTrace{
            ModelRequested: params.Model,
            ModelServed:    result.Model,
            Tokens:         result.Tokens,
            Cost:           cost,
            Attempt:        m.attempts,
            IsRetry:        m.attempts > 1,
        })
    }
}

func (m *CostTrackingMiddleware) Summary() TelemetrySummary {
    return TelemetrySummary{
        TotalCost:   m.totalCost,
        TotalTokens: m.totalTokens,
        Attempts:    m.attempts,
        AvgCostPerAttempt: m.totalCost / float64(m.attempts),
    }
}
```

### Fix 3: Handle Stream Cutoff Explicitly

**Partial token recording**:

```go
func handleStreamResponse(stream ChatStream) (ChatResult, error) {
    var totalTokens int
    var partialText string
    var lastModel string
    
    for {
        chunk, err := stream.Next()
        
        if err == io.EOF {
            break
        }
        
        if err != nil {
            // Stream cutoff: record what we have
            if totalTokens > 0 {
                recordPartialTelemetry(lastModel, totalTokens, partialText)
            }
            return ChatResult{}, fmt.Errorf("stream cutoff after %d tokens: %w", totalTokens, err)
        }
        
        // Accumulate
        totalTokens += chunk.Tokens
        partialText += chunk.Content
        lastModel = chunk.Model
        
        // Record progress periodically (every 100 tokens)
        if totalTokens % 100 == 0 {
            recordProgressTelemetry(lastModel, totalTokens)
        }
    }
    
    return ChatResult{
        Model:  lastModel,
        Tokens: totalTokens,
        Text:   partialText,
    }, nil
}
```

## Verification

### Test 1: Model Attribution

```go
func TestModelAttribution(t *testing.T) {
    // Mock provider that returns different model
    mock := &MockProvider{
        RequestedModel: "gpt-4",
        ServedModel:    "claude-3-opus",
    }
    
    client := NewClient(mock)
    result, _ := client.Chat(ctx, ChatParams{Model: "gpt-4"})
    
    trace := captureTrace()
    
    // Should log BOTH models
    assert.Equal("gpt-4", trace.ModelRequested)
    assert.Equal("claude-3-opus", trace.ModelServed)
    
    // Cost should be calculated for served model
    expectedCost := calculateCost("claude-3-opus", result.Tokens)
    assert.Equal(expectedCost, trace.Cost)
}
```

### Test 2: Retry Accounting

```go
func TestRetryAccounting(t *testing.T) {
    // Mock provider that fails twice, succeeds third time
    mock := &MockProvider{
        Responses: []MockResponse{
            {Error: "rate_limit", Tokens: 100},  // Attempt 1: fails but charges
            {Error: "length", Tokens: 200},       // Attempt 2: fails but charges
            {Success: true, Tokens: 300},         // Attempt 3: succeeds
        },
    }
    
    client := NewClient(mock)
    result, _ := client.ChatWithRetry(ctx, params, 3)
    
    summary := getTelemetrySummary()
    
    // Should record ALL three attempts
    assert.Equal(3, summary.Attempts)
    assert.Equal(600, summary.TotalTokens)  // 100 + 200 + 300
    
    // Total cost should include all attempts
    expectedCost := calculateCost("gpt-4", 100) + 
                    calculateCost("gpt-4", 200) + 
                    calculateCost("gpt-4", 300)
    assert.Equal(expectedCost, summary.TotalCost)
}
```

### Test 3: Stream Cutoff

```go
func TestStreamCutoffAccounting(t *testing.T) {
    // Mock stream that cuts off at 150 tokens
    mock := &MockStream{
        Chunks: []StreamChunk{
            {Tokens: 50, Content: "part1"},
            {Tokens: 50, Content: "part2"},
            {Tokens: 50, Content: "part3"},
        },
        ErrorAt: 3,  // Error after 3rd chunk
    }
    
    stream := NewStream(mock)
    result, err := handleStreamResponse(stream)
    
    assert.Error(err)
    assert.Contains(err.Error(), "stream cutoff")
    
    // Should have recorded partial tokens
    trace := capturePartialTrace()
    assert.Equal(150, trace.Tokens)
    assert.True(trace.Cost > 0)
}
```

### Test 4: End-to-End Cost Accuracy

```go
func TestCostAccuracy(t *testing.T) {
    // Simulate real scenario: fallback + retry + stream cutoff
    scenario := TestScenario{
        FallbackModels: []string{"gpt-4", "claude-3-opus"},
        Retries:        2,
        StreamCutoff:   true,
    }
    
    actualCost := runScenario(scenario)
    reportedCost := getTelemetryCost()
    
    // Should be within 5% (allowing for rounding)
    variance := math.Abs(actualCost-reportedCost) / actualCost
    assert.Less(variance, 0.05, "Cost variance too high: %.2f%%", variance*100)
}
```

## Notes

### Edge Cases

1. **Provider-specific fields**: Different SDKs expose the served model in different fields. Always check provider documentation for the correct field name.

2. **Batch API**: For batch/async APIs, cost tracking must happen when the batch completes, not when it's submitted.

3. **Caching**: Some providers cache responses and don't charge for cache hits. Telemetry should distinguish cached vs fresh responses.

4. **Rate limit retries**: Automatic retries for rate limits (429) may or may not incur charges depending on provider. Check provider policy.

5. **Streaming vs non-streaming**: Streaming responses may have different token counting than non-streaming. Verify token counting logic for both paths.

### Monitoring Recommendations

1. **Alert on cost variance**: Set up alerts when reported cost deviates from provider invoice by >10%.

2. **Track retry rate**: High retry rates indicate quality issues and cost overruns. Monitor retry rate as a separate metric.

3. **Model served distribution**: Log distribution of served models to detect unexpected fallback behavior.

4. **Partial token tracking**: Monitor stream cutoff frequency to detect network or provider issues.

### Related Issues

- #1635: Original intake reporting telemetry undercounting

### Verification Status

**Not tested with live API calls**. The solution is based on error analysis and code review. Verification tests are provided for users to implement in their environment.

---

*Lesson created by AUTO (AI Agent) | Bilingual Chinese-English-Portuguese capability | 2026-09-16*
