// A D1 stand-in that implements the `kv_store` table, for tests of the durable-store paths (#2116).
//
// Why this exists: `storePut`/`storeGet` write D1 first and keep KV as the fallback, so a test whose
// D1 stub silently accepts every statement looks like it is exercising the new path while actually
// storing nothing — the index goes "into D1", the write is reported as successful, and the next read
// finds an empty table. The tests that caught this were the ones asserting the index is *readable*
// (workers/bm25-index-refresh.test.mjs): 7 of them failed the first time the index was published
// through `storePut`, because a permissive stub answered `SELECT value FROM kv_store` with lesson
// rows and the value column did not exist.
//
// Wrap any existing D1 stub with this and it keeps handling every other statement:
//
//     env.MISAKANET_D1 = withKvStore(createColumnAwareD1(rows));
//
// The expiry comparison mirrors the SQL in `storeGet` (`expires_at IS NULL OR expires_at > now`), so a
// test can drive TTL behaviour without a real database.
export function withKvStore(d1 = null, { now = () => new Date().toISOString() } = {}) {
  const rows = new Map();

  const created = () => ({ run: async () => ({ success: true }) });

  return {
    /** The rows the durable store holds — `Map<key, value>`, for assertions. */
    kvStore: rows,
    /** Every statement this stub saw, so a test can assert the *query* says what it must. */
    kvStoreSql: [],

    prepare(sql) {
      const text = String(sql);
      this.kvStoreSql.push(text);

      if (/CREATE TABLE IF NOT EXISTS kv_store/i.test(text)) {
        return { bind: () => created(), run: created().run };
      }

      if (/INSERT INTO kv_store/i.test(text)) {
        return {
          // (key, value, expires_at) — the order `storePut` binds them in.
          bind: (key, value, expiresAt) => ({
            run: async () => {
              rows.set(String(key), { value: String(value), expires_at: expiresAt || null });
              return { success: true };
            },
          }),
        };
      }

      if (/CREATE INDEX IF NOT EXISTS kv_store_expires_at/i.test(text)) {
        return { bind: () => created(), run: created().run };
      }

      // A delete by key (`storeDelete`): `DELETE FROM kv_store WHERE key = ?1`.
      if (/DELETE FROM kv_store[\s\S]*WHERE key = \?1/i.test(text)) {
        return {
          bind: (key) => ({
            run: async () => ({ success: true, meta: { changes: rows.delete(String(key)) ? 1 : 0 } }),
          }),
        };
      }

      // The reclaimer (#2117): `DELETE … WHERE key IN (SELECT key … LIMIT n)`.
      if (/DELETE FROM kv_store/i.test(text)) {
        return {
          bind: (limit = 500) => ({
            run: async () => {
              let deleted = 0;
              for (const [key, row] of [...rows.entries()]) {
                if (deleted >= limit) break;
                if (row.expires_at && row.expires_at <= now()) {
                  rows.delete(key);
                  deleted += 1;
                }
              }
              return { success: true, meta: { changes: deleted } };
            },
          }),
        };
      }

      if (/SELECT value FROM kv_store/i.test(text)) {
        // Whether an expired row is hidden is the *query's* decision, not this stub's: the predicate
        // is read out of the SQL. A stub that filters unconditionally would keep answering "expired
        // rows are hidden" after the predicate was deleted from the worker, which is the one bug this
        // whole file exists to catch — a mutation that removed it left the tests green.
        const filtersExpiry = /expires_at\s+IS\s+NULL\s+OR\s+expires_at\s*>\s*datetime\('now'\)/i.test(text);
        return {
          bind: (key) => ({
            all: async () => {
              const row = rows.get(String(key));
              if (!row) return { results: [] };
              if (filtersExpiry && row.expires_at && row.expires_at <= now()) return { results: [] };
              return { results: [{ value: row.value }] };
            },
          }),
        };
      }

      if (!d1) {
        throw new Error(`withKvStore: unexpected statement with no inner stub — ${text.slice(0, 80)}`);
      }
      return d1.prepare(sql);
    },
  };
}
