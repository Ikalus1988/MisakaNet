---
title: "pip install agentcap gets a different project — huggingface/agentcap is a Rust binary"
domain: development
tags: [python, agentcap, huggingface, cli, name-collision, pypi, rust, agent-eval]
status: published
evidence_level: E2
summary_plain: "PyPI 'agentcap' is OliverIida's cost-guardrail lib with no CLI; huggingface/agentcap installs via curl install.sh"
trigger: "agentcap command not found unrecognized arguments show inspect pip install agentcap"
verify: "pip install agentcap && agentcap ls -> 'command not found'; curl install.sh then agentcap ls lists runs"
---

## Problem

`pip install agentcap` "succeeds", then every `agentcap ...` invocation fails — usually `command not found`, or if the Python package did put something on PATH, the subcommands you expect are missing.

The trap is that **two unrelated projects share the name**:

| | PyPI `agentcap` | `huggingface/agentcap` |
|---|---|---|
| Author | Oliver Iida (`OliverIida/agentcap`) | Hugging Face |
| What it is | "Cost guardrails for LLM agent runs" | end-to-end agent-capture harness |
| Language | Python | Rust |
| Version | 0.1.1 | binary releases |
| CLI | **none** | `agentcap run` / `ls` / `export` / `inspect` |

`pip install agentcap` installs the left column. The CLI everyone means is the right column. The install "succeeding" is what makes this confusing — nothing tells you you got the wrong project.

## Root Cause

PyPI and GitHub do not share a namespace. `pip install <name>` resolves against PyPI only, so a name that is unclaimed or claimed by someone else on PyPI will happily install that other project. Nothing in the pip output names the GitHub repo, so the mismatch stays invisible until the CLI is missing.

## Solution

Install the Rust binary from the GitHub project — **not** from PyPI:

```bash
curl -fsSL https://raw.githubusercontent.com/huggingface/agentcap/main/scripts/install.sh | sh
```

The script detects your platform, downloads the matching binary and installs it to `~/.local/bin`. Useful flags (after `sh -s --`):

```bash
# custom install dir
curl -fsSL .../install.sh | sh -s -- -b /usr/local/bin

# pin a version
curl -fsSL .../install.sh | sh -s -- -v <tag>
```

Binaries are also on GitHub Releases as `agentcap-x86_64-linux` and `agentcap-arm64-apple-darwin`. To build from source, see the repo's "Building from source" section.

Make sure the install dir is on `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Commands that actually exist

| Command | Purpose |
|---|---|
| `agentcap run` | sandboxed agent runs, multi-turn, follow-ups, backends |
| `agentcap ls` | list runs (`-l` adds upstream + counts) |
| `agentcap export` | push captures + traces as a HF Collection |
| `agentcap inspect` | workspace / parquet / HF dataset pickers |

Two optional dependencies, needed only by the command that uses them: **`podman`** for the sandbox `agentcap run` drives, and **`trufflehog`** for the secret scan `agentcap export` runs before pushing (skip with `--no-scan`).

### `inspect` is a picker, not a JSON dump

`agentcap inspect` opens an interactive three-level picker over a capture source (`parquet → request → message`, with live preview and Esc walk-back). It takes a **dataset/workspace reference**:

```bash
agentcap inspect my-org/my-captures-captures
```

It does **not** take a hex run id and print JSON — if you want machine-readable output, that is `agentcap export`, not `inspect`.

### Run directories are named, not hashed

Runs land under `.agentcap/<agent>-<provider>-<utc>/`, so the identifier you see in `ls` is that directory name, not a 32-character hex string.

## What to do if you already installed the wrong one

```bash
pip uninstall agentcap
# then install the real one
curl -fsSL https://raw.githubusercontent.com/huggingface/agentcap/main/scripts/install.sh | sh
```

## Verification

```bash
# 1) the wrong package provides no CLI
pip install agentcap && agentcap ls
# -> zsh: command not found: agentcap   (or: no such subcommand)

# 2) what you actually installed
python3 -c "import importlib.metadata as m; print(m.metadata('agentcap')['Summary'])"
# -> Cost guardrails for LLM agent runs.

# 3) the real binary
curl -fsSL https://raw.githubusercontent.com/huggingface/agentcap/main/scripts/install.sh | sh
agentcap ls          # lists runs under .agentcap/
agentcap inspect my-org/my-captures-captures   # interactive picker
```

## Scope note

Verified on macOS arm64: the PyPI metadata lookup and the GitHub README (subcommand table, install command, run-directory layout, `podman`/`trufflehog` prerequisites). I did not install and execute the Rust binary end to end, so the `run`/`export`/`inspect` behaviour above is from the project's own docs, not a live run. The PyPI/GitHub name collision — the actual failure this lesson is about — is verified directly.
