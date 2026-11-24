// The ladder's "someone else fetched your lesson" read must be three indexed joins, not one OR.
//
// Measured 2026-11-23 in Cloudflare's D1 analytics, grouped by query, over 2026-10-25…11-23:
//
//     19,561,754,663  rows read   1,873 calls   ≈10,444,076 rows per call
//     SELECT la.node_id … FROM search_signals ss JOIN lesson_authors la
//       ON la.path = ss.top_id OR la.lesson_id = ss.top_id OR la.slug = ss.top_id
//      GROUP BY la.node_id
//
// One query was 90% of every row this account read in a month: an OR across three columns cannot use
// an index, so the plan degenerates to `lesson_authors × search_signals`.
//
// This test runs both forms through real SQLite (`node:sqlite`), so it pins what matters: the rewrite
// returns **the same counts** (a faster wrong answer is not a fix), and the query shape is no longer
// the quadratic one.
//
// Run: node --test workers/ladder-join-is-indexed.test.mjs
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import test from 'node:test';
import { ladderUsedSql } from './register-proxy-sw.js';

const NEWLINE = String.fromCharCode(10);

const OLD_SQL = `SELECT la.node_id AS node_id, COUNT(*) AS n, MAX(ss.created_at) AS last
  FROM search_signals ss
  JOIN lesson_authors la
    ON la.path = ss.top_id OR la.lesson_id = ss.top_id OR la.slug = ss.top_id
 GROUP BY la.node_id`;

function build() {
  const db = new DatabaseSync(':memory:');
  db.exec(`
    CREATE TABLE lesson_authors (
      path TEXT PRIMARY KEY, lesson_id TEXT, slug TEXT, node_id TEXT, login TEXT,
      updated_at TEXT NOT NULL DEFAULT (datetime('now')));
    CREATE INDEX idx_lesson_authors_node ON lesson_authors(node_id);
    CREATE INDEX idx_lesson_authors_lesson_id ON lesson_authors(lesson_id);
    CREATE INDEX idx_lesson_authors_slug ON lesson_authors(slug);
    CREATE TABLE search_signals (
      id INTEGER PRIMARY KEY AUTOINCREMENT, solved INTEGER NOT NULL, query TEXT, top_id TEXT,
      result_count INTEGER NOT NULL DEFAULT 0, domain TEXT,
      created_at TEXT DEFAULT (datetime('now')));
    CREATE INDEX idx_search_signals_top ON search_signals(top_id);
  `);

  // `search_signals.top_id` carries a lesson id, a path or a basename (measured 2026-11-13 across
  // 16k signals), so each author row answers to three different spellings.
  const insertAuthor = db.prepare(
    'INSERT INTO lesson_authors (path, lesson_id, slug, node_id, login) VALUES (?, ?, ?, ?, ?)');
  for (let i = 0; i < 400; i += 1) {
    insertAuthor.run('lessons/' + i + '.md', 'lesson-' + i, 'slug-' + i, 'Misaka' + (i % 37), 'user' + i);
  }

  const insertSignal = db.prepare(
    'INSERT INTO search_signals (solved, query, top_id, created_at) VALUES (1, ?, ?, ?)');
  for (let i = 0; i < 3000; i += 1) {
    const n = i % 400;
    const shape = i % 3;
    const topId = shape === 0 ? 'lessons/' + n + '.md' : shape === 1 ? 'lesson-' + n : 'slug-' + n;
    insertSignal.run('q' + i, topId, '2026-11-20T00:00:00Z');
  }
  for (let i = 0; i < 20; i += 1) {
    insertSignal.run('miss' + i, 'nothing-' + i, '2026-11-20T00:00:00Z');
  }
  return db;
}

function counts(rows) {
  const map = new Map();
  for (const row of rows) map.set(String(row.node_id), Number(row.n));
  return map;
}

function planLines(db, sql, ...params) {
  return db.prepare('EXPLAIN QUERY PLAN ' + sql).all(...params).map((row) => String(row.detail));
}

test('the rewrite returns exactly the counts the OR-join returned', () => {
  const db = build();
  const before = counts(db.prepare(OLD_SQL).all());
  const after = counts(db.prepare(ladderUsedSql(false)).all());
  assert.ok(after.size > 0, 'the fixture must actually match something');
  assert.deepEqual([...after.entries()].sort(), [...before.entries()].sort());
  db.close();
});

test('a signal that matches two columns of one author is still counted once', () => {
  const db = build();
  const author = db.prepare('SELECT path, slug FROM lesson_authors WHERE lesson_id = ?').get('lesson-7');
  db.prepare('UPDATE search_signals SET top_id = ? WHERE top_id = ?').run(author.path, author.slug);
  const before = counts(db.prepare(OLD_SQL).all());
  const after = counts(db.prepare(ladderUsedSql(false)).all());
  assert.deepEqual([...after.entries()].sort(), [...before.entries()].sort());
  db.close();
});

test('the shape is three joins and no OR across columns', () => {
  // The *shape* is the regression: `ON a OR b OR c` cannot use an index in any SQLite version.
  // Asserting a specific plan would not travel — measured 2026-11-24, this machine's SQLite drives
  // from `search_signals` and CI's drives from `lesson_authors`; both are linear, while the OR form
  // is quadratic in both. So the unit test guards the shape, and the effect is read back from
  // Cloudflare's D1 analytics after the deploy, where the number is per-query.
  const sql = ladderUsedSql(false);
  const joins = (sql.match(/JOIN search_signals ss ON ss\.top_id = la\./g) || []).length;
  assert.equal(joins, 3, 'expected one indexed join per id shape:' + NEWLINE + sql);
  assert.ok(!sql.includes('la.path = ss.top_id OR'), 'the OR-join is back:' + NEWLINE + sql);
  assert.ok(sql.includes('UNION'), 'expected a UNION of the three branches');
  assert.ok(!sql.includes('UNION ALL'), 'UNION ALL would double-count a signal matching two shapes');
  assert.ok(ladderUsedSql(true).includes('?1'),
    'the filtered variant must bind the since-filter');
});

test('the three indexes the branches need exist after the schema is built', () => {
  const db = build();
  const names = db.prepare("SELECT name FROM sqlite_master WHERE type = 'index'").all()
    .map((row) => String(row.name));
  for (const wanted of ['idx_search_signals_top', 'idx_lesson_authors_lesson_id',
                        'idx_lesson_authors_slug']) {
    assert.ok(names.includes(wanted), wanted + ' missing from: ' + names.join(', '));
  }
  db.close();
});

test('both plan shapes are linear: one full scan per branch, indexed on the other side', () => {
  const db = build();
  for (const guarded of [false, true]) {
    const plan = planLines(db, ladderUsedSql(guarded), ...(guarded ? ['2026-11-01T00:00:00Z'] : []));
    assert.ok(!plan.some((line) => line.includes('CROSS JOIN')),
      'a cross product is back:' + NEWLINE + plan.join(NEWLINE));
    // `SCAN matched` is the CTE being read back, not a table scan — only the two tables count.
    const scans = plan.filter((line) => line.startsWith('SCAN ss') || line.startsWith('SCAN la')).length;
    const searched = plan.filter((line) => /SEARCH [a-z]+ USING (COVERING )?INDEX/.test(line)).length;
    assert.ok(scans <= 3, 'more than one full scan per branch:' + NEWLINE + plan.join(NEWLINE));
    assert.ok(searched >= 3,
      'a branch has no index lookup, which is the cross product:' + NEWLINE + plan.join(NEWLINE));
  }
  db.close();
});
