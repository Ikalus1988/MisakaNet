# Agent Self-Healing Mini Benchmark

A 10-task benchmark comparing agent performance with versus without MisakaNet knowledge retrieval.

## Methodology

Each task simulates a real-world agent failure scenario. The agent is given the failure and must self-heal within 3 attempts. We measure:

- **Without MisakaNet**: Agent relies on its own training data and general reasoning
- **With MisakaNet**: Agent can query `search_knowledge.py` for relevant lessons before attempting a fix

### Metrics

| Metric | Description |
|--------|-------------|
| Success rate | % of tasks healed within 3 attempts |
| Mean attempts | Average attempts until success |
| Mean time | Average wall-clock time to heal |
| First-attempt rate | % healed on first try |

---

## Task Suite

### Task 1: DCO Sign-Off Failure

**Scenario**: CI fails with `Expected "Signed-off-by: ..."` on a PR.

**Setup**: Create a branch, commit without `--signoff`, push, observe CI failure.

**Expected Heal**: Amend commit with `--signoff --no-edit`, force-push.

**Without MisakaNet**: Agent may try re-committing, rebasing, or adding footer manually.

**With MisakaNet**: Query `search_knowledge.py "DCO sign-off"` → retrieves `ci-dco-fork-pr-signoff.md` with exact fix.

**Success Criterion**: CI passes after heal.

---

### Task 2: pip install Timeout

**Scenario**: `pip install -r requirements.txt` hangs indefinitely on a large package.

**Setup**: Simulate a slow PyPI mirror or large dependency.

**Expected Heal**: Set `--default-timeout=60` or use `pip install --timeout 30`, switch to `uv pip install`.

**Without MisakaNet**: Agent may retry with `--retries`, increase verbosity, or wait.

**With MisakaNet**: Query `pip install timeout` → retrieves `pip-install-timeout-ssl.md` with timeout flags and mirror fallback.

**Success Criterion**: Install completes within 2 minutes.

---

### Task 3: GitHub Token 401

**Scenario**: `git push` or API call returns `HTTP 401 Bad credentials`.

**Setup**: Use an expired or invalid `GITHUB_TOKEN`.

**Expected Heal**: Check token validity via `gh auth status`, regenerate from GitHub Settings → Developer Settings → Tokens, update local config.

**Without MisakaNet**: Agent may re-enter credentials, check `.git/config`, or give up.

**With MisakaNet**: Query `github 401 token` → retrieves `github-401-credential-lookup.md` with PAT scope guidance.

**Success Criterion**: `git push` succeeds after heal.

---

### Task 4: MCP Server Path Error

**Scenario**: Agent tries to start an MCP server but gets `ENOENT: no such file or directory` for the server binary.

**Setup**: Configure Claude Desktop with a wrong `command` path in `claude_desktop_config.json`.

**Expected Heal**: Find the correct binary path with `which` / `where`, update the config, restart.

**Without MisakaNet**: Agent may reinstall the package, check `PATH`, or edit config blindly.

**With MisakaNet**: Query `MCP server path` → retrieves MCP setup patterns with path resolution.

**Success Criterion**: MCP server starts and tool list appears.

---

### Task 5: Windows GBK Encoding Error

**Scenario**: Python script crashes with `UnicodeDecodeError: 'gbk' codec can't decode byte...` when reading a file on Windows.

**Setup**: Create a file with UTF-8 characters, read it with default Windows encoding.

**Expected Heal**: Add `encoding='utf-8'` to `open()` call or set `PYTHONUTF8=1` environment variable.

**Without MisakaNet**: Agent may try `errors='ignore'`, `chardet` detection, or file conversion.

**With MisakaNet**: Query `Windows encoding GBK` → retrieves encoding best practices.

**Success Criterion**: File reads without error.

---

### Task 6: pytest ImportError

**Scenario**: `pytest` fails with `ImportError: cannot import name '...'` after a dependency update.

**Setup**: Install incompatible versions of `pytest` and a plugin.

**Expected Heal**: Pin compatible versions in `requirements-dev.txt`, reinstall with `pip install -r requirements-dev.txt`.

**Without MisakaNet**: Agent may try `pip install --upgrade`, `pip check`, or manual imports.

**With MisakaNet**: Query `pytest ImportError dependency` → retrieves `python-venv-troubleshoot.md`.

**Success Criterion**: `pytest --version` runs without import errors.

---

### Task 7: Cloudflare Deploy Failure

**Scenario**: `wrangler deploy` fails with `API request failed: 403 Forbidden`.

**Setup**: Use a Cloudflare API token without Workers permissions.

**Expected Heal**: Verify token permissions in Cloudflare Dashboard → API Tokens, ensure `Workers Scripts:Edit` scope, update `CF_API_TOKEN`.

**Without MisakaNet**: Agent may retry deploy, check `wrangler.toml`, or re-login.

**With MisakaNet**: Query `cloudflare deploy 403` → retrieves `cloudflare-email-worker-registration-trap.md`.

**Success Criterion**: `wrangler deploy` succeeds.

---

### Task 8: JSON Schema Validation Error

**Scenario**: API response fails validation with `jsonschema.exceptions.ValidationError`.

**Setup**: Send a malformed JSON payload missing a required field.

**Expected Heal**: Inspect the schema, identify the missing field, add it with a valid value.

**Without MisakaNet**: Agent may guess the missing field, try defaults, or relax validation.

**With MisakaNet**: Query `json schema validation` → retrieves `json-schema-validate-input.md` with debugging patterns.

**Success Criterion**: Payload passes validation.

---

### Task 9: npm publish 403

**Scenario**: `npm publish` fails with `403 Forbidden - You do not have permission to publish`.

**Setup**: Try publishing to a scoped package without proper access or an expired token.

**Expected Heal**: Check `npm whoami`, verify scope permissions in `package.json`, regenerate npm token with publish scope.

**Without MisakaNet**: Agent may try `npm login`, check registry URL, or change scope.

**With MisakaNet**: Query `npm publish 403` → retrieves registry and auth patterns.

**Success Criterion**: `npm publish --dry-run` passes permission check.

---

### Task 10: Stale Generated Data Cleanup

**Scenario**: CI cache or generated files cause false test passes because stale artifacts mask real failures.

**Setup**: Generate output files, then change the source without regenerating.

**Expected Heal**: Add `rm -rf dist/ build/ *.egg-info/` before build step, add `.gitignore` for generated dirs, add `--force-regen` flag.

**Without MisakaNet**: Agent may clear cache, re-run tests, or add cleanup script.

**With MisakaNet**: Query `stale generated data cleanup` → retrieves build hygiene patterns.

**Success Criterion**: Stale artifacts are removed and tests reflect current source.

---

## Running the Benchmark

```bash
# Run all 10 tasks with MisakaNet
python3 bench/self-healing/run_benchmark.py --with-misakanet

# Run baseline (no knowledge retrieval)
python3 bench/self-healing/run_benchmark.py --baseline

# Run a single task
python3 bench/self-healing/run_benchmark.py --task dco-signoff
```

## Results Template

| Task | Without MK (attempts) | Without MK (time) | With MK (attempts) | With MK (time) | Improvement |
|------|----------------------|--------------------|--------------------|-----------------|-------------|
| 1. DCO sign-off | | | | | |
| 2. pip timeout | | | | | |
| 3. GitHub 401 | | | | | |
| 4. MCP path | | | | | |
| 5. GBK encoding | | | | | |
| 6. pytest import | | | | | |
| 7. Cloudflare | | | | | |
| 8. JSON schema | | | | | |
| 9. npm publish | | | | | |
| 10. Stale data | | | | | |
| **TOTAL** | | | | | |

---

*Benchmark v1.0 — designed for MisakaNet issue #682*
