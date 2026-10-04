// Submitted text is the deliverable on every path, and it was being sheared at 2,000
// characters with no marker — the same defect `scripts/intake_pipeline.py` documents for
// itself in `_clip_question`, thirty times under the cap it uses.
//
// Measured on `main` at 206d7214d, from #2774:
//
//     submitted 1,668 chars  → GitHub received 2,583  (full body + ~915 wrapper)
//     submitted 22,690 chars → GitHub received 2,915  (= 2,000 body + 915 wrapper)
//
// The second line is the bug: a 22,690-character failure report became a tidy 2,000-character
// report that read as complete. Nothing errored, nothing was marked, and the evidence that
// made the report worth filing was simply gone.
//
// Two writes shared the limit, and both had to be fixed. `redactIntake` builds the issue body;
// `recordQuestion` writes the D1 `questions.problem` row. Fixing only the first would have left
// the durable record truncated — the issue would look whole and the row behind it would not be,
// which is the harder half of the problem to notice.
//
// The Python path's cap is `QUESTION_BODY_CAP = 60_000`, chosen for GitHub's 65,536-character
// issue-body limit. The worker uses the same number, so both halves of one submission agree.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { clipSubmittedText, redactIntake, redactSecrets, SUBMITTED_TEXT_CAP } from './register-proxy-sw.js';

test('a long intake survives the cap that used to destroy it', () => {
  // The exact shape from #2774. At the old 2,000 cap this arrived as 2,000 characters and
  // nothing said so — well under the 60,000 GitHub allows, so the cap should not touch it
  // at all and the body should come through whole.
  const body = 'F'.repeat(22690);
  const out = clipSubmittedText(body, "a lesson");
  assert.equal(out.length, 22690, 'a 22,690-character report must not be cut at 2,000');
  assert.equal(out, body, 'and must arrive unmodified, with no truncation marker');
  assert.ok(!out.includes('Truncated'), 'nothing was truncated, so nothing may claim it was');
});

test('a short intake is passed through byte for byte', () => {
  const body = 'a technician reported a servo following error at 12:04\n';
  assert.equal(clipSubmittedText(body, "a lesson"), body);
});

test('when the cap does bite it says so', () => {
  // The whole point: a well-formed issue that quietly lost its evidence is the one thing
  // nobody suspects (#2743). Silence is the defect, not the cut.
  const out = clipSubmittedText('x'.repeat(SUBMITTED_TEXT_CAP + 500), "a lesson");
  assert.ok(out.includes('Truncated'), 'truncation must be announced in the text');
  assert.ok(out.includes(String(SUBMITTED_TEXT_CAP)), 'and must name the cap it applied');
  assert.ok(out.includes(String(SUBMITTED_TEXT_CAP + 500)), 'and how much was actually submitted');
});

test('the cap matches the one the Python intake path uses', () => {
  // Two halves of one submission must not disagree about how much text there is allowed to be.
  assert.equal(SUBMITTED_TEXT_CAP, 60000);
});

// A token-shaped string, assembled at runtime on purpose. This file is scanned by the very
// pattern the test below is about — `tests/test_scanner_secret_patterns.py` exists because a
// literal here is itself an alert, and #256 is what happened last time someone wrote one
// (`ghp_${'a'.repeat(24)}` is the same trick `workers/write-lesson-guards.test.mjs` uses).
const GITHUB_TOKEN = `ghp_${'a1b2c3d4e5'.repeat(3)}`;

test('redaction still runs, and now runs over the whole text', () => {
  assert.ok(!redactIntake(`key ${GITHUB_TOKEN}`).includes(GITHUB_TOKEN),
    'a token in reach must be redacted');
});

test('a credential past the old 2,000-character line is redacted rather than dropped', () => {
  // The old order was slice-then-redact, so a secret beyond 2,000 characters was discarded
  // instead of redacted — safe by accident, and only because the cap was small. With a cap
  // that actually admits content, the order has to be redaction first.
  const body = 'a'.repeat(5000) + ' key ' + GITHUB_TOKEN;
  const out = redactIntake(body);
  assert.ok(!out.includes(GITHUB_TOKEN), `token at offset 5000 survived: …${out.slice(4995, 5040)}…`);
  assert.ok(out.includes('[REDACTED:github_token]'), 'and it should be replaced, not merely absent');
});

// ── The lesson path ──
// `redactSecrets` carried its own `slice(0, 2000)` on `title`, `problem`, `root_cause`, `fix`
// and `verification`. Measured against this corpus on 2026-10-04: 33 sections across 506
// lessons run past 2,000 — the longest a `solution` at 8,233 — and `scripts/lesson_gate.py`
// sets no upper bound on a section at all, so the gate was accepting content that this path
// then quietly cut. A lesson section is the lesson; a silent cut there loses the lesson.

test('a long lesson section survives the cap that used to destroy it', () => {
  const solution = 'S'.repeat(8233);           // the longest solution in the corpus
  const out = redactSecrets(solution);
  assert.equal(out.length, 8233, 'an 8,233-character solution must not be cut at 2,000');
  assert.equal(out, solution, 'and must arrive unmodified, with no truncation marker');
});

test('every real section in this corpus that exceeds 2,000 now passes whole', () => {
  // The shapes that were actually being destroyed, not one synthetic size.
  for (const n of [2252, 3072, 3279, 5036, 8233]) {
    const section = 'x'.repeat(n);
    assert.equal(redactSecrets(section), section, `a ${n}-character section was clipped`);
  }
});

test('the lesson path announces a clip instead of losing text quietly', () => {
  const out = redactSecrets('y'.repeat(SUBMITTED_TEXT_CAP + 10));
  assert.ok(out.includes('Truncated'), 'truncation must be announced in the text');
  assert.ok(out.includes('a lesson'), 'and must say which submission it was');
});

test('the lesson path still redacts, and still redacts before clipping', () => {
  assert.ok(!redactSecrets(`key ${GITHUB_TOKEN}`).includes(GITHUB_TOKEN),
    'a token in reach must be redacted');
  const far = 'a'.repeat(5000) + ' key ' + GITHUB_TOKEN;
  const out = redactSecrets(far);
  assert.ok(!out.includes(GITHUB_TOKEN), `token at offset 5000 survived: …${out.slice(4995, 5040)}…`);
  assert.ok(out.includes('[REDACTED:github_token]'), 'and it should be replaced, not merely absent');
});

test('no 2,000-character slice is left on any submitted-text path', () => {
  // The shape both bugs shared. A future field added to either list inherits the same clip, and
  // this is what stops the 2,000 from coming back one edit later.
  const src = readFileSync(new URL('./register-proxy-sw.js', import.meta.url), 'utf8');
  const offenders = src.split('\n')
    .map((line, i) => [i + 1, line])
    .filter(([, line]) => /slice\(0,\s*2000\)/.test(line));
  assert.deepEqual(offenders, [],
    `a 2,000-character slice is back at: ${offenders.map(([n, l]) => `${n}: ${l.trim()}`).join('; ')}`);
});
