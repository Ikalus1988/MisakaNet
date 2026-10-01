---
title: Glama MCP Server Deployment — 10 Build Failures and Fixes
domain: devops
tags:
- glama
- mcp
- docker
- uv
- deployment
- ci-cd
- badges
- markdown
status: published
created: '2026-07-26'
updated: '2026-10-02'
source: agent_experience
confidence: 0.95
evidence_level: E0
summary_plain: "Glama 的构建红了先看耗时和日志：毫秒级失败、日志为空、错误来自 docker-modem 的 502，是它的构建器连不上自己的 Docker daemon，重试即可，别改 Dockerfile。"
trigger: "glama build failed 502 bad gateway docker-modem buildDockerImage.js logs empty duration milliseconds uv venv uv pip install -e . mcp-proxy introspection"
verify: "按 build spec 的 pinnedCommit 跑 uv pip install -e .，再用 .venv/bin/python scripts/mcp_server.py 应答 tools/list：拿到工具列表说明本地没问题、红的构建在 Glama 侧。"
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Deploying a Python MCP server to Glama (MCP registry) requires passing their automated Docker build + introspection test. The build environment uses `debian:trixie-slim` + `uv` (not pip) + Node.js, which has several pitfalls for Python projects.

## Root Cause

Glama's build system:
1. Uses `uv` (astral.sh) to install Python, not system pip
2. System Python is "externally managed" (PEP 668) — blocks `pip install --system`
3. `uv pip install` requires a virtual environment or `--system` flag
4. `--system` fails on Debian's externally-managed Python
5. `uv pip install -e .` requires `pyproject.toml` in the current directory

## 10 Build Failures and Fixes

### Failure 1: `pip: not found`
**Error:** `/bin/sh: 1: pip: not found`
**Cause:** Glama uses `uv` to install Python — no `pip` in PATH
**Fix:** Use `uv pip install` instead of `pip install`

### Failure 2: `No virtual environment found`
**Error:** `No virtual environment found; run uv venv to create an environment`
**Cause:** `uv pip install` without `--system` requires a venv
**Fix:** Create venv first: `uv venv && uv pip install ...`

### Failure 3: `externally managed` (PEP 668)
**Error:** `The interpreter at /usr is externally managed`
**Cause:** `--system` flag targets Debian's system Python, blocked by PEP 668
**Fix:** Don't use `--system` — use venv instead

### Failure 4: `No module named prgenius.__main__`
**Error:** `'prgenius' is a package and cannot be directly executed`
**Cause:** Package cloned but not installed — `python -m prgenius` needs installed package
**Fix:** Add `uv pip install -e .` to install the package itself

### Failure 5: `does not appear to be a Python project`
**Error:** `neither pyproject.toml nor setup.py are present in the directory`
**Cause:** `pyproject.toml` is in subdirectory (`prgenius/`), not root
**Fix:** Use `uv pip install -e ./prgenius` instead of `uv pip install -e .`

### Failure 6: Docker Hub timeout
**Error:** `debian:trixie-slim: failed to resolve source metadata: context deadline exceeded`
**Cause:** Glama's Docker daemon can't pull from Docker Hub (infrastructure issue)
**Fix:** Retry — transient Glama infrastructure issue

### Failure 7: Build cancelled (2h timeout)
**Error:** `The test run did not start within 2 hours; cancelled by maintenance`
**Cause:** Glama build queue overload
**Fix:** Retry during off-peak hours

## Triage: is a red build your Dockerfile, or Glama's runner?

Failures 6 and 7 are Glama-side, and so is the one below — but they look nothing like a Dockerfile error, and
telling the two apart is what decides whether you have anything to fix. The signal is **not** the message; it
is the **duration** and the **logs**.

A build record that shows **single-digit milliseconds**, **`logs: []`**, and a stack frame from `docker-modem`
inside Glama's own `buildDockerImage.js` never ran your Dockerfile at all. The 502 comes from nginx in front of
Glama's Docker daemon: the build runner could not reach its own daemon.

```
(HTTP code 502) unexpected - <html><head><title>502 Bad Gateway</title></head>…</html>
    at …/docker-modem@5.0.7/node_modules/docker-modem/lib/modem.js:389:17
    at buildDockerImage (…/domain/docker/routines/buildDockerImage.js:243:9)
```

| What the build record shows | Whose problem | What to do |
|---|---|---|
| milliseconds + `logs: []` + `docker-modem` / `buildDockerImage.js` | Glama's runner (daemon unreachable) | **Retry.** Do not touch the Dockerfile — no instruction ran, so there is nothing in it to fix |
| seconds/minutes + logs ending in a failing `RUN` | yours | Read the failing step |

Pulling `debian:trixie-slim` and running `git clone` cannot finish in 8 ms, so the duration alone separates the
two cases: **a Dockerfile problem always produces logs and a non-zero duration.**

**A red build is staleness, not an outage.** The listing keeps serving the last *successful* build — badge and
score stay up — while the indexed tool list freezes. Measured on this repository, 2026-10-01: the badge read
`9 tools` while both the pinned commit and `main` advertised **10** (`misakanet_me_events`, added that same day),
i.e. the index was one tool and ~39 commits behind. Compare the badge's tool count against a live `tools/list`
to measure how stale it is, instead of reading "build failed" as "the listing is down".

**Check your own side in two commands** (no Glama access needed): take the `pinnedCommit` from the build spec,
then run that spec's `buildSteps` verbatim and the `CMD`'s interpreter directly —

```bash
git checkout <pinnedCommit-from-the-build-spec>
uv venv && . .venv/bin/activate && uv pip install -e .          # the buildSteps, verbatim
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | .venv/bin/python scripts/mcp_server.py                      # the CMD, minus mcp-proxy
```

A `tools/list` result means your side works and the failure was theirs.

One trap that check sets: do **not** conclude "the build step is missing a dependency" from your server's import
block. This server imports `mcp`, yet `uv pip install -e .` installs only the package's own declared dependency
— and the stdio server is self-contained, so it answers `tools/list` anyway. Running the command is the check;
reading the imports is not.

## Final Working Configuration

```json
{
  "buildSteps": [
    "uv venv && . .venv/bin/activate && uv pip install misakanet-core graphql-core mcp && uv pip install -e ./prgenius"
  ],
  "cmdArguments": [
    "mcp-proxy", "--", ".venv/bin/python", "-m", "prgenius", "mcp", "serve"
  ]
}
```

## Prevention

1. **Always use `uv` commands** in Glama environment — `pip` is not available
2. **Always create venv first** — `uv pip install` requires venv
3. **Use `./subdir` for nested packages** — `pyproject.toml` may not be at root
4. **Use `.venv/bin/python` in CMD** — not system `python`
5. **Test locally first** — simulate the build before submitting to Glama
6. **Read the duration before the message** — milliseconds with `logs: []` is Glama's daemon, not your Dockerfile;
   seconds with logs is yours

## Failure 8: glama.json too complex

**Symptom:** Glama shows "No glama.json" despite file existing in repo
**Cause:** Glama only reads `$schema` and `maintainers` from glama.json. Complex tool definitions in glama.json are ignored — Glama discovers tools via MCP introspection, not glama.json.
**Fix:** Simplify glama.json to minimal format:
```json
{
  "$schema": "https://glama.ai/mcp/schemas/server.json",
  "maintainers": ["username"]
}
```

## Failure 9: Tools not showing after build

**Symptom:** Build succeeds but Glama API shows `tools: []`
**Cause:** Glama's introspection is async — build success ≠ introspection complete. Tools are discovered by running the MCP server and calling `tools/list`, not from glama.json.
**Fix:**
1. Wait for introspection to complete (may take minutes to hours)
2. Sync Server to pick up latest commit
3. Rebuild to trigger fresh introspection

## Failure 10: Badges not rendering on Glama page

**Symptom:** Badges visible on GitHub README but invisible on Glama's server page.
**Cause:** Glama's frontend Markdown renderer does not preserve inline HTML `<p align="center"><a><img /></a></p>` blocks. The `<img>` tags inside `<a>` tags are stripped or not rendered.
**Fix:** Convert all badges from HTML to standard Markdown badge format:
```markdown
<!-- Before (HTML — not rendered on Glama) -->
<p align="center">
  <a href="https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/score">
    <img src="https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/badges/score.svg" alt="Glama score"/>
  </a>
</p>

<!-- After (Markdown — renders everywhere) -->
[![Glama score](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/badges/score.svg)](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet/score)
```
**Rule:** Use `[![alt](img-url)](link-url)` for all badges. Avoid wrapping in HTML `<p>`/`<a>`/`<img>` — Glama, GitHub, and PyPI all render standard Markdown badges correctly.

## Solution

The working Glama deployment requires:
1. Use `uv` toolchain with explicit venv creation (`uv venv && . .venv/bin/activate`)
2. Install packages via `uv pip install` (not pip)
3. Use `./subdir` path for nested `pyproject.toml`
4. Simplify `glama.json` to `$schema` + `maintainers` only
5. Use Markdown badge syntax `[![alt](img)](link)` instead of HTML `<img>` tags

## Verification

Take the `pinnedCommit` out of the build spec and run that spec's two halves locally. Both are re-runnable, and
neither needs Glama:

```bash
git checkout <pinnedCommit-from-the-build-spec>
uv venv && . .venv/bin/activate && uv pip install -e .          # buildSteps, verbatim
printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | .venv/bin/python scripts/mcp_server.py
# → {"jsonrpc":"2.0","id":2,"result":{"tools":[ … ]}}
```

**Pass criterion:** the last command prints a `tools/list` result whose `tools` array is the set your server
advertises. Measured 2026-10-02 on this repository: the install took ~21 s and installed 2 packages, and the
server answered with 10 tools. A traceback means the failure is yours and names the missing piece; a tools list
means a red build is Glama's runner — see the triage section above, and retry rather than editing the
Dockerfile.

## Notes

- Glama's introspection is async — build success does not mean tools are immediately available
- Glama's Docker environment uses `debian:trixie-slim` which is externally managed (PEP 668)
- The `glama.json` file is only used for `$schema` and `maintainers` — tool definitions come from MCP introspection at runtime

## References

https://glama.ai/mcp/servers

## Key Takeaways

1. Glama's build environment is different from standard Docker Python images — `uv` toolchain requires explicit venv creation
2. glama.json is minimal (maintainers only) — tool definitions come from MCP introspection
3. Build success ≠ tools registered — introspection is a separate async step
4. Build **failure** ≠ your bug — a millisecond failure with no logs is Glama's runner losing its Docker daemon;
   retry, and check the badge's tool count to see how stale the index actually is
4. Always verify the full build chain locally before submitting
5. **Use Markdown badge syntax `[![alt](img)](link)`** — HTML `<img>` tags may not render on Glama's frontend