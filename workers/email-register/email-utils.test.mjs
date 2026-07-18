import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildReplyText,
  detectIntakeType,
  extractLessonContent,
  parseEmailBody,
} from './src/email-utils.mjs';

// ── Existing tests ────────────────────────────────────────────────────────

test('parses a plain-text lesson and strips quoted replies', () => {
  const raw = [
    'From: agent@example.com',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: retry SQLite writes with bounded backoff.',
    '',
    'On Tue, Maintainer wrote:',
    '> old message',
  ].join('\r\n');
  const body = parseEmailBody(raw);
  assert.equal(extractLessonContent(body), 'Lesson: retry SQLite writes with bounded backoff.');
  assert.equal(detectIntakeType('Submission', body), 'lesson-submission');
});

test('prefers text/plain in multipart email and decodes quoted-printable', () => {
  const raw = [
    'Content-Type: multipart/alternative; boundary="abc"',
    '',
    '--abc',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: quoted-printable',
    '',
    'Lesson: lock=20retry',
    '--abc',
    'Content-Type: text/html',
    '',
    '<p>wrong fallback</p>',
    '--abc--',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: lock retry');
});

test('detects registration hints from the body and includes node ID in reply', () => {
  assert.equal(detectIntakeType('Hello', 'Please register my agent'), 'registration');
  const reply = buildReplyText({ intakeId: 'intake-1', intakeType: 'registration', nodeId: 'Misaka10053' });
  assert.match(reply, /Misaka10053/);
  assert.match(reply, /Next steps:/);
});

test('falls back from HTML to readable text', () => {
  const raw = 'Content-Type: text/html; charset=UTF-8\r\n\r\n<p>Bug report<br>worker failed</p>';
  assert.equal(parseEmailBody(raw), 'Bug report\nworker failed');
  assert.equal(detectIntakeType('', parseEmailBody(raw)), 'bug-report');
});

test('converts HTML without regex tag filtering or recursive entity decoding', () => {
  const raw = [
    'Content-Type: text/html; charset=UTF-8',
    '',
    '<style>.hidden{display:none}</style>',
    '<p>Lesson &amp; notes</p>',
    '<script>alert("ignore")</script>',
    '<div>&amp;lt;not-a-tag&amp;gt;</div>',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson & notes\n&lt;not-a-tag&gt;');
});

// ── NEW: MIME edge cases ──────────────────────────────────────────────────

test('parseEmailBody: deeply nested multipart/mixed containing multipart/alternative extracts text/plain', () => {
  const raw = [
    'Content-Type: multipart/mixed; boundary="outer"',
    '',
    '--outer',
    'Content-Type: multipart/alternative; boundary="inner"',
    '',
    '--inner',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Hello from nested multipart world',
    '--inner',
    'Content-Type: text/html',
    '',
    '<p>HTML fallback</p>',
    '--inner--',
    '--outer',
    'Content-Type: application/octet-stream',
    '',
    'attachment data',
    '--outer--',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Hello from nested multipart world');
});

test('parseEmailBody: base64 encoded text/plain part decodes correctly', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: base64',
    '',
    'SGVsbG8gV29ybGQhIE15IGxlc3NvbiBpcyBoZXJlLg==',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Hello World! My lesson is here.');
});

test('parseEmailBody: missing Content-Type header defaults to text/plain', () => {
  const raw = [
    'From: bob@example.com',
    'Date: Mon, 1 Jan 2025 00:00:00 +0000',
    '',
    'Just a plain-text message with no content-type header.',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Just a plain-text message with no content-type header.');
});

test('parseEmailBody: broken or unmatched boundary does not throw', () => {
  const raw = [
    'Content-Type: multipart/alternative; boundary="abc"',
    '',
    '--abc',
    'Content-Type: text/plain',
    '',
    'visible part',
    '--abc-deformed',
    'garbage',
  ].join('\r\n');
  assert.doesNotThrow(() => parseEmailBody(raw));
  const result = parseEmailBody(raw);
  assert.equal(typeof result, 'string');
});

// ── NEW: Non-ASCII content ─────────────────────────────────────────────────

test('parseEmailBody: Chinese characters in text/plain body are preserved', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    '',
    '课程提交：关于数据库锁的教训。使用重试机制解决死锁问题。',
  ].join('\r\n');
  const body = parseEmailBody(raw);
  assert.ok(body.includes('课程'));
  assert.ok(body.includes('数据库'));
  assert.ok(body.includes('重试'));
});

test('parseEmailBody: Japanese and emoji in HTML body survive html-to-text conversion', () => {
  const raw = [
    'Content-Type: text/html; charset=UTF-8',
    '',
    '<p>バグ修正: メモリリークを修正しました 🐛</p><br><p>日本語テスト完了 ✅</p>',
  ].join('\r\n');
  const body = parseEmailBody(raw);
  assert.ok(body.includes('バグ修正'));
  assert.ok(body.includes('日本語テスト'));
  assert.ok(body.includes('✅'));
});

// ── NEW: Quoting and forwarding chains ─────────────────────────────────────

test('extractLessonContent: strips quoted content after Outlook Original Message separator', () => {
  const body = [
    'This is my lesson about SQLite retries.',
    'It contains the solution to the deadlock issue.',
    '',
    '------ Original Message ------',
    'From: someone@example.com',
    'Sent: Tuesday, January 1, 2025 12:00 PM',
    'To: me@example.com',
    'Subject: RE: deadlock issue',
    '',
    '> old quoted text that should be removed',
    '> more quoted text',
  ].join('\n');
  assert.equal(
    extractLessonContent(body),
    'This is my lesson about SQLite retries.\nIt contains the solution to the deadlock issue.',
  );
});

test('extractLessonContent: strips multiple levels of > quoting', () => {
  const body = [
    'My fresh lesson submission.',
    '',
    '> single-level quote',
    '>> double-level quote',
    '>>> triple-level quote',
    '> > space-separated quote',
    '>deep quote without space',
  ].join('\n');
  assert.equal(extractLessonContent(body), 'My fresh lesson submission.');
});

test('extractLessonContent: Gmail forwarded message delimiter is preserved (not a reply-quote pattern)', () => {
  const body = [
    'Original lesson text.',
    '',
    '---------- Forwarded message ----------',
    'From: sender@example.com',
    'Date: Tue, 1 Jan 2025 12:00:00 +0000',
    'Subject: Fwd: old lesson',
    'To: recipient@example.com',
    '',
    '> some content from the forward',
  ].join('\n');
  const result = extractLessonContent(body);
  // Forward delimiter is not handled by extractLessonContent, so it stays
  assert.ok(result.includes('Forwarded message'));
  assert.ok(result.includes('sender@example.com'));
});

// ── NEW: Intake type detection edge cases ──────────────────────────────────

test('detectIntakeType: CJK subject with registration keyword is classified as registration', () => {
  assert.equal(detectIntakeType('新用户注册申请', ''), 'registration');
});

test('detectIntakeType: CJK subject with submission keyword is classified as lesson-submission', () => {
  assert.equal(detectIntakeType('投稿：数据库锁的问题', ''), 'lesson-submission');
});

test('detectIntakeType: subject has "register" and body has "lesson" — registration takes priority (checked first)', () => {
  const body = 'This is my lesson about retry mechanisms. 我的教训。';
  assert.equal(detectIntakeType('Please register my lesson', body), 'registration');
});

test('detectIntakeType: empty subject and empty body returns unknown', () => {
  assert.equal(detectIntakeType('', ''), 'unknown');
});

test('detectIntakeType: bug keyword triggers bug-report classification', () => {
  assert.equal(detectIntakeType('Bug: worker crashes on startup', ''), 'bug-report');
  assert.equal(detectIntakeType('', 'I have an issue with my agent'), 'bug-report');
  assert.equal(detectIntakeType('', 'There is a defect in the pipeline'), 'bug-report');
});

test('parseEmailBody & detectIntakeType: very long body (>20KB) is truncated to MAX_BODY_LENGTH', () => {
  const longBody = 'a'.repeat(25000);
  const raw = [
    'Content-Type: text/plain',
    '',
    longBody,
  ].join('\r\n');
  const parsed = parseEmailBody(raw);
  assert.equal(parsed.length, 20000);
  // detectIntakeType should still work with the truncated body
  assert.equal(detectIntakeType('Registration', parsed), 'registration');
});

// ── NEW: Reply text generation ─────────────────────────────────────────────

test('buildReplyText: without nodeId references intake ID and queue message', () => {
  const reply = buildReplyText({ intakeId: 'intake-42', intakeType: 'lesson-submission', nodeId: null });
  assert.match(reply, /intake-42/);
  assert.match(reply, /queued for maintainer review/);
  assert.doesNotMatch(reply, /Next steps:/);
});

test('buildReplyText: with nodeId references node ID and next steps', () => {
  const reply = buildReplyText({ intakeId: 'intake-1', intakeType: 'registration', nodeId: 'Misaka00001' });
  assert.match(reply, /Misaka00001/);
  assert.match(reply, /Next steps:/);
  assert.doesNotMatch(reply, /queued for maintainer review/);
  assert.doesNotMatch(reply, /intake ID for follow-up/);
});
