// The AI Gateway is a var-gated hop on the serving embedding call (2026-10-31).
//
// The gateway `misakanet-bench` existed since 2026-08-28 and had seen nothing since 2026-10-12, because
// only the paused benchmark pointed at it while production called `env.AI` directly. Wiring it is one
// option object — which means the risk is exactly one option object: an unset var must leave the call
// identical to yesterday's, or a dashboard value that nobody set would change production behaviour.
import test from 'node:test';
import assert from 'node:assert/strict';

import { semanticFallbackHits } from './register-proxy-sw.js';

function fakeEnv({ gateway, vector = [0.1, 0.2] } = {}) {
  const calls = [];
  const env = {
    AI: {
      async run(model, input, options) {
        calls.push({ model, input, options });
        return { data: [new Array(1024).fill(0.01)] };
      },
    },
    VECTORIZE: {
      async query(_vector, _opts) {
        return { matches: [] };
      },
    },
  };
  if (gateway !== undefined) env.MISAKANET_AI_GATEWAY = gateway;
  void vector;
  return { env, calls };
}

test('an unset gateway var leaves the embedding call exactly as it was', async () => {
  const { env, calls } = fakeEnv();
  await semanticFallbackHits(env, 'pip install timeout');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options, undefined, 'the direct call passes no third argument');
  assert.deepEqual(calls[0].input, { text: ['pip install timeout'] });
});

test('an empty or whitespace gateway var is the same as unset', async () => {
  for (const value of ['', '   ']) {
    const { env, calls } = fakeEnv({ gateway: value });
    await semanticFallbackHits(env, 'q');
    assert.equal(calls[0].options, undefined, `gateway var ${JSON.stringify(value)} must not add an option`);
  }
});

test('a set gateway var adds exactly one option and nothing else', async () => {
  const { env, calls } = fakeEnv({ gateway: 'misakanet-bench' });
  await semanticFallbackHits(env, 'pip install timeout');
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].options, { gateway: { id: 'misakanet-bench' } });
  assert.deepEqual(calls[0].input, { text: ['pip install timeout'] });
});

test('the gateway does not turn a failing call into a result', async () => {
  const env = {
    MISAKANET_AI_GATEWAY: 'misakanet-bench',
    AI: { async run() { throw new Error('gateway unavailable'); } },
    VECTORIZE: { async query() { return { matches: [] }; } },
  };
  await assert.rejects(() => semanticFallbackHits(env, 'q'), /gateway unavailable/);
});
