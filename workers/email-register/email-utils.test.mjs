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
