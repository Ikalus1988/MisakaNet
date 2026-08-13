---
title: "An Unlikely Database Migration: From JSON Files to etcd"
domain: "database-architecture"
tags: ["database-migration", "etcd", "golang", "control-plane", "performance", "key-value-store"]
language: "en"
status: "published"
source: "https://tailscale.com/blog/an-unlikely-database-migration/"
created: "2026-07-28"
confidence: 0.85
---

# An Unlikely Database Migration: From JSON Files to etcd

## Problem

Tailscale's control plane (CONTROL) began using a JSON file-based persistence layer that became a significant bottleneck as the service scaled. The database file reached a peak size of 150MB, with the entire file being rewritten on every data change. Even with optimizations like NVMe drives and splitting data into two halves (important data vs. ephemeral data on tmpfs), performance degraded as the file I/O became the limiting factor.

## Root Cause

The original persistence mechanism was implemented as a shortcut during early development: a Go in-memory data model wrapped in `sync.Mutex` that would serialize the entire data structure to JSON and write it to disk on every edit. The data model structure followed this pattern:

```go
type AllTheData struct {
    BigLock sync.Mutex
    Somethings map[string]Something
    Widgets map[string]Widget
    Gadgets map[string]Gadget
}
```

This approach was intended to be temporary but persisted because the team prioritized other work. The fundamental issue was that every write operation required serializing and writing the entire state, not just the changed data.

## Solution

Tailscale migrated to etcd as a "minimally-viable database" for the following reasons:

1. **KV-store alignment**: The core data model mapped naturally onto a key-value store pattern
2. **Lock granularity**: Migration broke the `BigLock` into something more akin to `sync.RWMutex`
3. **Selective writes**: Only changed data is written, not the entire structure
4. **Testing benefits**: Being written in Go, etcd can be linked directly into tests without Docker or mocks, allowing tests to run against the same codebase used in production
5. **Positive validation**: A Jepsen report showed positive results for etcd, and the team had positive experiences from previous use

The team also evaluated but rejected alternatives:
- **SQLite**: Could work but difficult to justify for a growing service
- **MySQL/PostgreSQL**: High availability story was concerning; required Docker for testing
- **CockroachDB**: Promising but relatively new with risk of vendor lock-in

## Verification

not specified in source

## Notes

- The Tailscale team is intentionally careful not to use etcd features that would be hard to map onto CockroachDB, keeping migration options open for the future
- Tailscale maintains an open source etcd client wrapper at `github.com/tailscale/tailetc`
- The team successfully debugged and fixed a slow key pagination edge case in etcd 3.4 by reading through source code and implementing a fix in one hour
- CONTROL remains a single Go process on a single VM; the control plane design doesn't require high availability typical of web services (short outages only prevent new nodes from logging in; existing networks continue working)

## References

- Jepsen report on etcd (referenced as showing positive results)
- CockroachDB (mentioned as alternative database option)
- Perkeep's dockertest (github.com/tailscale/tailetc mentioned as reference in testing approach)
- Tailscale tailetc client: github.com/tailscale/tailetc