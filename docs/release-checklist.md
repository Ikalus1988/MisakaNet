# MisakaNet Release Checklist

Standard release process. Do not skip steps.

## Pre-release

1. **Run gate tests**
   ```bash
   python -m pytest tests/test_intake_redaction.py tests/test_demand_board_model.py tests/test_intake_classify.py
   python -m pytest
   ```

2. **Run site-health** (issue #783 — also run it after any Worker / frontend change)
   ```bash
   python3 scripts/site_health_check.py --write --strict
   ```
   Writes `docs/maintainer/site-health-YYYY-MM-DD.md` and exits non-zero if any
   endpoint or frontend entry point is not OK. Commit the snapshot with the release.

3. **Update version**
   - `pyproject.toml`: `version = "X.Y.Z"`
   - `server.json`: `"version": "X.Y.Z"` (both occurrences)

4. **Update CHANGELOG.md**
   - Add new version section with highlights, new files, data stats

5. **Update stale docs**
   - Scan for old lesson/node counts: `grep -rn "235\+\|244\|旧数字" --include="*.md" --include="*.html" --include="*.json"`
   - Update: README.md, docs/index.html, docs/search/index.html, docs/mcp-quickstart.md, STATUS.md, server.json description

## Release

6. **Commit and tag**
   ```bash
   git add -A
   git commit -m "release: vX.Y.Z - Title"
   git tag -a vX.Y.Z -m "vX.Y.Z — Title"
   git push && git push origin vX.Y.Z
   ```

7. **Publish to PyPI**
   ```bash
   python -m build
   python -m twine upload dist/misakanet-X.Y.Z*
   ```

8. **Create GitHub Release**
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z — Title" --notes '...'
   ```

## Post-release

9. **Wait for Glama auto-sync** — no manual action needed

10. **MCP Registry — best-effort only**
    - Requires `mcp-publisher.exe login github` (device code flow)
    - Requires direct HTTPS to `registry.modelcontextprotocol.io:443`
    - Unreliable in restricted networks (proxy, firewall)
    - **Do not delay release for MCP Registry**
    - Retry manually when network is available:
      ```bash
      .\mcp-publisher.exe login github
      .\mcp-publisher.exe publish
      ```

## Do NOT update for routine releases

- **npm `@misaka-net/fatal-guard`** — only if fatal-guard code changed
- **`misakanet-core`** — only if search core library changed
- **Smithery** — continue pause
- **GitHub /mcp** — continue pause until v2.13+ demo-ready
- **`server.mcpb`** — do not rebuild for Smithery

## Order principle

```
PyPI → GitHub Release → CHANGELOG/docs → site-health → Glama wait → MCP Registry (best-effort)
```

MCP Registry is last and non-blocking. Never let it delay the release.
