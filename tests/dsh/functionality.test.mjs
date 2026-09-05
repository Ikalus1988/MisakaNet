// dsh MCP functionality tests against the real stdio server.
// Run: node --test tests/dsh/functionality.test.mjs
import assert from 'node:assert/strict';
import path from 'node:path';
import test from 'node:test';

import { contentJson, firstPublishedLessonPath, McpStdioClient } from './dsh-test-helpers.mjs';

async function withClient(fn) {
  const client = new McpStdioClient();
  try {
    await fn(client);
  } finally {
    await client.close();
  }
}

test('MCP initialize and tool discovery expose MisakaNet tools to dsh clients', async () => {
  await withClient(async (client) => {
    const init = await client.request('initialize');
    assert.equal(init.result.serverInfo.name, 'misakanet');
    assert.ok(init.result.protocolVersion);
    assert.ok(init.result.capabilities.tools);
    assert.ok(init.result.capabilities.resources);

    const list = await client.request('tools/list');
    const tools = list.result.tools;
    const names = new Set(tools.map((tool) => tool.name));
    assert.ok(names.has('misakanet_search'));
    assert.ok(names.has('misakanet_get_lesson'));

    const search = tools.find((tool) => tool.name === 'misakanet_search');
    assert.deepEqual(search.inputSchema.required, ['query']);
    assert.equal(search.inputSchema.properties.detail.enum.includes('compact'), true);
  });
});

test('misakanet_search executes through JSON-RPC and returns structured content', async () => {
  await withClient(async (client) => {
    const response = await client.request('tools/call', {
      name: 'misakanet_search',
      arguments: { query: 'DCO sign-off failed', top: 3, detail: 'compact' },
    });
    const payload = contentJson(response);
    assert.ok(
      Array.isArray(payload.results) || payload.no_match === true || typeof payload.error === 'string',
      `unexpected search payload: ${JSON.stringify(payload)}`,
    );
  });
});

test('misakanet_get_lesson reads a real published lesson by path', async () => {
  await withClient(async (client) => {
    const lessonPath = firstPublishedLessonPath();
    const response = await client.request('tools/call', {
      name: 'misakanet_get_lesson',
      arguments: { path: lessonPath },
    });
    const payload = contentJson(response);
    assert.equal(payload.path.replaceAll('\\', '/'), lessonPath);
    assert.equal(typeof payload.content, 'string');
    assert.ok(payload.content.length > 20);
  });
});

test('misaka://lessons/index resource is discoverable and readable', async () => {
  await withClient(async (client) => {
    const listed = await client.request('resources/list');
    const resources = listed.result.resources;
    assert.ok(resources.some((resource) => resource.uri === 'misaka://lessons/index'));

    const read = await client.request('resources/read', { uri: 'misaka://lessons/index' });
    const text = read.result.contents[0].text;
    const payload = JSON.parse(text);
    assert.ok(Array.isArray(payload.lessons));
    assert.equal(payload.lessons.length, payload.count);
    assert.ok(payload.lessons.length > 0);
  });
});

test('tool and resource error handling is explicit and non-crashing', async () => {
  await withClient(async (client) => {
    const unknownTool = await client.request('tools/call', { name: 'definitely_not_a_tool', arguments: {} });
    assert.equal(unknownTool.error.code, -32601);
    assert.match(unknownTool.error.message, /Unknown tool/);

    const missingLesson = await client.request('tools/call', {
      name: 'misakanet_get_lesson',
      arguments: { id: 'not-a-real-lesson-id-for-dsh-tests' },
    });
    assert.match(contentJson(missingLesson).error, /Lesson not found/);

    const missingResource = await client.request('resources/read', { uri: 'misaka://missing/resource' });
    const missingResourcePayload = JSON.parse(missingResource.result.contents[0].text);
    assert.match(missingResourcePayload.error, /Unknown resource/);
  });
});
