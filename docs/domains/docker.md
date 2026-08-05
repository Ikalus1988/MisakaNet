# Docker Domain

Lessons learned running MisakaNet nodes in Docker and containerized environments.

---

## docker — lesson injection path mismatch

**Problem:** `inject_to_claude.py` expects `CLAUDE.md` at the project root, but Docker containers often mount repos at non-standard paths.

**Fix:** Set `LESSONS_DIR` env var or symlink `CLAUDE.md` into the container mount.

**Verify:** `python3 misakanet/scripts/inject_to_claude.py` exits 0.

---

## docker — pip install network timeout in build step

**Problem:** Docker build fails on `pip install -r requirements.txt` due to network timeouts in restricted CI runners.

**Fix:** Use `--retries 3 --timeout 10` flags or mirror pip cache via `--mount=type=cache`.

**Verify:** `docker build --no-cache .` completes.

---

*More: search lessons with `search_knowledge.py "docker" --lessons`*
