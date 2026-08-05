# Tombstone Protocol v2 — RFC

> A standardized, minimal, redacted fatal-error payload format for Node.js process crashes.
> Status: Draft | Version: 2 (alpha) | 2026-06-22
> Implementation: `@misaka-net/fatal-guard`

## Purpose

Define a portable, versioned, redacted-by-default JSON contract for reporting process crashes from a parent wrapper (or preload hook) to an external handler (syslog, webhook, custom script). The protocol is language-agnostic but the reference implementation targets Node.js.

## Core Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Redacted by default** | No stack traces, env vars, or secrets. The handler decides what to enrich. |
| **Backward compatible** | New fields are additive. `schemaVersion` signals the shape. Consumers that only read known fields never break. |
| **Lightweight** | Payload < 1KB in typical scenarios. No blocking I/O during collection. |
| **Self-describing** | `schemaVersion` + `reason` alone are enough for basic alert routing. |

## v1 (Current, 4 fields)

```json
{
  "schemaVersion": 1,
  "reason": "uncaught_exception",
  "timestamp": "2026-06-19T08:38:26.091Z",
  "pid": 180739
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schemaVersion` | integer | Always `1` |
| `reason` | string | `uncaught_exception` · `unhandled_rejection` · `process_crash` · `exit_code` · `killed_by_<signal>` |
| `timestamp` | string | ISO 8601 |
| `pid` | integer | Process ID |

## v2 (Alpha — Conservative Extension)

Adds runtime context fields (no secrets, no stack):

```json
{
  "schemaVersion": 2,
  "reason": "killed_by_SIGKILL",
  "timestamp": "2026-06-22T04:00:00.000Z",
  "pid": 12345,
  "exitCode": null,
  "signal": "SIGKILL",
  "rssMB": 284.3,
  "uptimeSec": 14402
}
```

### v2 Alpha Fields (compared to v1)

| Field | Type | Max | Description | Risk |
|-------|------|-----|-------------|------|
| `schemaVersion` | integer | — | Bumped to `2` | None |
| `exitCode` | integer\|null | 0-255 | Raw exit code. Null when killed by signal. | None — already visible in process exit |
| `signal` | string\|null | 16 chars | Signal name like `SIGKILL`, `SIGTERM`. Null for normal exit. | None — same as exit code |
| `rssMB` | number\|null | — | Resident Set Size in MB at crash time | Low — aggregate metric, not a secret |
| `uptimeSec` | number\|null | — | Process uptime in seconds | Low — no identifying info |

Total added size: **~80 bytes** per payload.

### v2 Beta — Adds Non-Fatal Stderr Snippet

Extends v2 Alpha with a guarded stderr excerpt:

| Field | Type | Max | Description | Risk |
|-------|------|-----|-------------|------|
| `stderrSnippet` | string\|null | 500 chars | Last N lines of stderr, redacted | **Medium** — must pass through `redact()` |

### v2 Gamma — Adds Process Snapshot (Optional)

Extends v2 Beta with performance-critical process snapshot:

| Field | Type | Max | Description | Risk |
|-------|------|-----|-------------|------|
| `fdCount` | integer\|null | — | Open file descriptors at crash | Low |
| `heapUsedMB` | number\|null | — | V8 heap usage in MB | Low |
| `nodeVersion` | string\|null | 32 chars | `process.version` value | None |

## Migration Strategy

### Rolling upgrade (recommended)

```text
Phase 1: Writers emit v2, consumers read v2
  → Set schemaVersion: 2, add new fields
  → Old consumers ignore unknown fields (per JSON Schema `additionalProperties`)

Phase 2: All consumers updated
  → Enable v2-specific features (routing by signal, uptime-based preemption)
```

### Consumer compatibility

| Consumer | v1 payload | v2 payload |
|----------|-----------|-----------|
| Syslog / logger | Reads `reason`, `timestamp`, `pid` → unchanged behavior | Same fields in same positions → **no breakage** |
| Promtail → Loki | Ingests all JSON fields → unknown fields silently indexed | New fields appear in Loki → **no breakage** |
| Custom alert script | Reads `reason` to decide severity | Same field + `signal` for more precise routing → **backward compatible** |

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| `stderrSnippet` may contain secrets | Must be passed through `redact()` before serialization |
| `rssMB` / `heapUsedMB` reveals resource usage | Aggregate metric only; cannot identify specific code paths |
| `uptimeSec` reveals restart patterns | Acceptable risk; restart frequency is observable from process manager anyway |

## Reference Implementation

- `@misaka-net/fatal-guard` — Node.js wrapper + preload
- Payload builder: `packages/fatal-guard/index.js` → `buildPayload(reason)`
- Redaction: `packages/fatal-guard/src/lib/redact.js` → `redact(text)`
- Test suite: `packages/fatal-guard/tests/verify-fix.js`

## Related

- [Security Audit Report](security-audit-report.md)
- [Node Hardening Guide](node-hardening.md)
