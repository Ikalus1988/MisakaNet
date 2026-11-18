// "Is the plugin I am talking to current?" — the endpoint's half of intake #5185 (2026-11-17).
//
// The plugin knows its own version and says it in its first-run announcement. What it cannot know is
// whether that number is behind, because only the publisher knows what has been published — and the
// two channels carry deliberately different numbers (`.cindy-plugin` 1.6.2 vs
// `.cindy-plugin-community` 1.5.11), so "the latest" is not one number.
//
// What this file pins, and why each one is worth a test:
//   * the comparison is numeric per segment — "1.5.11" is newer than "1.5.9", which a string compare
//     gets backwards, and the whole `outdated` flag rests on it;
//   * an absent `cindy:plugin:latest` means the endpoint says *nothing* about being behind, not
//     "you are current". The repository's manifest is ahead of the marketplace during a review, so a
//     compiled-in default would nag marketplace users who are up to date;
//   * an unknown channel never picks one of the two to compare against;
//   * a caller that is not the plugin carries no `plugin_version` at all.
//
// Run: node --test workers/cindy-plugin-version.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import { comparePluginVersions, describePluginVersion, readPublishedPluginVersion } from './register-proxy-sw.js';

function kv(store, { throws = false } = {}) {
  return {
    async get(key, type) {
      if (throws) throw new Error('kv unavailable');
      if (!(key in store)) return null;
      const value = store[key];
      return type === 'json' ? value : JSON.stringify(value);
    },
    async put() {},
  };
}

const LATEST = { 'cindy:plugin:latest': { community: '1.5.11', official: '1.6.2' } };

test('the comparison is numeric per segment, not lexical', () => {
  assert.equal(comparePluginVersions('1.5.9', '1.5.11'), -1, '"1.5.9" < "1.5.11" is what a string compare gets wrong');
  assert.equal(comparePluginVersions('1.5.11', '1.5.9'), 1);
  assert.equal(comparePluginVersions('1.6.2', '1.5.11'), 1);
  assert.equal(comparePluginVersions('1.5.11', '1.5.11'), 0);
  assert.equal(comparePluginVersions('v1.5.11', '1.5.11'), 0, 'a leading v is the same release');
});

test('an unparseable version makes no claim instead of guessing', () => {
  assert.equal(comparePluginVersions('', '1.5.11'), 0);
  assert.equal(comparePluginVersions('local', '1.5.11'), 0);
  assert.equal(comparePluginVersions('1.5', '1.5.0'), 0);
});

test('a behind community build is told so, with both numbers', async () => {
  const described = await describePluginVersion(
    { MISAKANET_KV: kv(LATEST) },
    { agent: 'cindy', channel: 'community', client_version: '1.5.9' },
  );
  assert.deepEqual(described, { channel: 'community', current: '1.5.9', latest: '1.5.11', outdated: true });
});

test('the official channel is compared against its own number, not the community one', async () => {
  const described = await describePluginVersion(
    { MISAKANET_KV: kv(LATEST) },
    { agent: 'cindy', channel: 'official', client_version: '1.5.9' },
  );
  assert.equal(described.latest, '1.6.2');
  assert.equal(described.outdated, true);
});

test('a current build is not nagged', async () => {
  const described = await describePluginVersion(
    { MISAKANET_KV: kv(LATEST) },
    { agent: 'cindy', channel: 'community', client_version: '1.5.11' },
  );
  assert.equal(described.outdated, false);
});

test('an unwritten key means silence, not "you are current"', async () => {
  for (const store of [{}, { 'cindy:plugin:latest': { community: '1.5.11' } }]) {
    const described = await describePluginVersion(
      { MISAKANET_KV: kv(store) },
      { agent: 'cindy', channel: 'official', client_version: '1.5.9' },
    );
    assert.equal('latest' in described, false, 'nothing was recorded for this channel, so nothing is claimed');
    assert.equal('outdated' in described, false, 'without a latest there is no verdict to give');
    assert.equal(described.channel, 'official');
  }
});

test('a KV failure is silence too, not an error in the search result', async () => {
  const described = await describePluginVersion(
    { MISAKANET_KV: kv({}, { throws: true }) },
    { agent: 'cindy', channel: 'community', client_version: '1.5.9' },
  );
  assert.deepEqual(described, { channel: 'community', current: '1.5.9' });
});

test('a caller that is not the plugin is not described at all', async () => {
  for (const args of [{}, { agent: 'claude-code', channel: 'community', client_version: '1.5.9' }, { agent: 'cindy' }]) {
    const described = await describePluginVersion({ MISAKANET_KV: kv(LATEST) }, args);
    if (args.agent === 'cindy') {
      assert.deepEqual(described, { channel: '', current: '' }, 'no channel: no comparison to make');
    } else {
      assert.equal(described, null);
    }
  }
});

test('an unknown channel never borrows another channel\'s number', async () => {
  const described = await describePluginVersion(
    { MISAKANET_KV: kv(LATEST) },
    { agent: 'cindy', channel: 'file-install', client_version: '1.5.9' },
  );
  assert.equal(described.channel, '', 'the channel is a closed set: community | official');
  assert.equal('latest' in described, false);
});

test('the reader ignores a stored value that is not an object', async () => {
  assert.equal(await readPublishedPluginVersion({ MISAKANET_KV: kv({ 'cindy:plugin:latest': '1.6.2' }) }, 'official'), '');
  assert.equal(await readPublishedPluginVersion({ MISAKANET_KV: kv({ 'cindy:plugin:latest': { official: 162 } }) }, 'official'), '');
});

// ── the wiring: a real `tools/call` through the worker ───────────────────────────────────────────
// The helpers above are pure; these two drive the same path the plugin does, because a spread in the
// wrong envelope is exactly the kind of change that passes a unit test and ships a field nobody sees.
import worker from './register-proxy-sw.js';
import { testToken } from './_test-token.mjs';

const TOKEN = testToken('cindy-plugin-version');
const QUERY = 'pip install timeout on a corporate proxy';
const LESSONS = [{
  id: 'pip-timeout-mirror',
  title: 'pip install timeout',
  description: 'pip install times out on slow networks; use a mirror.',
  domain: 'python',
  tags: ['pip', 'network'],
  path: 'lessons/core/pip-timeout-mirror.md',
  status: 'published',
}];

function searchEnv(extra = {}) {
  const store = new Map([
    ['proxy:lessons', JSON.stringify({ ts: Date.now(), data: LESSONS })],
    ...Object.entries(extra),
  ]);
  return {
    env: {
      MCP_TOKEN: TOKEN,
      REGISTER_TOKEN: TOKEN,
      MCP_VERSION: 'cindy-plugin-version-test',
      MISAKANET_KV: {
        async get(key, type) {
          if (!store.has(key)) return null;
          const raw = store.get(key);
          return type === 'json' ? JSON.parse(raw) : raw;
        },
        async put(key, value) { store.set(key, value); },
        async delete(key) { store.delete(key); },
      },
    },
    store,
  };
}

/** One `misakanet_search` call; `headers` is how the plugin sends its self-declared context. */
async function search(env, { args = {}, headers = {} } = {}) {
  const pending = [];
  const response = await worker.fetch(new Request('https://misakanet.org/mcp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'MCP-Protocol-Version': '2025-06-18',
      Origin: 'https://misakanet.org',
      'CF-Connecting-IP': '198.51.100.7',
      Authorization: `Bearer ${TOKEN}`,
      ...headers,
    },
    body: JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'tools/call',
      params: { name: 'misakanet_search', arguments: { query: QUERY, top: 3, ...args } },
    }),
  }), env, { waitUntil: (promise) => pending.push(Promise.resolve(promise)) });
  await Promise.all(pending);
  const body = await response.json();
  assert.equal(body.error, undefined, `unexpected MCP error: ${JSON.stringify(body.error)}`);
  return JSON.parse(body.result.content[0].text);
}

test('the field reaches the plugin through the headers it actually sends', async () => {
  const latest = JSON.stringify({ community: '1.5.11', official: '1.6.2' });
  const { env } = searchEnv({ 'cindy:plugin:latest': latest });
  const payload = await search(env, {
    headers: {
      'X-MisakaNet-Agent': 'cindy',
      'X-MisakaNet-Version': '1.5.9',
      'X-MisakaNet-Channel': 'community',
    },
  });
  assert.deepEqual(payload.plugin_version,
    { channel: 'community', current: '1.5.9', latest: '1.5.11', outdated: true }, JSON.stringify(payload));
});

test('a no_match answer carries it too — that is where an old build hurts most', async () => {
  const latest = JSON.stringify({ community: '1.5.11', official: '1.6.2' });
  const { env } = searchEnv({ 'cindy:plugin:latest': latest });
  const payload = await search(env, {
    args: { query: 'zzz-no-such-topic-anywhere-999' },
    headers: { 'X-MisakaNet-Agent': 'cindy', 'X-MisakaNet-Version': '1.5.9', 'X-MisakaNet-Channel': 'community' },
  });
  assert.equal(payload.no_match, true);
  assert.equal(payload.plugin_version.outdated, true);
});

test('every other caller\'s search answer is unchanged, key for key', async () => {
  const { env } = searchEnv({ 'cindy:plugin:latest': JSON.stringify({ community: '1.5.11' }) });
  const payload = await search(env, { headers: { 'X-MisakaNet-Agent': 'claude-code', 'X-MisakaNet-Version': '1.0.0' } });
  assert.equal('plugin_version' in payload, false, 'a non-plugin caller must not pay for or see this');
});

test('an unknown channel header is dropped instead of picking a number', async () => {
  const { env } = searchEnv({ 'cindy:plugin:latest': JSON.stringify({ community: '1.5.11', official: '1.6.2' }) });
  const payload = await search(env, {
    headers: { 'X-MisakaNet-Agent': 'cindy', 'X-MisakaNet-Version': '1.5.9', 'X-MisakaNet-Channel': 'file-install' },
  });
  assert.deepEqual(payload.plugin_version, { channel: '', current: '1.5.9' }, JSON.stringify(payload.plugin_version));
});
