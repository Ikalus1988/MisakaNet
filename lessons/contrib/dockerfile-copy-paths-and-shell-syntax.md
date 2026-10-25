---
title: "Dockerfile COPY does not follow a moved file and does not understand shell redirects"
domain: "docker"
tags:
  - "dockerfile"
  - "copy"
  - "dockerignore"
  - "build-context"
  - "unknown-instruction"
  - "repo-restructure"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "Dockerfile 的 COPY 按构建上下文找文件、也不接受 shell 语法；项目结构调整后路径没跟上，COPY 会让整个 build 失败。"
trigger: "Dockerfile COPY failed file in subdirectory COPY unknown instruction 2>/dev/null || true"
verify: "在仓库根目录跑 docker build . 退出码 0，且 docker run --rm <image> ls <被 COPY 的目录> 能看到期望的文件。"
source: "intake-2102"
provenance:
  issue: "#2102"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Dockerfile COPY does not follow a moved file and does not understand shell redirects

## Problem

Two build failures from the same Dockerfile, both after the project layout changed:

1. `COPY pyproject.toml README.md CHANGELOG.md LICENSE ./` failed: `pyproject.toml` had been moved into the `prgenius/` subdirectory, while the other three files were still at the repository root. One source in the list no longer existed where the instruction said it was.
2. The developer then tried to make the copy tolerant — `COPY dir/ ./ 2>/dev/null || true` — and got an `unknown instruction` build error instead of a graceful skip.

Both are Dockerfile errors, not build-environment errors: the file itself described a repository layout that no longer existed, and then used shell syntax that `COPY` does not have.

## Root Cause

Two independent rules, and the second is the one that surprises people:

- **`COPY <src>` resolves against the build context**, the directory passed to `docker build`. A relative source is a path inside that context, not a path relative to the Dockerfile and not a path that the instruction can follow when files move. A Dockerfile is a static snapshot of the layout at the time it was written: when `pyproject.toml` moved into `prgenius/`, the `COPY` line kept pointing at the context root and its source simply stopped existing. Nothing in the Dockerfile refers to the restructure, so nothing warns.
- **`COPY` is a build instruction, not a command run by a shell.** There is no shell in front of it, so `2>/dev/null` and `|| true` are not part of its grammar — the Dockerfile parser rejects the line (the reported fragment is `unknown instruction`). And there is no "continue if the source is missing" mode: a `COPY` whose sources resolve to nothing fails the build. That is exactly what the redirect was trying to work around, so the workaround could never work.

Together: a path list that must be maintained by hand against a layout that changes, plus an attempt to make it fault-tolerant with syntax the instruction does not support.

## Solution

1. **Treat COPY sources as a claim about the repository layout, and re-check the claim on every restructure.** Before committing a move, list the references:

   ```bash
   grep -rn --include='Dockerfile*' -e 'COPY' -e 'ADD' .
   ```

   Any path in that output that no longer exists is a build failure waiting for the next CI run.

2. **Prefer `COPY . .` with a `.dockerignore`** over a hand-maintained file list. One instruction covers files that appear later and does not need editing when the layout moves:

   ```dockerfile
   COPY . .
   ```

   ```gitignore
   .git
   .venv
   __pycache__
   *.pyc
   dist/
   tests/
   ```

   Exclusions belong in `.dockerignore`, which is the supported place for "everything except" — a `COPY` line is the wrong place for it.

3. **If the copy really must name a subdirectory, write the real path** (`COPY prgenius/pyproject.toml ./`), and keep the file list short enough that a restructure is visible in the diff.

4. **Never put shell syntax in `COPY`.** If a condition is needed, put it in a `RUN` (`RUN test -f <path>`) so a missing file fails with a message you wrote, rather than making the copy tolerate absence — a build that silently skips a required file produces an image that fails at runtime instead of at build time.

## Verification

The reporter's three checks, all of which must be green together:

- `docker build .` succeeds locally — **from the repository root**, the same context the publish pipeline uses. A build that only succeeds when run from inside `prgenius/` tests a different context than the one that ships.
- The Glama MCP auto-build passes.
- The GHCR publish workflow passes.

The criterion that actually catches a regression: the build must be run with the same context root as CI, and after the build, `docker run --rm <image> ls <directory>` must show the files the `COPY` was supposed to place. A build that completes because `COPY . .` copied a different subset than intended still passes `docker build`; only looking inside the image shows it.

## Notes

- 报料者未给出 `COPY dir/ ./ 2>/dev/null || true` 失败的完整报错原文（只给了 `unknown instruction` 这个片段），也没有给出缺失源文件时 `COPY pyproject.toml …` 的确切报错文本 —— 需复现确认。两条指令的具体行号、Dockerfile 的 base image 也未给出。
- The same project's "pyproject.toml is not at the repository root" fact also shows up in a build-step context rather than a COPY context: Glama's spec needed `uv pip install -e ./prgenius` (see [glama-mcp-server-deploy-lessons.md](lessons/contrib/glama-mcp-server-deploy-lessons.md), Failure 5). One restructure, two instruction languages, same root cause: a path written once and never re-checked.
- Domain choice: `docker` — the failing artifact is the Dockerfile and its build context, and that is the word a reader will search for.
