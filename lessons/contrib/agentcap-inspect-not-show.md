---
title: "huggingface/agentcap inspect, not show, is the subcommand to read a run record"
domain: development
tags: [python, agentcap, huggingface, cli, inspect, agent-eval, agent-benchmark]
status: published
evidence_level: E2
summary_plain: "agentcap uses 'inspect <rid>' not 'show' to read a run record; rid is 32-hex from ls output"
trigger: "agentcap show run record 'unrecognized arguments' inspect 32-hex rid"
verify: "agentcap ls → pick a run rid (32 hex chars) → agentcap inspect <rid> succeeds and prints JSON"
---

## Problem

`agentcap show <rid>` fails with "unrecognized arguments" or "invalid choice" — the subcommand doesn't exist. Users expect `show` to read a run record from Hugging Face's AgentCap benchmarking tool (`huggingface/agentcap`).

## Root Cause

AgentCap CLI subcommands are: `run`, `ls`, `export`, `inspect`. There is no `show` subcommand. `inspect` is the correct command to read a single run record by its run ID (rid). The rid is a 32-character hex string, visible in `agentcap ls` output.

## Solution

```bash
# List recent runs to find a rid
agentcap ls

# Read a run record (use the 32-hex rid from ls output)
agentcap inspect a1b2c3d4e5f607182930405060708090

# Export is for bulk/filtered export to JSONL — not for single-run read
agentcap export --out results.jsonl
```

If you need to script against the output, `agentcap inspect` prints JSON to stdout — pipe through `jq`:

```bash
agentcap inspect a1b2c3d4e5f607182930405060708090 | jq '.score, .model, .status'
```

## Verification

```bash
pip install agentcap
agentcap ls          # lists runs, each with a rid column
agentcap inspect <rid-from-ls>   # prints JSON of that run; exit 0
agentcap show <rid>              # should error: 'show' is not a valid subcommand
```