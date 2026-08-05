# Feishu Domain

Lessons for integrating MisakaNet with Feishu (Lark) bots, documents, and notifications.

---

## feishu — webhook URL must be env var or gitignored

**Problem:** Feishu webhook URLs committed to git create a security risk.

**Fix:** Use `FEISHU_WEBHOOK_URL` environment variable or `hub/config.yaml` (gitignored).

**Verify:** `grep -r 'open.feishu.cn' .git/` returns no matches.

---

## feishu — credential rotation requires Gateway restart

**Problem:** After rotating Feishu App credentials, Gateway still uses old tokens silently.

**Fix:** Run `hermes-cli restart gateway` after credential rotation.

**Verify:** `hermes-cli status gateway` shows "running" and bot replies in group chat.

---

## feishu — WebSocket never started (dead code)

**Problem:** `HubFeishuWSClient.start()` was defined but never called, so WebSocket messages were never received.

**Fix:** Register the call to `start()` after `__init__` completes in `hermes_hub.py`.

**Verify:** Hub receives and logs incoming Feishu messages.

---

## feishu — message dispatch fails with OpenClaw Gateway

**Problem:** OpenClaw Gateway dynamic module loading fails on Python path mismatch.

**Fix:** Set `PYTHONPATH` explicitly in startup script, or install the module via `pip install -e .`

**Verify:** Gateway responds to `@bot` mentions.

---

*More: search lessons with `search_knowledge.py "feishu" --lessons`*
