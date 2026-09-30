// `GET /api/versions` — the machine-readable answer to "which number is which" (intake #2486, decision D5).
//
// Three version channels move independently (release / registry listing / npm bundle) and a plugin market
// shows the *manifest* version while install docs quote the release line, so a reader comparing two numbers
// on one page concluded the page was broken. This endpoint is the comparison: every channel with its source
// and its value read live, plus the capability surface and what was actually verified.
//
// What this file pins: that it is an **aggregator** (it reads the worker's own constant, never a literal), that
// each source degrades to null with the source still named (an endpoint about versions must not fail when one
// of five fetches does), and that the notes which prevent the original misreading are present.
//
// Run: node --test workers/versions-endpoint.test.mjs
import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { buildVersionsPayload, MCP_TOOLS } from './register-proxy-sw.js';

const FULL = {
  serverVersion: '9.9.9',
  npm: { version: '9.9.7' },
  manifest: { version: '9.9.7', mcp: { transport: 'http', tools: ['misakanet_search'] } },
  install: { label: 'install verified', message: 'npm + git+ green', color: 'brightgreen' },
  now: '2026-09-30T00:00:00.000Z',
};

test('every version channel is reported with the source that owns it', () => {
  const p = buildVersionsPayload(FULL);
  assert.equal(p.versions.release.version, '9.9.9');
  assert.equal(p.versions.registry.version, '9.9.9', 'the registry line is bumped with the release');
  assert.equal(p.versions.npm.version, '9.9.7');
  assert.equal(p.versions.plugin_manifest.version, '9.9.7');
  for (const [name, channel] of Object.entries(p.versions)) {
    assert.ok(channel.source, `${name} must name its source`);
  }
  // The two notes that answer the original report: why npm may lag, and which number a market shows.
  assert.match(p.versions.npm.note, /lag|own publish step/i);
  assert.match(p.versions.plugin_manifest.note, /plugin market/i);
  assert.equal(p.generated_at, '2026-09-30T00:00:00.000Z');
});

test('the capability surface comes from the worker itself, not from a copy', () => {
  const p = buildVersionsPayload(FULL);
  assert.deepEqual(p.capabilities.hosted.tools, MCP_TOOLS.map(t => t.name));
  assert.equal(p.capabilities.hosted.tools.length, 7, 'the hosted surface is the worker\'s seven tools');
  assert.equal(p.capabilities.hosted.transport, 'http');
  // …and the manifest's own declaration is passed through untouched, so D4's block is what a reader sees.
  assert.deepEqual(p.capabilities.declared, FULL.manifest.mcp);
  assert.match(p.capabilities.note, /local stdio/i);
});

test('an unreadable source degrades to null with its source named, instead of failing the endpoint', () => {
  const p = buildVersionsPayload({ serverVersion: '9.9.9' });
  assert.equal(p.versions.npm.version, null);
  assert.match(p.versions.npm.source, /registry\.npmjs\.org/);
  assert.ok(p.versions.npm.note, 'a null must say why it is null');
  assert.equal(p.versions.plugin_manifest.version, null);
  assert.equal(p.capabilities.declared, null);
  assert.equal(p.verification.real_install.message, null);
  assert.match(p.verification.real_install.note, /unproven|no published smoke/i);
  // A manifest without the block (before D4 lands) must not throw either.
  assert.doesNotThrow(() => buildVersionsPayload({ serverVersion: '1.0.0', manifest: {} }));
});

test('the two verification layers are described as different claims', () => {
  const p = buildVersionsPayload(FULL);
  assert.match(p.verification.real_install.source, /badges\/install\.json/);
  assert.match(p.verification.registry_metadata.note, /does not prove/i);
});

test('GET /api/versions answers 200 even when every upstream fetch fails', async () => {
  // No durable store and no network in this test: the handler must still answer, with nulls.
  const env = { MCP_VERSION: '8.8.8' };
  const resp = await worker.fetch(new Request('https://misakanet.org/api/versions'), env);
  assert.equal(resp.status, 200);
  const body = await resp.json();
  assert.equal(body.versions.release.version, '8.8.8', 'the release line is the worker\'s own constant');
  assert.equal(body.capabilities.hosted.tools.length, 7);
  assert.ok(body.generated_at, JSON.stringify(body).slice(0, 200));
});
