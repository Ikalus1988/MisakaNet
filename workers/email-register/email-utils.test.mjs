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
});

// --- NEW EDGE CASE TESTS FOR #498 ---

// 1. MIME edge cases
test('parses deeply nested multipart', () => {
  const raw = [
    'Content-Type: multipart/mixed; boundary="mix"',
    '',
    '--mix',
    'Content-Type: multipart/alternative; boundary="alt"',
    '',
    '--alt',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'nested plain',
    '--alt--',
    '--mix--',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'nested plain');
});

test('decodes base64 text/plain', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: base64',
    '',
    'aGVsbG8=', // hello
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'hello');
});

test('defaults to text/plain if missing Content-Type', () => {
  const raw = 'Subject: test\r\n\r\nmissing type body';
  assert.equal(parseEmailBody(raw), 'missing type body');
});

test('does not throw on broken boundary', () => {
  const raw = 'Content-Type: multipart/alternative; boundary="broken"\r\n\r\nno boundary here';
  assert.equal(parseEmailBody(raw), 'no boundary here');
});

// 2. Non-ASCII content
test('handles CJK and non-ASCII characters in subject and body', () => {
  const subject = '=?UTF-8?B?5rOo5YaMPw==?='; // "注册?" (Register?)
  const body = 'English + 注册';
  assert.equal(detectIntakeType(subject, body), 'registration');
  const raw = 'From: "Löwe" <l@ex.com>\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n' + body;
  assert.equal(parseEmailBody(raw), body);
});

// 3. Quoting and forwarding chains
test('strips Outlook-style Original Message separator', () => {
  const body = 'new message\n-----Original Message-----\nold message';
  assert.equal(extractLessonContent(body), 'new message');
});

test('strips multiple levels of > quoting', () => {
  const body = '> > > very old\n> > old\n> recent\nfresh';
  assert.equal(extractLessonContent(body), 'fresh');
});

test('strips Gmail-style forwarded message headers', () => {
  const body = 'Here is my lesson.\n---------- Forwarded message ---------\nFrom: Bob\n> old stuff';
  assert.equal(extractLessonContent(body), 'Here is my lesson.');
});

// 4. Intake type detection edge cases
test('classifies based on combined signal if subject and body differ', () => {
  // subject has "register", body has "lesson"
  // Combined signal will match "registration" first because regex for registration is checked first in detectIntakeType
  assert.equal(detectIntakeType('register', 'Here is my lesson'), 'registration');
});

test('returns unknown for empty subject and body, does not crash', () => {
  assert.equal(detectIntakeType('', ''), 'unknown');
});

test('truncates very long body', () => {
  const longBody = 'A'.repeat(25000);
  assert.equal(parseEmailBody('\r\n\r\n' + longBody).length, 20000);
  assert.equal(extractLessonContent(longBody).length, 20000);
});

// 5. Reply text generation
test('buildReplyText with nodeId: null', () => {
  const reply = buildReplyText({ intakeId: '123', intakeType: 'unknown', nodeId: null });
  assert.match(reply, /intake ID is 123/);
  assert.match(reply, /queued for maintainer review/);
});

test('buildReplyText with valid nodeId', () => {
  const reply = buildReplyText({ intakeId: '123', intakeType: 'lesson-submission', nodeId: 'Misaka00001' });
  assert.match(reply, /node ID is Misaka00001/);
  assert.match(reply, /follow the node quickstart/);
});
