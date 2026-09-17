-- MisakaNet D1 Lesson Service — schema (PRD ④)
-- Apply: wrangler d1 execute misakanet-db --remote --file=workers/d1/schema.sql

CREATE TABLE IF NOT EXISTS lessons (
  id TEXT PRIMARY KEY,          -- slug (filename without .md)
  title TEXT NOT NULL,
  domain TEXT,
  status TEXT DEFAULT 'published',
  language TEXT DEFAULT 'en',
  tags TEXT,                    -- JSON array
  path TEXT,                    -- repo path, e.g. lessons/core/foo.md
  problem TEXT,                 -- first ~2000 chars of Problem/描述 section
  root_cause TEXT,
  solution TEXT,
  verification TEXT,
  content_md TEXT,              -- full markdown body (after frontmatter)
  frontmatter TEXT,             -- raw frontmatter JSON
  summary TEXT,                 -- short summary from lessons.json
  created TEXT,
  updated TEXT,
  synced_at TEXT,               -- sync run timestamp
  checksum TEXT                 -- content hash for repo<->D1 reconciliation
);

CREATE INDEX IF NOT EXISTS idx_lessons_domain ON lessons(domain);
CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons(status);
CREATE INDEX IF NOT EXISTS idx_lessons_updated ON lessons(updated);
CREATE INDEX IF NOT EXISTS idx_lessons_created ON lessons(created);

-- Sync ledger: one row per successful sync run (audit + reconciliation)
CREATE TABLE IF NOT EXISTS lesson_sync_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_at TEXT NOT NULL,
  source_commit TEXT,
  total INTEGER NOT NULL,
  upserted INTEGER NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0,
  checksums TEXT               -- JSON: {id: checksum} for reconciliation
);

-- PRD ③: intake pipeline drafts. Each intake (MCP submit_intake / email /
-- crash tombstone) gets a row here after parse→classify→draft→precheck; a
-- maintainer reviews it (via the linked GitHub issue) and promotes it into
-- the lessons/ table (or the repo) on approval.
CREATE TABLE IF NOT EXISTS lesson_drafts (
  id TEXT PRIMARY KEY,          -- draft slug
  kind TEXT NOT NULL,           -- missing_lesson | stale_lesson | new_lesson_candidate | question
  source TEXT,                  -- mcp | email | tombstone | api
  source_id TEXT,               -- original intake id (dedup key), e.g. issue-1234
  status TEXT DEFAULT 'draft',  -- draft | prechecked | review | approved | rejected | merged
  title TEXT,
  domain TEXT,
  tags TEXT,                    -- JSON array
  problem TEXT,
  root_cause TEXT,
  solution TEXT,
  verification TEXT,
  content_md TEXT,              -- generated lesson draft (frontmatter + body)
  precheck TEXT,                -- JSON report: {score, issues[], verified}
  issue_number INTEGER,         -- linked GitHub review issue
  issue_url TEXT,
  created TEXT,
  updated TEXT,
  UNIQUE(source_id, kind)       -- idempotency: same intake never processed twice
);

CREATE INDEX IF NOT EXISTS idx_drafts_status ON lesson_drafts(status);
CREATE INDEX IF NOT EXISTS idx_drafts_kind ON lesson_drafts(kind);
CREATE INDEX IF NOT EXISTS idx_drafts_source ON lesson_drafts(source_id);

-- PRD ④ #1357: usage analytics — which lessons are searched/viewed,
-- which queries miss (knowledge gaps), latency/error signal. Written
-- asynchronously via ctx.waitUntil so hot paths are not blocked.
CREATE TABLE IF NOT EXISTS lesson_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event TEXT NOT NULL,          -- 'search' | 'get_lesson' | 'no_match'
  query TEXT,                   -- search query (if applicable)
  lesson_id TEXT,               -- lesson accessed (if applicable)
  domain TEXT,                  -- lesson domain
  ip TEXT,                      -- anonymized (first 2 octets, e.g. 192.168.0.0)
  user_agent TEXT,              -- agent name/version (truncated 80)
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_usage_event ON lesson_usage(event);
CREATE INDEX IF NOT EXISTS idx_usage_created ON lesson_usage(created_at);

-- PRD ④ #1356: FTS5 full-text search index. Standalone virtual table
-- (content duplicated from lessons for simplicity — 314 rows is tiny).
-- Rebuilt after each sync by scripts/sync_lessons_to_d1.py.
CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
  id UNINDEXED,
  title,
  problem,
  root_cause,
  solution,
  verification,
  content_md
);

-- PRD ⑤ #1396: async question intakes — durable state + answer delivery.
-- One row per question-kind intake issue. The worker records 'pending' on
-- submit; a sync (scripts/sync_answered_questions.py / cron) flips answered
-- rows and stores the maintainer's answer; re-submitting the same question
-- returns the answer, and misakanet_search surfaces answered rows as FAQ
-- hits — pull-based delivery, no push channel (see docs/prd/05 §9).
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  issue_number INTEGER UNIQUE NOT NULL,
  dedup_hash TEXT,               -- content hash, same scheme as intake_dedup KV key
  problem TEXT NOT NULL,
  source TEXT DEFAULT 'mcp',
  status TEXT DEFAULT 'pending', -- pending | answered
  answer TEXT,                   -- maintainer answer markdown (answered only)
  answer_comment_id INTEGER,     -- GitHub comment id that carries the answer
  issue_url TEXT,
  created TEXT DEFAULT (datetime('now')),
  answered_at TEXT,
  updated TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);
CREATE INDEX IF NOT EXISTS idx_questions_dedup ON questions(dedup_hash);

-- ── Counters & telemetry (KV → D1, issues #1647-#1649, 2026-09-12) ──────────
-- Why this exists: KV's free tier caps *distinct keys written per day* (1,000), and a
-- same-key rewrite is exempt. So the paths that need a new key per request or per entity
-- are the ones that die first — proven live on 2026-09-12, when `misakanet_register`
-- (which writes `node:<id>` and `mcp_token:<token>`, both new every call) failed with
-- `KV put() limit exceeded for the day.` while the cron's index rewrite kept succeeding.
-- Counters are rows, not keys, and D1 allows ~100k row writes/day on the free tier.
--
-- One table serves them all: `scope` names the counter family, `bucket` the subject
-- (ip, ip:minute, traffic class, query) and `period` the window. A single
-- `INSERT … ON CONFLICT … RETURNING count` increments atomically, which the KV
-- read-modify-write never did.
--
-- Retention: rows are small and periodic. `scripts/prune_counters.py` (issue #1649)
-- is not required for correctness; anything older than the longest window (30 days for
-- traffic monthly) can be deleted at leisure.
CREATE TABLE IF NOT EXISTS counters (
  scope      TEXT NOT NULL,   -- rate_read | signal_rate | traffic | traffic_monthly | gap
  bucket     TEXT NOT NULL,   -- ip | ip:minute | class | query
  period     TEXT NOT NULL,   -- YYYY-MM-DD | YYYY-MM-DDTHH:MM | YYYY-MM
  count      INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (scope, bucket, period)
);

CREATE INDEX IF NOT EXISTS idx_counters_scope_period ON counters(scope, period);

--
-- kv_store: the registration keys that were still KV-only (follow-up to #1647, 2026-09-17).
--
-- `misakanet_register` writes `node:<id>` and `mcp_token:<token>` — both *new* keys on every
-- call — and auth reads `mcp_token:<token>` back. The free tier caps KV at 1,000 distinct keys
-- written per day (a same-key rewrite is exempt), so registration is the first path to die
-- when that budget is spent: measured live on 2026-09-12 (#1647), and again on 2026-09-17 when
-- every registration answered `storage_unavailable` while KV *reads* kept working.
--
-- #1647-#1649 moved the counters to their own table and left the registration keys behind.
-- Same medicine here: rows, not keys. Key shapes stay identical to the KV ones, so reads fall
-- back to KV for tokens issued before this table existed and a rollback sees the same
-- namespace.
CREATE TABLE IF NOT EXISTS kv_store (
  key        TEXT PRIMARY KEY,   -- verbatim KV key: node:<id> | mcp_token:<token> | client:<client_id>
  value      TEXT NOT NULL,      -- the JSON text that used to be the KV value
  expires_at TEXT,               -- ISO-8601, or NULL for none (mirrors expirationTtl)
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_kv_store_expires ON kv_store(expires_at);
