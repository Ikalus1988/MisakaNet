// Unit tests for the PR Genius statistics endpoint (Issue #1035).
import assert from 'node:assert/strict';
import test from 'node:test';

import worker, {
  handlePrGeniusStats,
} from './register-proxy.js';

test('handlePrGeniusStats returns statistics from mock GitHub data', async () => {
  const mockEnv = {
    REGISTER_TOKEN: 'fake-token',
    MISAKANET_KV: null,
  };

  const payload = {
    repo: "Ikalus1988/MisakaNet",
    summary: { total_observed_runs: 100, all_time_success_rate: 96.0 },
    windows: {
      all_time: { total_runs: 100, success_rate: 96.0, failure_rate: 4.0 }
    }
  };

  const base64Content = Buffer.from(JSON.stringify(payload)).toString("base64");

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    return {
      ok: true,
      status: 200,
      json: async () => ({
        content: base64Content,
        encoding: "base64"
      })
    };
  };

  try {
    const res = await handlePrGeniusStats(mockEnv);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.repo, 'Ikalus1988/MisakaNet');
    assert.equal(body.summary.all_time_success_rate, 96.0);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
