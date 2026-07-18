import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildReplyText,
  detectIntakeType,
  extractLessonContent,
  parseEmailBody,
} from './src/email-utils.mjs';

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

// --- MIME edge cases ---

test('handles deeply nested multipart (mixed containing alternative)', () => {
  const raw = [
    'Content-Type: multipart/mixed; boundary="outer"',
    '',
    '--outer',
    'Content-Type: multipart/alternative; boundary="inner"',
    '',
    '--inner',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Nested plain text lesson',
    '--inner',
    'Content-Type: text/html',
    '',
    '<p>HTML fallback</p>',
    '--inner--',
    '--outer--',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Nested plain text lesson');
});

test('decodes base64 Content-Transfer-Encoding in text/plain part', () => {
  const plainText = 'Lesson: base64 encoded content';
  const encoded = btoa(plainText);
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: base64',
    '',
    encoded,
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: base64 encoded content');
});

test('defaults to text/plain when Content-Type header is missing', () => {
  const raw = [
    'From: agent@example.com',
    '',
    'Lesson: no content type header present',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: no content type header present');
});

test('handles broken boundary without throwing', () => {
  const raw = [
    'Content-Type: multipart/alternative; boundary="broken"',
    '',
    '--broken',
    'Content-Type: text/plain',
    '',
    'Lesson: broken boundary test',
  ].join('\r\n');
  assert.doesNotThrow(() => parseEmailBody(raw));
});

// --- Non-ASCII content ---

test('handles CJK characters in subject line (RFC 2047 encoded)', () => {
  const subject = '=?UTF-8?B?5q2j56eN?= Lesson';
  const body = 'Lesson: CJK subject test';
  assert.equal(detectIntakeType(subject, body), 'lesson-submission');
});

test('handles mixed Chinese and English body content', () => {
  const body = 'Lesson: 提交一个bug报告 about SQLite locking';
  assert.equal(detectIntakeType('', body), 'lesson-submission');
});

test('handles sender name with non-ASCII characters', () => {
  const raw = [
    'From: =?UTF-8?B?5peg5a2d5LiA?= <agent@example.com>',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: non-ASCII sender name',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: non-ASCII sender name');
});

// --- Quoting and forwarding chains ---

test('strips Outlook-style Original Message separator', () => {
  const raw = [
    'From: agent@example.com',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: new content after outlook separator',
    '',
    '-----Original Message-----',
    'From: old@example.com',
    'old quoted text',
  ].join('\r\n');
  const body = parseEmailBody(raw);
  assert.equal(extractLessonContent(body), 'Lesson: new content after outlook separator');
});

test('strips multiple levels of > quoting', () => {
  const raw = [
    'From: agent@example.com',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: original lesson text',
    '',
    '> On Mon, someone wrote:',
    '>> older message',
    '>>> oldest message',
  ].join('\r\n');
  const body = parseEmailBody(raw);
  assert.equal(extractLessonContent(body), 'Lesson: original lesson text');
});

test('Gmail-style forwarded message headers are not yet stripped (known gap)', () => {
  const raw = [
    'From: agent@example.com',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: forwarded lesson content',
    '',
    '---------- Forwarded message ----------',
    'From: previous-sender@example.com',
    'old forwarded content',
  ].join('\r\n');
  const body = parseEmailBody(raw);
  const extracted = extractLessonContent(body);
  assert.ok(extracted.includes('Lesson: forwarded lesson content'), 'preserves new lesson text');
  assert.ok(extracted.includes('Forwarded message'), 'does not yet strip Gmail forwarding headers');
});

// --- Intake type detection edge cases ---

test('classifies based on combined subject+body signal when conflicting', () => {
  const subject = 'register';
  const body = 'I want to submit a lesson about networking';
  assert.equal(detectIntakeType(subject, body), 'registration');
});

test('returns unknown for empty subject and empty body', () => {
  assert.equal(detectIntakeType('', ''), 'unknown');
});

test('truncates very long body to MAX_BODY_LENGTH without crashing', () => {
  const longBody = 'Lesson: ' + 'x'.repeat(25000);
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    '',
    longBody,
  ].join('\r\n');
  const body = parseEmailBody(raw);
  assert.ok(body.length <= 20000);
  assert.ok(body.startsWith('Lesson: '));
});

// --- Reply text generation ---

test('buildReplyText with null nodeId returns intake ID instead of node ID', () => {
  const reply = buildReplyText({ intakeId: 'intake-99', intakeType: 'bug-report', nodeId: null });
  assert.match(reply, /intake-99/);
  assert.match(reply, /Your intake ID is intake-99/);
  assert.doesNotMatch(reply, /Your node ID/);
  assert.match(reply, /queued for maintainer review/);
});

test('buildReplyText with registered nodeId includes node ID and quickstart link', () => {
  const reply = buildReplyText({ intakeId: 'intake-42', intakeType: 'lesson-submission', nodeId: 'Misaka00001' });
  assert.match(reply, /Your node ID is Misaka00001/);
  assert.match(reply, /Next steps:/);
  assert.match(reply, /quickstart/);
});
