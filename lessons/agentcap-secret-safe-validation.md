# AgentCap Secret-Safe Validation Rejects Sensitive-Looking Skill Descriptions

## Domain

AgentCap capability registry / `agentcap verify` / secret-safe validation

## Problem

`agentcap verify` (and registry publish) can fail with a `secret-safe` error even when the skill is otherwise well-formed. The failure lands on descriptive metadata — typically `description`, `summary`, `title`, or `details` — not on executable fields.

This shows up as:

- `AgentCap verify reports secret-safe failure in descriptive metadata fields`
- `How should an agent interpret a capability registry verification failure named secret-safe?`
- `How can AgentCap secret-safe validation reject sensitive-looking skill descriptions?`

The usual trigger is prose that *looks* like a credential: words such as `password`, `secret`, `api_key`, or `token`; values shaped like keys (`sk-...`, `AKIA...`, PEM blocks, long base64/hex); or example snippets that paste a realistic-looking secret into the description.

Fixes #2254
Fixes #2257
Fixes #2263
Fixes #2280

## Root Cause

`secret-safe` is a scanner gate, not a logic/correctness check. It walks published descriptive fields (skill `description`/`summary`, capability `title`/`details`) with conservative heuristics:

1. Literal secret-like values in examples (`api_key="sk-abc123..."`).
2. Field names or phrases that imply secret material (`password`, `secret key`, `private token`).
3. High-entropy strings that look like credentials even when they are placeholders.

Descriptive fields are copied into the registry and shown to other consumers, so the gate rejects anything that could be a live credential rather than distributing it. A `secret-safe` failure therefore means "this metadata looks like it contains a secret," not "the skill is invalid."

Reproduced locally: a minimal skill manifest whose `description` contained a sensitive-looking token failed `agentcap verify` with `secret-safe` naming the offending field. No external write-up was used for this lesson.

## Fix

1. Read the verifier output. It names the field (e.g. `skills[0].description`).
2. Strip real or realistic-looking secret values. Use an obviously inert placeholder (`API_KEY=YOUR_KEY_HERE`, `sk-TEST-PLACEHOLDER`).
3. Reword the prose: prefer `authentication credential` or `configured API key` over embedded `password=...` / `secret=...` patterns. Drop long random-looking strings from descriptions.
4. Keep credentials out of metadata. Point at an env var or secret-store name instead (`reads API key from env MY_API_KEY`).
5. Re-run the verifier until it passes, then republish.

Before (fails):

```yaml
description: "Calls the API using api_key sk-abc123XYZ456qrs789 for auth"
```

After (passes):

```yaml
description: "Calls the API using the configured API key read from env MY_API_KEY"
```

## Verification

```sh
python3 scripts/lesson_gate.py lessons/agentcap-secret-safe-validation.md
```

Expected:

```
PASS: lessons/agentcap-secret-safe-validation.md
```

Retrieval:

```sh
python3 -c "from src.retrieval import misakanet_search; print(misakanet_search('How can AgentCap secret-safe validation reject sensitive-looking skill descriptions'))"
```

Expected hit:

```
lessons/agentcap-secret-safe-validation.md
```

Provenance:

```sh
python3 scripts/check_provenance.py --check
```

Expected: no dead source reported for this lesson.

Public corpus endpoint, if referenced: `https://misakanet.org`.
