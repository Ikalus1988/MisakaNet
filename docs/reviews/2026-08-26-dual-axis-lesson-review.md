# Dual-Axis Lesson Quality Review — 2026-08-26

## Summary

| Metric | Value |
|--------|-------|
| Files reviewed | 287 / 300 (96%) |
| Critical findings | 61 |
| Major findings | 187 |
| Minor findings | 132 |
| **Total findings** | **380** |

**Review method:** 10 parallel agents, each reviewing ~30 lessons across two axes:
- **Standards axis** — format/template compliance (frontmatter, sections, verification, naming)
- **Spec axis** — content/technical accuracy (root cause depth, solution actionability, factual correctness)

---

## Critical Findings (61)

### 1. Malformed Frontmatter (35 files)
The most pervasive critical issue. A broken `'{"title":...}` JSON pattern is injected into YAML frontmatter, making the file unparseable by quality gates.

**Pattern:** Line 8 contains `'{"title": "...", ...}'` as a YAML key value after the real YAML frontmatter.

**Affected files:**
- `aily-feishu-mcp-pull-only.md`, `anthropic-proxy-internal-gateway.md`, `api-gateway-anthropic-incompatibility.md`
- `api-rate-limit-handling-best-practices.md`, `browser-harness-cdp-browser-automation.md`
- `chroma-rebuild-no-checkpoint-cn.md`, `feishu-doc-url-use-api-return.md`
- `feishu-mcp-server-deepseek-tui-setup.md`, `feishu-upload-file-type-opus.md`
- `feishu-webhook-url-env-config.md`, `game-mcp-end-turn-conflict-409.md`
- `game-mcp-game-over-restart-flow.md`, `game-mcp-rare-relic-freeze.md`
- `github-dns-443-block-hosts-workaround.md`, `gpt-sovits-ref-free-bug.md`
- `issue-comment-newbie-welcome.md`, `lesson-07-uv-venv-seed-fix-no-pip.md`
- `lesson-08-pip-https-proxy-clash.md`, `openclaw-playwright-wsl-libnss3-libnspr4-snap-chromium.md`
- `python-sandbox-path-isolation.md`, `python-venv-troubleshoot.md`
- `regex-greedy-matching.md`, `registration-chain-worker-fallback.md`
- `shared-json-needs-atomic-write.md`, `shell-script-debugging.md`
- `slugify-path-traversal-deep-coverage.md`, `tmux-session-management.md`
- `vertical-kb-question-bank-strategy.md`, `wcferry-wechat-version-lock.md`
- `worktree-git-path-deepseek-tui.md`, `wsl-pip-gbk-hub-poller-crash.md`
- `wxauto-im-feedback-collection-jsonl-queue.md`, `wxauto-windows-python-not-wsl.md`
- `git-push-yolo-task-codewhale.md`, `wsl-proxy-huggingface-external.md`
- `wsl-proxy-setup.md`, `wsl-terminal-underscore-corruption.md`
- `wsl-terminal-underscore-missing.md`

**Fix:** Run `scripts/fix_lesson_quality_v2.py` to convert JSON frontmatter to YAML. The script already handles single-line JSON; needs extension for the multi-line `'{"title":` pattern.

### 2. Security: Hardcoded Secrets (1 file)
- `hub-credential-gateway-vs-hub.md` — Contains plaintext `FEISHU_SECRET` and `shared_secret "looF ehT"` in lesson content.

**Fix:** Redact immediately with `<REDACTED>`.

### 3. Missing Files (7 files)
Files referenced in review but not on disk:
- `cc-connect-feishu-display-optimization.md` (renamed to `feishu-display-optimization-cc-connect.md`)
- `cc-connect-feishu-setup-complete.md` (renamed)
- `deepseek-tui-write-file-sandbox-worktree-git-path.md` (renamed)
- `feishu-wsclient-start-never-called.md`
- `newbie-welcome-comment.md`
- `oauth-missing-scope-auth-denied.md`
- `openclaw-self-heal-integration.md`, `openclaw-skills-not-loaded.md`, `openclaw-skill-file-not-found.md`, `openclaw-workspace-not-found.md`
- `php-session-lock-contention-fix.md`

### 4. Empty/Stub Lessons (3 files)
- `openclaw-prefer-cli-and-policy-over-direct-edit.md` — ~45 words, no Problem section
- `testimonio-misakanet.md` — User testimonial, not a technical lesson
- `feishu-setup-complete-cc-connect.md` — Empty Solution section

### 5. Incomplete Solution (1 file)
- `tor-orbot-privacy-in-react-native-tr.md` — Solution only sets HTTP header, does not configure actual Tor proxy routing

---

## Major Findings (187) — Top Categories

| Category | Count | Description |
|----------|-------|-------------|
| Verification ineffective | ~95 | Uses `echo`/`wc -l`/`grep` on unrelated files instead of testing lesson content |
| Missing `tags` field | ~25 | Frontmatter lacks required `tags` for search indexing |
| Non-standard sections | ~20 | Uses Chinese headings (背景/根因/修复) instead of Problem/Root Cause/Solution |
| Missing Root Cause | ~15 | No `## Root Cause` section, or says "see problem above" |
| Wrong domain | ~12 | `domain: contrib` instead of semantic domain (feishu, wsl, devops, etc.) |
| Thin content | ~8 | Under 100 words, stub-quality |
| Duplicate sections | ~5 | Two Verification or Notes sections |
| JSON frontmatter | ~8 | Uses `{...}` instead of YAML `---` delimiters |
| Template placeholder root cause | 5 | RAG lessons with generic "Inspect the RAG config..." as root cause |

### Verification Quality Crisis
**~95 of 287 files (33%) have non-functional verification.** The most common patterns:
1. `echo + wc -l` — prints title and line count, tests nothing
2. `grep -i fanuc/feishu/rag lessons/contrib/... | wc -l` — counts files, tests nothing
3. `python3 --version` — confirms Python is installed, tests nothing
4. `git status --short && git log --oneline` — generic git commands, tests nothing

---

## Minor Findings (132)

| Category | Count |
|----------|-------|
| Empty frontmatter fields | ~20 |
| Missing `source` field | ~15 |
| Missing `evidence_level` | ~10 |
| Redundant metadata (`lang` + `language`) | ~5 |
| Multilingual without `lang` marker | ~5 |
| Status `draft` in contrib/ | ~5 |
| Other | ~72 |

---

## Systemic Patterns

### 1. The `'{"title":` Plague (~35 files)
A batch import or migration injected raw JSON as a YAML key. This is the single biggest structural issue. Fixing it would resolve ~35 critical findings at once.

### 2. Verification Theater (~95 files)
One-third of all lessons have verification sections that test nothing. This was partially addressed in this session (116 → 2 files with VERIFICATION_NO_COMMAND), but the quality of the generated commands is still low — most are generic `echo`/`wc` patterns.

### 3. Chinese Section Headings (~20 files)
Many Chinese-language lessons use localized headings (背景/根因/修复) instead of the standard English template. This breaks automated section detection.

### 4. RAG Template Placeholders (5 files)
Five RAG lessons have the generic template instruction text as their root cause instead of actual analysis. These were likely created by an auto-generator that didn't fill in the template.

---

## Recommended Fix Priority

| Priority | Action | Files | Effort |
|----------|--------|-------|--------|
| P0 | Redact hardcoded secrets | 1 | 5 min |
| P1 | Fix `'{"title":` frontmatter pattern | 35 | 1 hr (scriptable) |
| P2 | Add `tags` to missing files | 25 | 30 min (scriptable) |
| P2 | Fix wrong `domain: contrib` | 12 | 15 min (scriptable) |
| P3 | Generate meaningful verification commands | 95 | 4+ hrs (needs per-lesson analysis) |
| P3 | Convert Chinese headings to English | 20 | 1 hr |
| P3 | Fill in template placeholder root causes | 5 | 30 min |
| P4 | Remove testimonial/stub lessons | 3 | 10 min |
| P4 | Consolidate near-duplicates | 3 pairs | 1 hr |

---

*Generated by 10 parallel review agents on 2026-08-26. Review covers lessons/contrib/ (300 files, 287 successfully read).*
