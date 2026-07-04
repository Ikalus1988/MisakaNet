# Decentralized Autonomous Learning Network (DALN) Specification

**Version:** 1.0.0-draft  
**Status:** Formal Specification  
**Repository:** Ikalus1988/MisakaNet  
**Date:** 2023-10-27

---

## 1. Executive Summary

The Decentralized Autonomous Learning Network (DALN) is the core architectural vision of MisakaNet. It is a peer-to-peer protocol designed to facilitate the autonomous discovery, propagation, verification, and consensus of "Lessons" (structured knowledge units) across a distributed network of nodes without a central authority.

DALN aims to solve the "single point of failure" and "censorship" problems in traditional knowledge graphs by leveraging a trust-based reputation system and a conflict resolution mechanism that favors verifiable, high-reputation sources.

---

## 2. Core Concepts

- **Node**: An instance of the MisakaNet client running on a machine, participating in the network.
- **Lesson**: A cryptographic hash of a structured knowledge unit (JSON-LD), signed by the author. Contains content, metadata, and a reference to parent lessons.
- **Trust Graph**: A dynamic, directed graph where edges represent trust scores between nodes, derived from historical behavior.
- **Epoch**: A logical time window during which specific consensus rules apply.

---

## 3. Protocol Definition

### 3.1 State Machine

Each node operates as a finite state machine (FSM) with the following states:

1.  **INIT**: Node is starting up, loading local state.
2.  **DISCOVERING**: Actively searching for peers via bootstrap nodes or DHT.
3.  **SYNCING**: Synchronizing the local Lesson Graph with discovered peers.
4.  **ACTIVE**: Fully connected, processing incoming messages, and propagating new lessons.
5.  **SUSPENDED**: Temporarily isolated due to low trust score or network partition.
6.  **OFFLINE**: Graceful shutdown or network loss.

**Transitions:**
- `INIT` → `DISCOVERING` (on successful config load)
- `DISCOVERING` → `SYNCING` (on finding ≥ 3 peers)
- `SYNCING` → `ACTIVE` (on hash verification of local DB)
- `ACTIVE` → `SUSPENDED` (if trust score < threshold)
- `SUSPENDED` → `DISCOVERING` (after cooldown period)

### 3.2 Message Formats

All messages are serialized as Protocol Buffers (or JSON for debugging) and wrapped in a transport envelope.

#### Envelope