---
{
  "title": "Glama MCP Server Deployment — 10 Build Failures and Fixes",
  "domain": "devops",
  "tags": ["glama", "mcp", "docker", "uv", "deployment", "ci-cd", "badges", "markdown"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-26",
  "confidence": "0.95"
}
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

Each failure was verified by:
- Reading Glama build logs for exact error messages
- Applying the fix and triggering a rebuild
- Confirming the build passes and tools appear in Glama API after introspection completes

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
4. Always verify the full build chain locally before submitting
5. **Use Markdown badge syntax `[![alt](img)](link)`** — HTML `<img>` tags may not render on Glama's frontend
