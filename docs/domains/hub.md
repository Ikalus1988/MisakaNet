# Hub Domain

Lessons about the Hermes Hub — central coordination layer for the MisakaNet swarm.

---

## hub — FeishuWSClient.start() never called

**Problem:** `start()` was defined in `HubFeishuWSClient` but never invoked after `__init__`, making WebSocket message reception dead code.

**Fix:** Add `self.feishu_ws_client.start()` after the callback registration block in `hermes_hub.py`.

**Verify:** Hub logs show incoming Feishu messages.

---

## hub — credential system: Gateway vs Hub

**Problem:** Gateway and Hub have separate credential stores — updating one does not update the other.

**Fix:** Gateway uses `~/.hermes/.env`, Hub uses `~/MisakaNet/config.yaml` + environment variables. Both must be updated separately.

**Verify:** Both Gateway and Hub can authenticate to Feishu independently.

---

## hub — WSL pip install GBK encoding crash

**Problem:** `pip install` from within Hermes Hub on WSL crashes due to GBK encoding in logs.

**Fix:** Set `PYTHONIOENCODING=utf-8` before running Hub scripts.

**Verify:** `python3 hub/hermes_hub.py` starts without UnicodeDecodeError.

---

*More: search lessons with `search_knowledge.py "hub|hermes" --lessons`*
