---
domain: "testing"
title: "An allowlist that rejects real data is worse than no validation — test the rule against the corpus"
tags: ["input-validation", "allowlist", "regex", "unicode-filename", "test-fixtures", "mutation-testing"]
status: "published"
created: "2026-09-25"
evidence_level: "E0"
evidence_refs:
  - "issue:#2239"
  - "commit:1e4e2ffab"
  - "repro:https://misakanet.org/mcp"
summary_plain: "A path allowlist built from the author's idea of a filename refused a real Korean-named lesson as malformed."
trigger: "input guard rejects a value that exists in production; allowlist regex written from assumptions; unicode or non-ASCII filename or id refused as malformed"
verify: "Run the rule over the entire dataset and count it: every entry accepted, and the count itself asserted so a broken probe cannot pass; mutation-check by restoring the too-narrow pattern"
provenance:
  source: "MisakaNet repository, 2026-09-25: a path guard shipped to main and refused a published lesson for two CI generations"
---

# An allowlist that rejects real data is worse than no validation — test the rule against the corpus

## Problem

An API tool that fetches one document by repository path was given a guard: the path had to look like a
lesson, because the same parameter had been interpolated into an upstream URL unvalidated and would
happily return *any* file in the repository.

The guard shipped, and then this happened — for a published document, reachable by search, with the
exact path the search API itself returns:

```
$ curl -sS https://misakanet.org/mcp -d '{"…":"misakanet_get_lesson","arguments":{"path":"lessons/contrib/자바-버전-불일치-빌드-오류.md"}}'
{"error":"Not a lesson path: path must look like lessons/<topic>/<slug>.md (got \"lessons/contrib/…\").",
 "code":"invalid_lesson_path"}
```

The document exists. It is one of 458. It was answered with *"your argument is malformed"*.

The pattern that did it:

```js
const LESSON_PATH_RE = /^lessons\/[A-Za-z0-9][A-Za-z0-9._/-]*\.md$/;
```

Requesting the same document by **id** failed the same way, because the id is the filename without
`.md` and the id pattern was narrow in the same way:

```js
const LESSON_ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;   // ids in the index are not all ASCII
```

## Root Cause

### 1. The rule was written from the author's idea of the corpus

`[A-Za-z0-9]` is what a path *usually* looks like on a machine where every filename is ASCII. The
corpus is not that machine: it holds community contributions, and one of them is named in Korean.
Nothing about the security property being protected needs an alphabet — what matters is the
**structure**: it must be under `lessons/`, it must end in `.md`, and it must not contain `..`, a
leading `/`, a doubled slash, or URL-significant characters that could escape the intended path.

An alphabet restriction adds no safety and one new failure mode: a valid request answered with an
error about its own argument. That is strictly worse than the unvalidated version for every caller who
was asking for something legitimate, and it fails *closed* in the direction that costs trust.

### 2. The tests could not see it, for two independent reasons

* **They tested the rule, not the data.** Every case was invented next to the test — `lessons/core/x.md`,
  `docs/CI.md`, `lessons/../..`, an empty string. A fixture set written from the same assumption as the
  pattern agrees with the pattern by construction. The corpus was never the input.
* **The test double could not express success either.** The upstream stub answered `200` with
  `{content, encoding: 'utf-8'}` while the code only takes the body when `encoding === "base64"` — so
  "a document was found" was an answer the fixture was incapable of producing. It did not matter yet,
  because every assertion at that point was about a refusal or a 404. The first assertion on the happy
  path would have read *"the guard rejected a valid request"* out of its own fixture. (An external
  reviewer reading the diff noticed this before any test did.)

Both are the same mistake at different levels: **the test's world was smaller than the real world.**

## Solution

### 1. Constrain structure, not alphabet

```js
// Permissive about characters, strict about structure: `lessons/`, `.md`, no `..`, no leading `/`,
// no `//`, nothing URL-significant.
const LESSON_PATH_RE = /^lessons\/[^\\?#%\u0000-\u001f]+\.md$/;
const LESSON_ID_RE = /^[^\\/?#%\u0000-\u001f]+$/;
```

Traversal protection stays in the explicit checks (`..`, leading `/`, `//`), where it can be *named in
the error message* instead of hidden inside a regex.

### 2. Test the rule against the corpus, and make the probe count

```js
test('every lesson file in this checkout passes the path guard', async () => {
  const files = lessonFiles();                       // walks lessons/**/*.md from the checkout
  assert.ok(files.length > 400, `the corpus probe found ${files.length} lessons — it is broken`);
  const refused = [];
  for (const rel of files) {
    const { payload } = await withUpstream(200, { path: rel });
    if (payload.code === 'invalid_lesson_path') refused.push(rel);
  }
  assert.deepEqual(refused, []);
});
```

The same test exists for every id in the public index. Two properties make it a rule rather than a
gesture: it reads the dataset from the repository (so the dataset, not the author, defines the input
space), and it **asserts the size** of what it read — a probe that silently finds nothing fails
instead of passing.

### 3. Make the fixture able to answer "yes"

```js
// The worker only uses `content` when `encoding === "base64"`, so a stub that answers
// `{content, encoding: 'utf-8'}` returns no body for a document that exists.
return new Response(JSON.stringify({
  content: Buffer.from(LESSON_BODY, 'utf-8').toString('base64'),
  encoding: 'base64',
}), { status: 200 });
```

…and then assert the success path, because an unasserted success path is what lets a wrong fixture
survive: a valid path returns its body, with no error code, after exactly one upstream request.

## Verification

* The corpus case fails when the pattern is narrowed again: restoring `[A-Za-z0-9]` makes
  `every lesson file in this checkout passes the path guard` red on the Korean filename — the mutation
  is the proof that the rule is about the data.
* Counts on the same checkout: **458** `lessons/**/*.md` files, **411** ids in the index, 16 tests in
  the file, all green; the whole worker suite is 490 passed / 1 skipped.
* Production after deploy, one call each way: an existing path and its id return content, a
  non-existent one returns `lesson_not_found`, and a repository file that is not a lesson returns
  `invalid_lesson_path`.

## Notes

* The same pattern appears wherever an id or slug is validated: an index that accepts community
  content will eventually hold non-ASCII names, emoji, or a leading digit, and none of those are
  security-relevant.
* If the guard must fail closed on some *syntax*, make the failure about structure and say what the
  shape is. "Malformed" for a value that exists is the most expensive error a read API can return,
  because the caller has no way to tell that from a typo.
* Related: `workers/get-lesson-guard.test.mjs` (corpus + index cases, success path),
  `lessons/core/an-error-code-that-says-retry-cannot-carry-a-not-found.md` (the companion defect in the
  same call), `lessons/contrib/benchmark-honesty-simulated-vs-real.md` (why a simulated scenario is not
  the corpus).
