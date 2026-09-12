// Synthetic tokens for the worker tests.
//
// The tests need *a* token to put in `env.MCP_TOKEN` / `REGISTER_TOKEN` and in the
// `Authorization: Bearer …` header they send, but a literal value is
// indistinguishable from a hardcoded credential to a scanner that cannot know the
// string is fake. hol-guard's plugin-scanner reported exactly that — two
// `HARDCODED_SECRET` alerts at error severity on fixtures like
// `const TOKEN = 'relevance-floor-test-token'` (#252/#253, 2026-09-12) — and a
// dozen more fixtures carried the same shape.
//
// Deriving the value at runtime removes the false positive and makes the tests
// independent of the literal: a fixture can no longer be mistaken for, or
// accidentally match, a real credential. Call it once per file and reuse the
// value, so a file keeps the "one token everywhere" semantics its assertions rely
// on.
import { randomUUID } from 'node:crypto';

/** A synthetic, per-run token. Never a literal, never a real credential. */
export function testToken(label = 'test') {
  return `${label}-${randomUUID()}`;
}
