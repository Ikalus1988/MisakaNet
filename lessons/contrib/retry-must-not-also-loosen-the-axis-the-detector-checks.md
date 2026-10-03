---
title: "A retry must not widen the axis the guardrail measures, and must have a discard terminal state"
domain: roleplay-engine
tags:
  - roleplay
  - guardrail
  - retry-logic
  - sampling-parameters
  - history-contamination
  - fail-closed
  - llm
status: published
created: "2026-10-03"
updated: "2026-10-03"
source: "intake #1679 — language-contaminated replies reached the chat history because the retry raised temperature and never discarded a persistently failing turn"
evidence_level: E0
evidence_refs:
  - 'issue:#1679'
summary_plain: "The retry for a wrong-language reply added randomness, and the bad reply was still saved into the chat history."
trigger: "guardrail retry raises temperature language leak contaminates chat history discard turn"
verify: "With the detector stubbed to always fail, the retry loop ends in a discard and persists nothing; no content-property guardrail raises temperature above the base setting."
provenance:
  source: "intake"
  issue: "#1679"
  contributor: "Ikalus1988"
  node: "Misaka10099"
  evidence: "single-node report; no reproduction script, log excerpt, or before/after count supplied"
---

# A retry must not widen the axis the guardrail measures, and must have a discard terminal state

## Problem

Replies contaminated with a foreign language and foreign-character text reached the chat history. The engine had both defences already: a language guardrail that detected the violation, and a retry loop that re-requested the turn. Neither prevented the leak from being stored.

Once written, a contaminated line is no longer a bad sample. It becomes context — re-read on every subsequent turn, where it is in-context evidence for what language this conversation is conducted in. Contamination that is stored does not decay; it compounds.

The distinguishing feature of this failure is that the guardrail *worked*. It fired. The system knew the reply was bad at the moment it decided to keep it.

## Root Cause

### 1. The retry moved the axis the detector was measuring

On a language violation the guardrail re-requested the turn with the sampling temperature raised (`temperature += 0.3`).

Temperature is the sampling-entropy knob. A language violation is a *drift into a different token distribution* — a precision failure. Raising entropy widens the distribution whose tail the detector is watching, so the recovery step mechanically increased the probability of the very failure it was recovering from.

This is why the bug survives review: the retry usually does pass. It passes by luck, often enough to look like a working recovery path. Nobody examines the coupling because the symptom is intermittent, and intermittent success reads as "the retry handles it". The defect lives in the parameters, not in the check, so no amount of staring at the detector logic reveals it.

The rule this violates is not "never raise temperature on a retry" — raising temperature on retry is exactly right for a *repetition* loop, where insufficient variety is the defect. The rule is narrower and survives being restated for any sampling knob:

> For a guardrail that measures a property **of the content**, the retry must **reduce the variance along that property's axis**. Entropy-raising retries belong to detectors that measure a **lack** of variety.

### 2. The retry loop had no terminal state that discarded

The loop could attempt again indefinitely, and on each attempt the candidate response remained eligible for persistence. When the violation survived the retry budget, nothing threw the turn away. The last attempt — a known-violating one — was what got written.

The missing structure is a **fail-closed exit**. A retry budget without an abort terminal state does not recover from a persistent failure; it converts a transient per-turn failure into a permanent one, because the terminal branch of the loop happens to be the persist branch.

### 3. The two defects hide each other's evidence

Because the retry raised entropy, the same mechanism that made contamination more likely also made it more likely to *pass on a later attempt*. The loop's own recovery signal was degraded by its own repair step. And because no verdict was recorded alongside the text, a turn that passed under relaxed settings is stored indistinguishably from one that passed first time. Neither the failure rate nor the repair rate is legible from the history afterwards.

## Fix

### 1. On a content-property violation, lower entropy instead of raising it

```python
# Before — the repair moves the axis the detector measures
if language_guardrail.violates(text):
    return generate(prompt, temperature=cfg.temperature + 0.3)   # more entropy, same drift

# After — a content violation is repaired by constraining, not by resampling wider
if language_guardrail.violates(text):
    return generate(
        prompt,
        temperature=cfg.language_retry_temperature,   # below the base setting
        extra_instruction="Respond only in the conversation language. No other language.",
    )
```

> The submitter uses a dedicated low-temperature setting for the language retry. The specific number is a local configuration value, not a general constant — what generalizes is the *direction*: strictly below the base temperature for this guardrail.

Note the deliberate split: the base temperature may legitimately be high for creative prose, and the repetition guardrail may legitimately raise it. The constraint is per-detector, and it is a property of the retry call site, not of the model config as a whole.

### 2. Give the loop a terminal state that discards, and route persistence through the check

```python
MAX_LANGUAGE_RETRIES = 2

def respond_with_language_guard(prompt, cfg):
    for _ in range(MAX_LANGUAGE_RETRIES):
        text = generate(prompt, temperature=cfg.language_retry_temperature)
        if not language_guardrail.violates(text):
            return Commit(text)              # only clean text can reach history
    return Discard(reason="errTurnUnintelligible")
```

> The submitter's discard path is a specific error code in their engine. The identifier is local; the mechanism is the terminal discard.

`Commit` and `Discard` are the only two exits, and **`Commit` is reachable only by a passing detector**. That is the structural change worth keeping: the persist step sits *downstream* of the check, not parallel to it. In the broken version the final attempt fell through into persistence by default; here, persistence is something a check has to authorize. Discarding a turn is a valid and often correct outcome, not a failure to be avoided at any cost.

### 3. Record the verdict, not just the text

```python
return Commit(text, guard="language", attempts=attempt_no, temperature=used_temp)
```

Without this, a turn repaired on attempt 2 under lowered entropy is indistinguishable from a clean first attempt, and the question "is the guardrail helping?" cannot be answered from logs. It is also the only way the entropy coupling stays visible once the immediate leak is fixed — the failure mode in this lesson is intermittent by construction.

## Verification

**Evidence boundary, stated up front:** the submission is a single-node report and carries **no reproduction script, no log excerpt, and no before/after count**. The behavioural outcome below is what the submitter observed in their own deployment. No metric is claimed here, and none should be quoted back as one.

What the submitter reports observing after the change: replies that still leaked the wrong language stopped reaching the chat history, because a persistently failing turn was discarded instead of stored.

The rest of this section is the criterion set a reader can apply in their own system. These are **tests to run, not results already obtained**.

1. **Axis check (config assertion, not a probabilistic test).** Read the retry call site for every content-property guardrail — language, format, schema, forbidden-token — and assert its retry temperature is `<=` the base temperature. This is a static property of the code and is the check that actually catches this class. A retry that adds to temperature for a content guardrail fails here regardless of what its pass rate looks like.
2. **Discard reachability.** Stub the detector to always violate. Pass: the loop terminates within a bounded number of attempts in a discard, and no text is written. Fail: a violating text is persisted — the terminal state is missing, and the compounding risk from Root Cause 2 is still live.
3. **No-persist-on-violation.** For every turn in a captured session, run the detector against the text that was *actually stored*. Pass: no stored text violates. A turn whose first attempt failed and whose retry passed is fine; a turn whose stored text violates is the bug, whatever the loop's internal verdict said.
4. **Discriminating power of the test itself.** A retry that succeeds by luck will pass any *probabilistic* check while still violating check 1. This is why check 1 is a config assertion and not a sampling test: the coupling being looked for lives in the parameters, and no amount of sampling will reliably surface it. If a reader only runs the probabilistic check, this bug class is not actually under test.

## See also

- [A cloned confirmation line poisons the context](roleplay-dialogue-loop-context-poisoning.md) — a different route to the same permanent-history failure, via a detector that never fired. This lesson covers a detector that fires correctly and is then routed around.
- [Character assistants — repetitive name and archetype loop](character-assistant-repetition-loop.md) — raises temperature deliberately, to buy variety. Useful contrast: entropy-raising retries are correct when the detected failure is insufficient variety, and wrong when it is a content violation.
- [RAG brand contamination detection and fix](rag-brand-contamination-detection-and-fix.md) — contamination at the *retrieval* layer. Here the contaminant is the model's own output, and the detection point is the persist boundary rather than the index.
