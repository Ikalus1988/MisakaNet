// `/api/health`'s `commit_sha` (#2779).
//
// Why this field exists: `serverInfo.version` cannot answer "is production current?". release-please
// bumps it only on a release, so across every `fix:`/`feat:` commit production and main keep
// reporting the same version — measured live on 2026-10-03, when production was days behind and both
// read 2.40.0. A version that only moves on release cannot see a stale deploy.
//
// Why it is a function and not a literal: the interesting cases are the ones that do NOT come from
// CI. `make deploy-api` deploys locally and knows no commit; a wrangler var left at its wrangler.toml
// default says "unknown"; a mis-set var could carry anything at all. All of those have to read as
// *unverifiable* rather than as a deployment record, and the only way to know that is to assert it
// against the same helper the endpoint calls.
import assert from 'node:assert/strict';
import test from 'node:test';
import { deployedCommit } from './register-proxy-sw.js';

test('a real commit SHA is reported, lowercased', () => {
  const sha = 'a'.repeat(40);
  assert.equal(deployedCommit({ COMMIT_SHA: sha }), sha);
  assert.equal(deployedCommit({ COMMIT_SHA: 'A1B2C3D4'.repeat(5) }), 'a1b2c3d4'.repeat(5));
  // Surrounding whitespace comes from shell quoting in `wrangler deploy --var COMMIT_SHA:"${GITHUB_SHA}"`,
  // so tolerating it is the difference between a working freshness check and a permanently-unknown one.
  assert.equal(deployedCommit({ COMMIT_SHA: `  ${sha}\t` }), sha);
});

test('a deploy that carries no SHA reads as unknown, not as absent', () => {
  // `make deploy-api`, and the wrangler.toml default, both land here. The field still has to be
  // present: monitors read this endpoint, and a missing key is indistinguishable from a build that
  // predates the field — which would read as "stale" when the truth is "we cannot tell".
  assert.equal(deployedCommit({}), "unknown");
  assert.equal(deployedCommit({ COMMIT_SHA: "" }), "unknown");
  assert.equal(deployedCommit({ COMMIT_SHA: "   " }), "unknown");
  assert.equal(deployedCommit(), "unknown");
});

test('anything that is not a commit SHA is refused', () => {
  // A truncated, abbreviated, or templated var is the failure mode that would otherwise poison
  // `doctor.py --deploy-freshness`: it would compare a non-SHA against HEAD and report a confident,
  // wrong answer. Better that it falls back to "cannot be verified".
  for (const bad of ["unknown", "HEAD", "main", "${GITHUB_SHA}", "a".repeat(39), "a".repeat(41),
                     "a".repeat(39) + "z", "e04084785 deadbeef"]) {
    assert.equal(deployedCommit({ COMMIT_SHA: bad }), "unknown", `accepted ${JSON.stringify(bad)}`);
  }
});

test('a non-string var cannot produce a string-shaped lie', () => {
  for (const bad of [null, undefined, 42, {}, [], true]) {
    assert.equal(deployedCommit({ COMMIT_SHA: bad }), "unknown", `accepted ${String(bad)}`);
  }
});
