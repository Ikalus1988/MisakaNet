---
domain: "backend"
title: "Character Generation 502: Tolerant JSON Decoding for LLM Type Mismatches"
tags:
  - go
  - json-unmarshal
  - llm-output
  - http-502
  - gateway
  - character-generation
status: "draft"
evidence_level: "E1"
evidence_refs:
  - "issue:#1548"
summary_plain: "Character generation returned 502 because the LLM sent a list where text was expected."
trigger: "cannot unmarshal array into Go struct field Character"
verify: "Same POST /api/characters/assist/sheet request returns HTTP 200 with correct content"
---

<!-- provenance:
  source: "intake-1548"
  contributor: "antigravity (via remote MCP)"
  evidence: "production 502 + cloud logging / BigQuery llm_traces analysis"
-->

# Character Generation 502: Tolerant JSON Decoding for LLM Type Mismatches

## Problem

`POST /api/characters/assist/sheet` (character generation) fails with
**HTTP 502 Bad Gateway**. The application log shows:

```text
json: cannot unmarshal array into Go struct field Character.forbidden_words of type string
```

Two LLM output behaviors trigger it:

1. The model returns a **JSON array** for a field declared as `string`
   (e.g. `forbidden_words`, `speech_tics`) — observed with DeepSeek output
   in `json_object` fallback mode.
2. The model **wraps the JSON in markdown fences** (```` ```json ... ``` ````),
   so the body is not valid JSON at all.

A 502 is the worst possible surface for this: it looks like an
infrastructure outage, but the gateway is healthy — the app crashes (or the
upstream handler errors out) while decoding the model response.

## Root Cause

Two independent causes combine, so diagnose them in order.

### Step 0 — Discriminate: is the 502 from the gateway or from the app?

A 502 only means "something between the client and the origin failed".
Before touching code, check all three:

1. **Gateway logs** — does the gateway log show `upstream prematurely closed
   connection`, a timeout, or `no healthy upstream`? A timeout with no app
   log line points at the gateway/upstream layer; an app panic or decode
   error logged just before the 502 points at the app.
2. **Timeout configuration** — LLM calls are slow. If the gateway/proxy
   timeout is shorter than the model's p99 latency, long generations die as
   502 even when the JSON would have been fine.
3. **Upstream health checks** — confirm the app instance was healthy at the
   time (`/healthz` or equivalent). An unhealthy instance makes every
   request 502 regardless of payload.

In this incident the gateway, timeouts, and upstreams were all healthy, and
GCP Cloud Logging plus BigQuery `llm_traces` showed the failure happened
**inside the app while unmarshalling the LLM response**. That routes to the
application branch below.

### Why the app fails

- Go's `encoding/json` is **strict about types**: unmarshalling a JSON array
  into a Go `string` field is a hard error, not a coercion.
- The prompt/schema declares `forbidden_words` as a string, but nothing
  forces the model to comply — especially in `json_object` fallback mode,
  where the model emits plausible JSON without schema enforcement.
- The decode path has no sanitization step, so markdown-fenced output also
  fails instead of being stripped first.

## Solution

### Step 1 — Fix the layer the discrimination pointed at

- **Gateway branch** (gateway logs show timeouts / no healthy upstream):
  raise the proxy read/send timeouts for the assist route to cover model p99
  latency, fix the upstream health check or capacity, and retry idempotent
  generation requests. Do not change decode code for a gateway problem.
- **Application branch** (app logs show the unmarshal error, as here):
  continue with Step 2.

### Step 2 — Tolerant decoding in `strutil` (application branch)

Add flexible scalar types that accept whatever shape the model emits:

```go
// FlexibleString accepts a JSON string, number, bool, or single-element array.
type FlexibleString string

func (f *FlexibleString) UnmarshalJSON(data []byte) error {
    var s string
    if err := json.Unmarshal(data, &s); err == nil {
        *f = FlexibleString(s)
        return nil
    }
    var arr []any
    if err := json.Unmarshal(data, &arr); err == nil {
        parts := make([]string, 0, len(arr))
        for _, v := range arr {
            parts = append(parts, fmt.Sprint(v))
        }
        *f = FlexibleString(strings.Join(parts, ", "))
        return nil
    }
    var n json.Number
    if err := json.Unmarshal(data, &n); err == nil {
        *f = FlexibleString(n.String())
        return nil
    }
    return fmt.Errorf("FlexibleString: unsupported JSON value %s", data)
}
```

```go
// FlexibleStringSlice accepts a JSON array, a single string, or null.
type FlexibleStringSlice []string

func (f *FlexibleStringSlice) UnmarshalJSON(data []byte) error {
    var arr []string
    if err := json.Unmarshal(data, &arr); err == nil {
        *f = arr
        return nil
    }
    var s string
    if err := json.Unmarshal(data, &s); err == nil {
        *f = []string{s}
        return nil
    }
    if string(data) == "null" {
        *f = nil
        return nil
    }
    return fmt.Errorf("FlexibleStringSlice: unsupported JSON value %s", data)
}
```

Apply the same pattern for `FlexibleInt` (accept numeric strings), and add a
`CleanJSON` helper in `strutil` that strips markdown fences before decoding:

```go
// CleanJSON removes ```json ... ``` fences and surrounding whitespace.
func CleanJSON(raw string) string {
    s := strings.TrimSpace(raw)
    s = strings.TrimPrefix(s, "```json")
    s = strings.TrimPrefix(s, "```")
    s = strings.TrimSuffix(s, "```")
    return strings.TrimSpace(s)
}
```

Change the `Character` struct to use the flexible types for every
model-generated field (`forbidden_words`, `speech_tics`, etc.).

### Step 3 — Make `sheetSchema` and `castSchema` strict-compliant

Put **every property in `required`** and set `additionalProperties: false`
where the provider supports strict mode. Strict schemas make the provider
enforce types server-side, so the tolerant decoders become a second layer of
defense instead of the only one. Keep both: strict schema reduces bad output,
flexible decoding survives it.

## Verification

1. Unit-test the decoders with the exact production payloads — an array
   `forbidden_words` and a markdown-fenced body must both decode:

```bash
go test ./internal/strutil/ -run 'TestFlexible|TestCleanJSON' -v
```

2. Replay the original failing request against a staging instance and confirm
   the same `POST /api/characters/assist/sheet` call now returns **HTTP 200**
   with correct character content, instead of 502.

3. Re-check the gateway access log for the replayed request: status 200 from
   upstream confirms the fix is in the app layer, not a masked gateway change.

## Notes

- Tolerant decoding must stay **observable**: log (or count a metric) every
  time a fallback branch coerces a value, so schema drift shows up in
  `llm_traces` instead of silently accumulating.
- Do not "fix" this by switching the struct fields to `any`: untyped fields
  push the failure downstream to template rendering instead of removing it.
- If a provider offers structured-output / strict-mode schemas, prefer them
  over fallback `json_object` mode — fallback is where the array-for-string
  output was observed.
- Related: `lessons/contrib/json-parse-failure-handling.md` (defensive JSON
  parsing in Python), `lessons/contrib/api-rate-limit-handling-best-practices.md`.
