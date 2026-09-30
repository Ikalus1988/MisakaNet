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
   - Lesson / domain counts are **not** hand-edited any more: the three surfaces that carry the literal
     number are rewritten by `scripts/sync_lesson_count.py`, which the daily jobs run
     (`update-lessons.yml` reaches it through `update_lessons_json.py`). Run
     `python3 scripts/sync_lesson_count.py --check` instead of grepping for the previous numbers — a
     grep pattern is stale the moment the number moves, which is how this step used to read. The node
     count is not published at all (#2313).
   - Everything else *points* at the count: the READMEs/ROADMAP carry the shields badge, and prose names
     the source. Do not paste a total back into README.md, docs/search/index.html, the integration
     guides, `skill.md`, JOIN.md or `.well-known/*.json` — `tests/test_lesson_count_ssot.py` fails on it.
     What still needs a human eye at release time is the prose *around* the numbers (server.json
     description, the site's marketing copy) and the version lines.
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

## npm bundle (`misakanet`) — automatic since 2026-09-30 (D1 = A)

- `package.json` and `.codex-plugin/plugin.json` are release-please-owned now
  (`release-please-config.json` → `.` → `extra-files`, `{"type": "json", "jsonpath": "$.version"}`), so
  the release PR carries the npm line and the tagged commit already says the released version.
  `tests/test_version_consistency.py::JSON_PINNED_VERSION_FILES` fails if either file lags the manifest
  or loses its declaration.
- The publish runs itself: `.github/workflows/misakanet-publish.yml` triggers on a **published
  release** (and on `misakanet-v*` tags, and on `workflow_dispatch`). Before publishing it refuses a
  tree whose `package.json` is not the released version — the run cannot ship a stale bundle, and it no
  longer moves or rewrites the line (a run that finds the version already on npm stands down, because
  the release event and release-please's dispatch both fire for one release).
- It declares `environment: release`, which holds `NPM_TOKEN` (granular, read+write on `misakanet`;
  rotation in `docs/maintainer/credentials-and-environments.md` §4.1). For an unattended publish that
  environment must not require a reviewer, and its deployment branch policy must allow the tag refs the
  release-event run uses (`v*`).
- Manual republish (escape hatch):
  ```bash
  gh workflow run misakanet-publish.yml --ref main -f "version=2.39.0"
  ```

**Rolling back a bad automatic publish** — npm cannot republish a version, and `npm unpublish` is only
available for **72 hours** after the publish (after that, only npm support can remove it):

```bash
npm deprecate misakanet@X.Y.Z "broken: install Y.Y.Y"   # always available — the safe default
npm unpublish misakanet@X.Y.Z --force                   # only inside the 72h window
```

Prefer `deprecate`: an unpublished version breaks every lockfile that pinned it (`ETARGET`), which turns
one bad release into a fleet of broken installs. Then fix forward — cut a patch release so the channels
move together. Do **not** hand-edit `package.json` backwards: release-please owns the line, and a
backwards move is what `npm_bundle_floor` in `scripts/align_versions.py` reports on (an advisory by the
owner's decision of 2026-09-29 — a rollback and a typo look identical from the number alone).

## Do NOT update for routine releases

- **npm `@misaka-net/fatal-guard`** — only if fatal-guard code changed
- **`misakanet-core`** — only if search core library changed
- **Smithery** — continue pause
- **GitHub /mcp** — continue pause until v2.13+ demo-ready
- **`server.mcpb`** — removed (2026-09-02); use `server.json` as the MCP manifest (its `version` is maintained by release-please — do not quote it here, intake #2486)

## Order principle

```
PyPI → GitHub Release → CHANGELOG/docs → site-health → Glama wait → MCP Registry (best-effort)
```

MCP Registry is last and non-blocking. Never let it delay the release.
