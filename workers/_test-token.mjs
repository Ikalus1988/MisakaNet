// Synthetic tokens for the worker tests.
//
// The tests need *a* token to put in `env.MCP_TOKEN` / `REGISTER_TOKEN` and in the
// `Authorization: Bearer …` header they send, but a literal value is
// indistinguishable from a hardcoded credential to a scanner that cannot know the
// string is fake. hol-guard's plugin-scanner reported exactly that — two
// `HARDCODED_SECRET` alerts at error severity on two of these fixtures
// (#252/#253, 2026-09-12) — and a dozen more files carried the same shape.
//
// That scanner reads comments too: the first version of *this* comment quoted one
// of the offending literals as an example and was itself reported (#254). Same
// lesson as the DSH STORE bundle patch, where quoting the forbidden namespace in a
// comment tripped the rule — describe the pattern, never paste it.
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
