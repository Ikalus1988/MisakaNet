// Would the corpus have answered this submission? Measured at submit time, acted on by nobody.
//
// The queue grows ~35 filed a day against ~2 triaged on a quiet day, and every account of that gap
// ends at the same place: the one moment the endpoint holds both the submission and the corpus is
// before the issue exists. Refusing on a hit is a behaviour change with no data behind it, so
// 2026-11-18 records the answer instead — the share of new intakes whose text already matched a
// lesson is the number that decides whether a submit-side gate is worth building.
//
// The probe complements a gate that already exists: `findCoveringLesson` (#1526) refuses a
// `missing_lesson` whose text a lesson already covers near-verbatim, and does **not** look at
// `question` at all — which is the queue that actually piles up (171 open `needs-answer` on
// 2026-11-18). The probe therefore measures every filing, not just the kind that has a gate.
//
// Two properties, because a measurement can be wrong in two directions:
//   * a real match is counted (not silently zero), and
//   * "could not measure" (-1, cold isolate, no index) never reads as "no match" (0).
//
// Run: node --test workers/intake-coverage-probe.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { buildBM25Index, measureIntakeCoverage } from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const LESSONS = [{
  id: 'pip-timeout-mirror',
  title: 'pip install timeout behind a corporate proxy',
  description: 'pip install times out behind a corporate proxy; point it at the internal mirror.',
  domain: 'python',
  tags: ['pip', 'proxy', 'timeout', 'mirror'],
  path: 'lessons/core/pip-timeout-mirror.md',
  status: 'published',
  summary_plain: 'pip install times out behind a corporate proxy because the index is unreachable.',
  trigger: 'pip install timeout corporate proxy mirror',
}];

test('a submission the corpus already answers is counted', () => {
  const index = buildBM25Index(LESSONS);
  const hits = measureIntakeCoverage('pip install timeout behind corporate proxy', index);
  assert.ok(hits >= 1, `expected the existing lesson to be found, got ${hits}`);
});

test('a submission nothing covers counts zero — not "could not measure"', () => {
  const index = buildBM25Index(LESSONS);
  assert.equal(measureIntakeCoverage('webgl context lost on a second canvas attach in safari', index), 0);
});

test('a cold isolate says "could not measure", which is not zero', () => {
  assert.equal(measureIntakeCoverage('pip install timeout', null), -1);
  assert.equal(measureIntakeCoverage('', buildBM25Index(LESSONS)), -1);
});

test('the intake still files, and the point records the probe', async () => {
  const TOKEN = testToken('intake-coverage-probe');
  const points = [];
  const store = new Map([['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })]]);
  const env = {
    MCP_TOKEN: TOKEN,
    REGISTER_TOKEN: TOKEN,
    MCP_VERSION: 'intake-coverage-probe',
    EVENTS: { writeDataPoint: (p) => points.push(p) },
    MISAKANET_KV: {
      async get(key, type) {
        if (!store.has(key)) return null;
        const raw = store.get(key);
        return type === 'json' ? JSON.parse(raw) : raw;
      },
      async put(key, value) { store.set(key, value); },
      async delete(key) { store.delete(key); },
    },
  };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({
    number: 990, html_url: 'https://github.com/Ikalus1988/MisakaNet/issues/990',
  }), { status: 201, headers: { 'content-type': 'application/json' } });
  let payload;
  try {
    const pending = [];
    const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'MCP-Protocol-Version': '2025-06-18',
        Origin: 'https://misakanet.org',
        'CF-Connecting-IP': '198.51.100.9',
        Authorization: `Bearer ${TOKEN}`,
      },
      body: JSON.stringify({
        jsonrpc: '2.0', id: 1, method: 'tools/call',
        params: {
          name: 'misakanet_submit_intake',
          arguments: {
            kind: 'missing_lesson',
            problem: 'webgl context lost on the second canvas attach in safari 17',
            error: 'WebGL: CONTEXT_LOST_WEBGL',
            source: 'mcp',
          },
        },
      }),
    }), env, { waitUntil: (p) => pending.push(Promise.resolve(p)) });
    await Promise.all(pending);
    const body = await response.json();
    payload = JSON.parse(body.result.content[0].text);
  } finally {
    globalThis.fetch = originalFetch;
  }
  assert.equal(payload.submitted, true, JSON.stringify(payload));
  assert.equal(points.length, 1, JSON.stringify(points));
  const [point] = points;
  assert.equal(point.blobs[0], 'misakanet_submit_intake');
  assert.equal(point.doubles[1], -1, 'no index loaded in this isolate: "could not measure", not 0');
  assert.equal(point.doubles[2], 0, 'the dedup flag keeps its slot');
});
