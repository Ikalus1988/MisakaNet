---
title: "The 502 was not the gateway: a Go struct expected a string and the model returned an array"
domain: "go"
tags:
  - "go"
  - "json"
  - "unmarshal"
  - "llm"
  - "structured-output"
  - "json-schema"
  - "http-502"
  - "gateway"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "线上 502 不是网关坏了，是模型把字符串字段返回成数组，Go 按结构体解析时直接失败，整条响应被丢掉。"
trigger: "json: cannot unmarshal array into Go struct field forbidden_words of type string"
verify: "用生产同款请求体（forbidden_words 为数组、JSON 包在 Markdown 围栏里）跑单测并通过同一接口，返回 200 且字段有值。"
source: "intake-1548"
provenance:
  issue: "#1548"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# The 502 was not the gateway: a Go struct expected a string and the model returned an array

## Problem

Character generation at `POST /api/characters/assist/sheet` (an LLM-backed endpoint) failed with
`HTTP 502 Bad Gateway`. A 502 is a status a *gateway* invents: it says an upstream hop broke. So the
default reading is "the gateway, the network, or a timeout" — and that reading is wrong often enough
that it is worth writing down the case where it is.

The reporter's actual error, from the application side:

```
json: cannot unmarshal array into Go struct field Character.forbidden_words of type string
```

The LLM had been asked for a JSON object. For fields declared as `string` — `forbidden_words`,
`speech_tics` — the model returned JSON **arrays**, and in some replies it wrapped the object in
Markdown code fences. `encoding/json` refused the first shape, the handler failed the request, and
the client saw a 502. The endpoint looked like an infrastructure failure and was a type mismatch.

## Root Cause

Three layers, and only the third one appears in the error message.

1. **The 502 was a pass-through of an application error, not a gateway failure.** The reporter traced
   it through GCP cloud logging and the BigQuery `llm_traces` table, and found the failing requests
   paired with model output where `forbidden_words` came back as a string array. That trace is the
   thing that separates the two branches: a gateway-caused 502 has no application-side decode error
   behind it, and an application-caused 502 does.
2. **`json_object` mode constrains the shape, not the types.** The model was running in the
   JSON-object fallback mode. Asked for an object, it emits an object — but a schema *hint* is not
   enforcement: `"forbidden_words": ["gambling", "politics"]` is a perfectly valid JSON value where
   the Go struct declared `string`. The model is not violating the format; the contract never said
   arrays were forbidden. Markdown fences are the same class of drift — the object is correct, the
   envelope around it is not, so the decoder fails on byte 0.
3. **A `string` field plus `json.Unmarshal` is an exact type check, and it is all-or-nothing.** One
   array-valued field aborts the decode of the whole object: every other correct field in that
   response is lost too. The strictness is where the damage is — the model's small deviation becomes
   a total failure.

## Solution

### Step 1 — decide whether the 502 is the gateway or the application

Do this before changing any decode code. The intake names three signals; all three are read-only:

- **Gateway logs** for the failing request: which upstream answered, with what status, and whether
  the gateway itself generated the 502 (its own error page / `upstream_connect_error` style entry) or
  relayed one.
- **Timeout configuration**: did the request exceed the gateway's `proxy_read_timeout` (or equivalent)
  while the LLM was still generating? A timeout-generated 502 has *no* application log line at all.
- **Upstream health check**: was the backend actually registered and healthy at that moment? An
  unhealthy target produces 502s that are constant, not tied to particular payloads.

The reporter's discriminator was the application trace: the application log carried the request and
the `cannot unmarshal` error, and `llm_traces` held the model output that caused it. That is the
application branch. The inverse is just as decisive — **no application log entry for that request
means the request never reached the handler**, so the fix is not in the decode path.

Not supplied: the exact log queries/filters, the gateway product and its config, the timeout values,
and how (or whether) a request ID is propagated from gateway to application — **报料者未给出，需复现确认**.
Also unstated is the mapping from the handler's error response to the 502 the client saw (application
5xx relayed verbatim vs. gateway rewrapping) — that is inferred from the report's causation, not
observed here.

### Step 2A — gateway/upstream branch

Out of scope for this report: the reporter's case was the application branch. What a gateway-branch
fix looks like (raise the timeout for LLM routes, repair the target group, cap generation length so
the request finishes inside the timeout) is **报料者未给出，需复现确认** — do not apply the decode changes
below to a timeout-generated 502; they will not fix it.

### Step 2B — application branch (the fix that shipped)

1. **Make the model-controlled fields tolerant**, in a shared `strutil` package:
   `FlexibleString`, `FlexibleStringSlice`, `FlexibleInt` — each an `UnmarshalJSON` that accepts the
   declared type *and* the shapes the model actually emits, plus `CleanJSON`, which strips Markdown
   fences and leading/trailing prose before decoding. Use these types *only* on fields the model
   controls (`forbidden_words`, `speech_tics`); leave internal structs exact.
2. **Make the schema strict-compliant**: `sheetSchema` and `castSchema` now list **all** properties in
   `required`. In strict structured-output mode every property must be in `required` (with
   `additionalProperties: false`) — optional values are expressed as nullable types, not by omitting
   the key. This is the request-side half: it narrows what the model is allowed to emit.
3. **Keep both halves.** The reporter's point is that neither alone is enough: a strict schema is a
   request, not a guarantee (the failing model was in `json_object` fallback mode, which enforces no
   types), and tolerant decode alone silently accepts garbage forever.

Sketch of the tolerant-string idea (illustrative — the reporter described the approach, not this
code):

```go
// FlexibleString accepts a JSON string, or an array of strings, and folds both into one string.
type FlexibleString string

func (s *FlexibleString) UnmarshalJSON(b []byte) error {
	var one string
	if err := json.Unmarshal(b, &one); err == nil {
		*s = FlexibleString(strings.TrimSpace(one))
		return nil
	}
	var many []string
	if err := json.Unmarshal(b, &many); err == nil {
		*s = FlexibleString(strings.Join(many, "、"))
		return nil
	}
	return fmt.Errorf("FlexibleString: unsupported JSON shape: %s", string(b))
}

// CleanJSON drops a Markdown fence and any prose around the object before decoding.
func CleanJSON(raw []byte) []byte {
	s := strings.TrimSpace(string(raw))
	s = strings.TrimPrefix(s, "```json")
	s = strings.TrimPrefix(s, "```")
	s = strings.TrimSuffix(strings.TrimSpace(s), "```")
	if i, j := strings.Index(s, "{"), strings.LastIndex(s, "}"); i >= 0 && j > i {
		s = s[i : j+1]
	}
	return []byte(s)
}
```

Errors must stay loud for shapes you did not anticipate: the third branch above returns an error
naming the shape rather than silently producing an empty string, so the next drift is visible.

## Verification

Reporter-reported: unit tests using **the exact production payloads** — an object whose
`forbidden_words` is an array, and an object wrapped in Markdown fences — now pass, where the same
payloads failed `json.Unmarshal` before. That is the criterion that matters, because a test built
from a hand-written "correct" payload exercises neither drift.

The intake's acceptance criterion adds the end-to-end half: after the fix, the same request returns
`200` with correct content — the sheet comes back with `forbidden_words`/`speech_tics` populated from
what the model sent (joined, not dropped), instead of 502. Observed signal that this held: the
failing requests stop carrying a decode error in the application log and the corresponding
`llm_traces` row no longer pairs with one.

For a gateway-branch 502 the equivalent check is different and not satisfied by these tests: the
request must complete inside the timeout and the target must be healthy — **报料者未给出该分支的验证记录，需复现确认**.

## Notes

Domain: filed as `go`, because the mechanism a searcher will paste is a Go `encoding/json` error and
`go` is the value the vocabulary has for it. The same lesson is simultaneously an `llm`
(structured-output drift) and `backend`/`api` (502 classification) story; a maintainer may retag.

Scope warning: tolerant decode is not a licence to accept anything. Every flexible type above should
be paired with a log or metric on the "wrong shape" branch, or the drift becomes invisible as the
error rate drops — you fix the 502 and lose the signal that the prompt or schema regressed.

Related lessons: `silent-data-loss-google-cloud.md` covers the other half of the same hazard (a Go
struct that omits a field silently erasing it); `json-schema-boolean-subschema-means-any-value.md`
covers reading a JSON Schema more literally than its author meant.

Not supplied by the reporter: the field list beyond `forbidden_words`/`speech_tics`, the model and
prompt settings, and whether temperature/sampling was changed as part of the fix — **报料者未给出，需复现确认**.
