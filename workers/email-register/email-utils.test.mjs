import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildReplyText,
  detectIntakeType,
  extractLessonContent,
  parseEmailBody,
} from './src/email-utils.mjs';

test('handles deeply nested multipart email', () => {
  const raw = [
    'Content-Type: multipart/mixed; boundary="outer"',
    '',
    '--outer',
    'Content-Type: multipart/alternative; boundary="inner"',
    '',
    '--inner',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: nested multipart',
    '--inner--',
    '--outer--',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: nested multipart');
});

test('handles base64 encoded text/plain part', () => {
  const raw = [
    'Content-Type: multipart/alternative; boundary="abc"',
    '',
    '--abc',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: base64',
    '',
    'TG9zc2U6IGJhc2U2NCBlbmNvZGVk',
    '--abc--',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: base64 encoded');
});

test('handles missing Content-Type header', () => {
  const raw = 'Lesson: no content type';
  assert.equal(parseEmailBody(raw), 'Lesson: no content type');
});

test('handles broken or missing boundary', () => {
  const raw = [
    'Content-Type: multipart/alternative; boundary="abc"',
    '',
    '--abc',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: broken boundary',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: broken boundary');
});

test('handles non-ASCII subject line', () => {
  const raw = [
    'Subject: =?UTF-8?B?6ZmE5YWo?=',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: non-ASCII subject',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: non-ASCII subject');
});

test('handles mixed Chinese + English content', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: ',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: ');
});

test('handles sender name with non-ASCII characters', () => {
  const raw = [
    'From: =?UTF-8?B?6ZmE5YWo?= <agent@example.com>',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: non-ASCII sender',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: non-ASCII sender');
});

test('handles Original Message separator', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: original message',
    'Original Message',
    'From: agent@example.com',
    'Subject: original subject',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: original message');
});

test('handles multiple levels of > quoting', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    '',
    '> > Lesson: quoted',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: quoted');
});

test('handles Gmail-style forwarded message headers', () => {
  const raw = [
    'Content-Type: text/plain; charset=UTF-8',
    '',
    '---------- Forwarded message ----------',
    'From: agent@example.com',
    'Subject: forwarded subject',
    'Lesson: forwarded message',
  ].join('\r\n');
  assert.equal(parseEmailBody(raw), 'Lesson: forwarded message');
});

test('handles subject contains "register" but body says "lesson"', () => {
  const raw = [
    'Subject: register',
    'Content-Type: text/plain; charset=UTF-8',
    '',
    'Lesson: lesson content',
  ].join('\r\n');
  assert.equal(detectIntakeType('register', parseEmailBody(raw)), 'lesson-submission');
});

test('handles empty subject + empty body', () => {
  const raw = '';
  assert.equal(detectIntakeType('', parseEmailBody(raw)), 'unknown');
});

test('handles very long body', () => {
  const raw = 'a'.repeat(20000);
  assert.equal(parseEmailBody(raw).length, 20000);
});

test('handles buildReplyText with nodeId: null', () => {
  const reply = buildReplyText({ intakeId: 'intake-1', intakeType: 'registration', nodeId: null });
  assert.notMatch(reply, /Next steps:/);
});

test('handles buildReplyText with nodeId: "Misaka00001"', () => {
  const reply = buildReplyText({ intakeId: 'intake-1', intakeType: 'registration', nodeId: 'Misaka00001' });
  assert.match(reply, /Misaka00001/);
  assert.match(reply, /Next steps:/);
});
