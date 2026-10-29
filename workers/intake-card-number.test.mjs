// #4060: the card-number rule counted digits and treated any run of spaces and hyphens between
// them as decoration, so `32767-20261029` — a port and a date — reached thirteen digits and was
// rewritten as `[REDACTED:card_number]` in a title. The submission still reported success and
// nothing said which text had been lost, which is why this is a redaction defect rather than a
// cosmetic one: a user who writes a version string, a port range or a date range next to a number
// loses text invisibly.
//
// The rule is now shaped: a card arrives as 13-19 unseparated digits, as groups of four, or in the
// 4-6-5 / 4-6-4 layouts (Amex, Diners). Two numbers joined by one hyphen fit none of those, and the
// fixtures below pin both halves — the false positive must survive, the real formats must not.
import test from 'node:test';
import assert from 'node:assert/strict';
import { redactIntake } from './register-proxy-sw.js';

const MARKER = '[REDACTED:card_number]';

for (const text of [
  'Latency probe 32767-20261029',         // the report's own title: a PID and a date
  'Latency probe 7684-20261029',          // four digits before the hyphen — never matched, kept as a control
  'range 1234-5678, then retry',          // two numbers, not a card
  'build-20261029 and pid 32767',         // the same pieces in prose order
  'a 5-digit port and a date: 32767 20261029',
]) {
  test(`a non-card number survives: ${text}`, () => {
    assert.equal(redactIntake(text), text, 'nothing here is a card, so nothing may be rewritten');
  });
}

for (const text of [
  'card: 4111 1111 1111 1111',            // 4-4-4-4, the fixture the Python test already had
  'card: 4242 4242 4242 4242',            // the shape the issue named
  'card: 4242-4242-4242-4242',            // hyphen-separated groups are still a card
  'card: 4111111111111111',               // unseparated 16
  'card: 3782 822463 10005',              // Amex 4-6-5
  'card: 3056 9300 0900 04',              // Diners 4-6-4
  'card: 6011 0000 0000 0004 123',        // 19 digits as 4-4-4-4-3
]) {
  test(`a real card is redacted: ${text}`, () => {
    const out = redactIntake(text);
    assert.ok(out.includes(MARKER), `expected a card redaction, got: ${out}`);
    assert.ok(!/\d{4}/.test(out.replace(MARKER, '')), 'no four-digit run may survive the redaction');
  });
}

test('the rule is not allowed to count hyphens as decoration again', () => {
  // The regression this file exists for: on the old rule `redactIntake('Latency probe
  // 32767-20261029')` returned 'Latency probe [REDACTED:card_number]'. Asserting the literal
  // sentence (rather than "no marker") is what fails when a future edit re-widens the separator.
  assert.equal(redactIntake('Latency probe 32767-20261029'), 'Latency probe 32767-20261029');
});

test('a card next to ordinary text is redacted, and the text around it is untouched', () => {
  const out = redactIntake('payment failed for 4111 1111 1111 1111 at 12:04');
  assert.equal(out, `payment failed for ${MARKER} at 12:04`);
});
