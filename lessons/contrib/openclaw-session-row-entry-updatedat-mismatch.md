---
{"title": "OpenClaw 8.2 — session_nodes entry_valid stays 0 after manual sqlite edit", "domain": "openclaw", "tags": ["openclaw", "sqlite", "session_nodes", "canonical-key", "repair", "entry_valid"], "language": "en", "status": "draft", "evidence_level": "E2", "created": "2026-09-10", "updated": "2026-09-10", "source": "incident-2026-09-09", "provenance": {"source": "self", "contributor": "Community", "evidence": "locally reproduced + fixed + smoke-tested"}}
---
# OpenClaw 8.2 — session_nodes entry_valid stays 0 after manual sqlite edit

## Problem

On OpenClaw 8.2.x, manually editing `session_nodes.entry_json` (e.g. to clear
`mainRestartRecovery` fields) leaves `entry_valid=0` permanently, even after
restarting the gateway. Every subsequent `openclaw agent --agent main` call
returns:

```
SessionCanonicalKeyMigrationRequiredError: invalid persisted session row
requires repair for agent:main:main; stop the Gateway and run
openclaw doctor --fix: code=SESSION_CANONICAL_KEY_MIGRATION_REQUIRED
```

Feishu DM inbound messages hit the same error during `feishu[default]:
dispatching to agent`, so the bot stops replying. The reported symptom is
"channel connected, works, but no reply arrives."

Manual `UPDATE session_nodes SET entry_valid=1` does NOT stick — three
`AFTER INSERT/UPDATE` triggers on the table re-set it back to 0:

- `session_nodes_entry_valid_after_insert`
- `session_nodes_entry_valid_after_entry_update`
- `session_nodes_entry_valid_after_identity_update`

The triggers fire because `entry_valid=1` is only ever set as a side effect
of OpenClaw's own internal re-validation pass, which the gateway runs once
at startup and which checks two invariant conditions on the row.

## Root Cause

The OpenClaw 8.2 validator function
`scanCanonicalSqliteSessionEntries` (in
`session-accessor.sqlite-transcript-state-*.js`) inspects every `session_nodes`
row and throws `SessionCanonicalKeyMigrationRequiredError` when any of:

1. `row.entry_valid !== 1`, OR
2. `parseSqliteSessionEntryRecord(row)` returns `null`, OR
3. lineage columns drift from `entry.parentSessionKey` / `spawnedBy`.

`parseSqliteSessionEntryRecord` returns `null` when:

```js
(row.current_session_id !== record.sessionId)
|| (row.updated_at !== record.updatedAt)
```

In other words `entry_json.sessionId === session_nodes.current_session_id`
AND `entry_json.updatedAt === session_nodes.updated_at` must BOTH be exact
integers. Naive manual edits that touch only `entry_json` (or only
`updated_at`) break this invariant and the next validator pass refuses to
mark `entry_valid=1`.

The skill `openclaw-gateway-troubleshooting` section C.3 mentions
`SessionCanonicalKeyMigrationRequired` and prescribes "DELETE then INSERT
minimal row" — but a blanket delete also drops `transcript_events`,
`conversations`, `session_windows`, and `session_pending_inputs` linked by
session_id, which means losing the entire direct-DM history. A targeted
fix is preferable when the only broken invariant is the entry ↔ row match.

## Solution

Stop the gateway, then run a single SQL update that aligns the row's
`current_session_id` / `updated_at` with the `sessionId` / `updatedAt`
values inside `entry_json`. Restart the gateway — the validator will pass
the row and set `entry_valid=1` itself.

### Step 1 — stop gateway and back up

```bash
ps -ef | grep -E 'openclaw.*gateway' | grep -v grep | awk '{print $2}' \
  | xargs -r kill -9
sleep 3
ss -ltn | grep 18789 || echo "gateway down"

# Full sqlite backup before any edit
cp -a <agent-sqlite> /tmp/openclaw-agent-full-backup-$(date +%s).sqlite
```

### Step 2 — align entry_json with row columns

```bash
python3 - <<'PY'
import sqlite3, json, time
DB = "<agent-sqlite>"
c = sqlite3.connect(DB)
key = "agent:main:main"
r = c.execute(
  "SELECT current_session_id, updated_at, entry_json "
  "FROM session_nodes WHERE session_key=?", (key,)
).fetchone()
current_sid, updated_at, entry_json = r
e = json.loads(entry_json)

# The two fields parseSqliteSessionEntryRecord demands equality on:
e["sessionId"]   = current_sid
e["updatedAt"]   = updated_at
# Canonical identity fields used by 8.2 validator downstream:
e.setdefault("canonicalKey", key)
e.setdefault("agentId",      "main")

now_ms = int(time.time() * 1000)
new_json = json.dumps(e, ensure_ascii=False)

c.execute(
  "UPDATE session_nodes SET entry_json=?, updated_at=?, status='running' "
  "WHERE session_key=?",
  (new_json, updated_at, key),  # keep updated_at unchanged; equality matters
)
c.commit()
PY
```

Notes:
- Do NOT set `entry_valid=1` in the UPDATE — the trigger fires on UPDATE OF
  `current_session_id, updated_at` and resets it; setting it to 1 here is
  wasted. The validator will set it to 1 at startup if the row is internally
  consistent.
- Do NOT change `current_session_id` — `transcript_events.session_id` FKs
  point at it. Keep it stable.

### Step 3 — restart gateway and smoke-test

```bash
openclaw gateway --port 18789 &
sleep 15
openclaw channels status --probe    # expect "connected, works"

# Smoke-test the dispatch path that previously failed:
timeout 90 openclaw agent --agent main -m 'ping pong' --deliver
```

Expected reply: a real model response (e.g. "pong 🏓"), NOT the
`SessionCanonicalKeyMigrationRequiredError` and NOT the
`settled-turn finalization completed without a visible answer: using terminal
fallback reply` chain that was the secondary symptom.

## Verification

```bash
# 1. Row invariant landed
python3 -c "
import sqlite3
DB='<agent-sqlite>'
c=sqlite3.connect(DB)
r=c.execute(\"SELECT entry_valid FROM session_nodes WHERE session_key='agent:main:main'\").fetchone()
print('entry_valid:', r[0])  # expect: 1
"

# 2. Feishu channel probe
openclaw channels status --probe
# Expected output: "Feishu default: enabled, configured, running, connected, works"

# 3. Dispatch path smoke-test
timeout 90 openclaw agent --agent main -m 'ping pong' --deliver
# expect: a real model reply (e.g. "pong"), NOT
#         "SessionCanonicalKeyMigrationRequiredError" and NOT
#         "settled-turn finalization completed without a visible answer".

# 4. Log fingerprint (no dispatch error paired with dispatching log)
grep -E 'dispatching to agent|failed to dispatch message' \
  /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -5
# expect: every "dispatching to agent" line is followed by an assistant
#         message, NOT a "failed to dispatch message: ..." error.
```

### Why the secondary "no final summary" symptom went away

The `failed to dispatch` / `attempts=2/2 using terminal fallback reply`
chain was downstream of the canonical-key throw — once the validator
accepted the row, dispatch resumed normally and the model returned a real
answer on the first attempt. Same fix, two symptoms.

## Related

- Skill `openclaw-gateway-troubleshooting` section C.3 — covers the
  nuclear "DELETE+INSERT" path that loses transcript_events; this lesson is
  the targeted alternative when only the entry ↔ row match is broken.
- Skill section B.1 — when the same symptom is caused by
  `mainRestartRecovery.tombstone`, follow the python sqlite script in the
  skill first; check whether the tombstone-clear also caused the
  entry_json ↔ row drift this lesson describes.
