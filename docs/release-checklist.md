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
   - Lesson / node / domain counts are **not** hand-edited any more: the managed sentences are rewritten
     by `scripts/sync_lesson_count.py`, which the daily jobs run (`update-lessons.yml` reaches it through
     `update_lessons_json.py`; `sync-node-counter.yml` owns the node row). Run
     `python3 scripts/sync_lesson_count.py --check` instead of grepping for the previous numbers — a
     grep pattern is stale the moment the number moves, which is how this step used to read.
   - Update the prose that no gate owns: README.md, docs/index.html, docs/search/index.html,
     docs/mcp-quickstart.md, server.json description
   - `STATUS.md` is gone (#2095 deleted the generator *and* the file, in that order of discovery — the
     file was never in the repo). If a step here still names it, that step is stale, not the file.

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

10. **MCP Registry — automatic (since 2026-09-19, #1820)**
    - `.github/workflows/publish-mcp-registry.yml` runs after every release: `release-please.yml`
      dispatches it once it has tagged, passing the version it just tagged.
    - Identity is the repository itself (`mcp-publisher login github-oidc`) — no stored secret, no
      device code to babysit. The workflow validates `server.json`, refuses a version mismatch,
      publishes, and then **reads the registry back**: it fails unless `isLatest` is the version it
      published.
    - Manual republish, for when the listing has drifted anyway (escape hatch, not the plan):
      ```bash
      gh workflow run publish-mcp-registry.yml --ref main -f "version=2.31.0"
      ```
    - **Why this is no longer a maintainer's manual step:** the listing had drifted to
      `isLatest = 2.29.0` while the repo, PyPI and the GitHub release were all at 2.30.2. The device
      flow also cannot be completed from a sandboxed agent environment at all: `github.com` is
      unreachable there (measured 2026-09-19 — HTTP 000 after 15s) while the registry is reachable,
      so "retry when the network is available" was never going to happen from inside one.

## Do NOT update for routine releases

- **npm `@misaka-net/fatal-guard`** — only if fatal-guard code changed
- **`misakanet-core`** — only if search core library changed
- **Smithery** — continue pause
- **GitHub /mcp** — continue pause until v2.13+ demo-ready
- **`server.mcpb`** — removed (2026-09-02); use `server.json` (v2.23.0) as the MCP manifest

## Order principle

```
PyPI → GitHub Release → CHANGELOG/docs → site-health → Glama wait → MCP Registry (best-effort)
```

MCP Registry is last and non-blocking. Never let it delay the release.
