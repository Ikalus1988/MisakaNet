import { test, strict as assert } from 'node:test';
import { parseEmail, buildReplyText } from '../email-utils.mjs';

// Existing tests...

// 1. MIME edge cases
test('should handle deeply nested multipart', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: multipart/mixed; boundary="boundary1"
MIME-Version: 1.0

--boundary1
Content-Type: multipart/alternative; boundary="boundary2"

--boundary2
Content-Type: text/plain; charset="utf-8"

This is a test email.

--boundary2
Content-Type: text/html; charset="utf-8"

<html><body>This is a test email.</body></html>

--boundary1--`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a test email.');
});

test('should handle Base64 Content-Transfer-Encoding in text/plain part', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: multipart/mixed; boundary="boundary"
MIME-Version: 1.0

--boundary
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: base64

VGhpcyBpcyBhIHRlc3QgZW1haWwu

--boundary--`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a test email.');
});

test('should default to text/plain if Content-Type header is missing', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test

This is a test email.`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a test email.');
});

test('should not throw if boundary is broken or missing', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: multipart/mixed; boundary="boundary"
MIME-Version: 1.0

--boundary
Content-Type: text/plain; charset="utf-8"

This is a test email.

--boundary`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a test email.');
});

// 2. Non-ASCII content
test('should handle subject line with CJK characters', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: =?UTF-8?B?5Y+W5a6d5Y+W5a6d?=
Content-Type: text/plain; charset="utf-8"

This is a test email with CJK subject.`;

  const result = await parseEmail(email);
  assert.equal(result.subject, '测试邮件');
});

test('should handle body with mixed Chinese + English content', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: text/plain; charset="utf-8"

This is a 测试 email.`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a 测试 email.');
});

test('should handle sender name with non-ASCII characters', async () => {
  const email = `From: 测试 <sender@example.com>
To: receiver@example.com
Subject: Test
Content-Type: text/plain; charset="utf-8"

This is a test email.`;

  const result = await parseEmail(email);
  assert.equal(result.senderName, '测试');
});

// 3. Quoting and forwarding chains
test('should handle Outlook-style Original Message separator', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: text/plain; charset="utf-8"

--Original Message--
From: original@example.com
To: sender@example.com
Subject: Original
Content-Type: text/plain; charset="utf-8"

This is the original message.

This is a forwarded message.`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a forwarded message.');
});

test('should handle multiple levels of > quoting', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: text/plain; charset="utf-8"

> > > This is a deeply quoted message.
> > This is a quoted message.
> This is a message.`;

  const result = await parseEmail(email);
  assert.equal(result.text, '> > > This is a deeply quoted message.\n> > This is a quoted message.\n> This is a message.');
});

test('should handle Gmail-style forwarded message headers', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: text/plain; charset="utf-8"

---------- Forwarded message ----------
From: original@example.com
To: sender@example.com
Subject: Original
Date: Tue, 1 Jan 2020 00:00:00 +0000
Message-ID: <original@example.com>

This is the original message.

This is a forwarded message.`;

  const result = await parseEmail(email);
  assert.equal(result.text, 'This is a forwarded message.');
});

// 4. Intake type detection edge cases
test('should classify based on combined signal if subject contains "register" but body says "lesson"', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: register
Content-Type: text/plain; charset="utf-8"

This is a lesson email.`;

  const result = await parseEmail(email);
  assert.equal(result.type, 'lesson');
});

test('should return unknown if subject and body are empty', async () => {
  const email = `From: sender@example.com
To: receiver@example.com
Subject: 
Content-Type: text/plain; charset="utf-8"

`;

  const result = await parseEmail(email);
  assert.equal(result.type, 'unknown');
});

test('should truncate very long body to MAX_BODY_LENGTH', async () => {
  const longBody = 'a'.repeat(21000); // 20KB + 1000 characters
  const email = `From: sender@example.com
To: receiver@example.com
Subject: Test
Content-Type: text/plain; charset="utf-8"

${longBody}`;

  const result = await parseEmail(email);
  assert.equal(result.text.length, 20000); // Assuming MAX_BODY_LENGTH is 20000
});

// 5. Reply text generation
test('should handle buildReplyText with nodeId: null', async () => {
  const result = await buildReplyText(null);
  assert.equal(result, 'Reply text for unregistered sender.');
});

test('should handle buildReplyText with valid nodeId', async () => {
  const result = await buildReplyText('Misaka00001');
  assert.equal(result, 'Reply text for node Misaka00001.');
});