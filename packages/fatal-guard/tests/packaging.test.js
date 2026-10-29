// What npm actually ships has to be able to run.
//
// Measured 2026-10-29: `@misaka-net/fatal-guard@0.3.1` was published and **could not start** —
//
//   Error: Cannot find module './src/lib/spawn-command'
//
// `index.js` requires it, `package.json`'s `files` listed `src/lib/redact.js` and
// `src/lib/resolve-handler.js` but not `spawn-command.js`, so every `npx` run died at require time.
// 0.3.0 had the same hole, which is a large part of why the package had zero recorded uses: it was
// not that nobody needed it, it was that nobody could run it.
//
// Nothing could see this. The test suite runs from the source tree, where every file exists. The
// release workflow builds a tarball and publishes it without ever requiring the entry point from
// inside that tarball. So the one artefact users get was the one artefact no test touched.
//
// This test walks the require graph from the shipped entry points and checks every relative target
// against `files`. It is deliberately a *packaging* check rather than a smoke test: it needs no npm,
// no network and no tarball, so it runs on every `npm test`.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const ROOT = path.join(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));

// Entry points npm exposes: the package main, the register helper, and the CLI bin.
const ENTRIES = [manifest.main || 'index.js', 'register.js']
  .concat(Object.values(manifest.bin || {}));

/** Does `files` cover this repo-relative path? Exact names and directory prefixes, as npm reads it. */
function shipped(relPath) {
  // `bin` values are written `./bin/fatal-guard.js` and `files` entries are not; both name the same
  // file, so the comparison normalises the leading `./` rather than assuming one spelling.
  const normalised = relPath.split(path.sep).join('/').replace(/^\.\//, '');
  return (manifest.files || []).some((entry) => {
    if (entry.endsWith('/')) return normalised.startsWith(entry);
    return normalised === entry;
  });
}

/** Every relative `require('./…')`, transitively, starting from the entry points. */
function requireGraph(entries) {
  const seen = new Set();
  const queue = entries.map((entry) => entry.split(path.sep).join('/').replace(/^\.\//, ''));
  while (queue.length) {
    const rel = queue.shift();
    if (seen.has(rel)) continue;
    seen.add(rel);
    const source = fs.readFileSync(path.join(ROOT, rel), 'utf8');
    for (const match of source.matchAll(/require\(\s*['"](\.{1,2}\/[^'"]+)['"]\s*\)/g)) {
      const resolved = path
        .join(path.dirname(rel), match[1])
        .split(path.sep).join('/');
      const withExt = [resolved, `${resolved}.js`, `${resolved}/index.js`]
        .find((candidate) => fs.existsSync(path.join(ROOT, candidate)));
      assert.ok(withExt, `${rel} requires '${match[1]}', which does not exist in the repository`);
      queue.push(withExt);
    }
  }
  return [...seen];
}

test('every file the entry points require is listed in package.files', () => {
  const missing = requireGraph(ENTRIES).filter((rel) => !shipped(rel));
  assert.deepEqual(missing, [],
    'these files are required at runtime but npm would not publish them — the package would fail '
    + 'with MODULE_NOT_FOUND on install — which is how the last two published versions shipped');
});

test('the CLI bin is shipped, and it is the one package.json points at', () => {
  for (const [name, rel] of Object.entries(manifest.bin || {})) {
    assert.ok(fs.existsSync(path.join(ROOT, rel)), `bin ${name} points at ${rel}, which does not exist`);
    assert.ok(shipped(rel), `bin ${name} (${rel}) is not in package.files`);
  }
});

test('the declared main is shipped', () => {
  assert.ok(shipped(manifest.main || 'index.js'),
    `main '${manifest.main}' is not in package.files — require('@misaka-net/fatal-guard') would fail`);
});
