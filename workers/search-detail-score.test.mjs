import { test } from "node:test";
import assert from "node:assert/strict";
import { MCP_TOOLS, compactResult, applyDetailLevel } from "./register-proxy-sw.js";

// `misakanet_search` must carry a `score` at every detail level (#2790).
//
// Why this rule exists. The tool's own description in `MCP_TOOLS` reads:
//
//   "[compact: {id, title, problem, freshness, evidence_level} | summary: + {domain, tags, fix} |
//    full: the record, each with score]"
//
// "each with score" is a promise about all three levels. `applyDetailLevel` kept it for `full` (it
// returns the rows untouched) and dropped it for `compact` and `summary`, which is the worse direction
// because `compact` is the *default* detail level. Measured against production on 2026-10-04, same
// query, one field apart:
//
//     detail=compact   5 results   first=gfw-tls-sni-block-pattern   score=<absent>
//     detail=full      5 results   first=gfw-tls-sni-block-pattern   score=3.16
//
// The numbers are the point. For a real query, full detail separates genuine hits from junk by a wide
// margin (18.43 and 11.22 against 2.99–3.16), and the field carrying that separation is precisely the one
// the default level withheld. An agent asking the normal question could not tell those two cases apart —
// and the handler answers `voice: "lesson-found"` for any non-empty result set, so from the caller's side
// an irrelevant hit and a good one are indistinguishable.
//
// This is deliberately a narrower fix than the issue asks for. It does not add a relevance floor, because
// the threshold for "this result is too weak to show" is a product decision with no defensible default
// here. Surfacing the number stops the worker from withholding the evidence a caller would need to make
// that call; the floor stays a separate, deliberate change.

// A row as the rankers actually produce it: `searchLessons` attaches `score` (rounded to 2dp at
// `register-proxy-sw.js:1625`), and `lessonQuery` re-attaches it after `publicLessonRow`.
const RANKED = {
  id: "srvo-002-position-error-servo",
  title: "SRVO-002 position error servo",
  problem: "servo overshoots then alarms",
  evidence_level: "E2",
  domain: "fanuc",
  tags: '["fanuc","servo"]',
  updated: "2026-09-01",
  score: 18.43,
};

// The naive `searchLessons` fallback does not rank, so its rows carry no score at all.
const UNRANKED = {
  id: "some-lesson",
  title: "Some Lesson",
  problem: "something failed",
  updated: "2026-08-01",
};

test("compact detail carries the score the schema promises", () => {
  const [out] = applyDetailLevel([{ ...RANKED }], "compact");
  assert.strictEqual(out.score, 18.43);
  // Not coerced, not reformatted: the ranker's rounding is the contract, and re-rounding here would
  // make the worker and the recorded value disagree whenever the multiplier moved.
  assert.strictEqual(typeof out.score, "number");
});

test("summary detail carries the score too", () => {
  const [out] = applyDetailLevel([{ ...RANKED }], "summary");
  assert.strictEqual(out.score, 18.43);
  assert.strictEqual(out.domain, "fanuc", "summary still adds its own fields");
});

test("full detail still carries the score", () => {
  const [out] = applyDetailLevel([{ ...RANKED }], "full");
  assert.strictEqual(out.score, 18.43);
});

test("a real hit and a junk hit are now distinguishable at the default detail level", () => {
  // The regression this file exists for, expressed as the caller experiences it: two results whose
  // titles and problems are equally plausible, differing only in a score the old compact path dropped.
  const junk = { ...RANKED, id: "gfw-tls-sni-block-pattern", title: "GFW TLS SNI block", score: 3.16 };
  const hit = { ...RANKED, id: "srvo-002-position-error-servo", title: "SRVO-002", score: 18.43 };

  const [junkOut, hitOut] = applyDetailLevel([junk, hit], "compact");

  assert.ok(hitOut.score > junkOut.score * 5,
    `expected the real hit to outscore junk by a wide margin, got ${hitOut.score} vs ${junkOut.score}`);
  assert.notStrictEqual(junkOut.score, undefined, "a weak result must still be labelled, not blank");
});

test("an unranked row omits the field rather than reporting a null score", () => {
  // `searchLessons` is the fallback for when the BM25 index is unavailable, and it does not score.
  // Emitting `score: null` would invite a caller to compare against nothing; omitting it is the honest
  // "this path did not rank" signal, and it is what the issue's default-level report turns on.
  const [out] = applyDetailLevel([{ ...UNRANKED }], "compact");
  assert.ok(!("score" in out), `expected no score key, got ${JSON.stringify(out.score)}`);
  assert.strictEqual(out.id, "some-lesson", "the rest of the row is unaffected");
});

test("a non-numeric score is treated as absent, not passed through", () => {
  for (const bad of [null, undefined, "18.43", NaN, Infinity, {}]) {
    const [out] = applyDetailLevel([{ ...RANKED, score: bad }], "compact");
    assert.ok(!("score" in out), `score=${JSON.stringify(bad)} should be omitted, got ${JSON.stringify(out.score)}`);
  }
});

test("zero is a real score and must survive", () => {
  // The falsy-value trap: `score: 0` is a legitimate low ranking, and `...(score ? ... : {})` would drop
  // it and read as "not scored". `Number.isFinite` is the guard that keeps it.
  const [out] = applyDetailLevel([{ ...RANKED, score: 0 }], "compact");
  assert.strictEqual(out.score, 0);
  assert.ok("score" in out);
});

test("every detail level the tool advertises is nested, not divergent", () => {
  // Guards the promise in the schema as a whole rather than one field of it. The description describes
  // the levels as nested — compact ⊂ summary, and `full` is the record itself — so the direction to
  // check is that the narrower level's keys survive into the wider one. A field that exists on
  // `summary` and vanishes on the default level is the shape of the #2790 defect; the reverse
  // (`summary` adding `domain`) is the documented design and must not fail.
  const levelOf = (level) => {
    const [out] = applyDetailLevel([{ ...RANKED }], level);
    return new Set(Object.keys(out));
  };
  const compact = levelOf("compact");
  const summary = levelOf("summary");
  const full = levelOf("full");

  for (const key of compact) {
    assert.ok(summary.has(key), `detail=summary is missing "${key}", which the default level returns`);
  }
  // `full` is documented as "the record", not as a shaped subset, so only the fields the description
  // lists for compact are required to survive there.
  for (const key of ["id", "title", "problem", "score"]) {
    assert.ok(full.has(key), `detail=full is missing "${key}"`);
  }
});

test("the advertised description really does promise a score on the default level", () => {
  // The rule above is only meaningful if the promise is still in the tool description. If someone
  // rewrites that sentence to drop the score again, this fails and the decision gets made on purpose
  // rather than by a formatter drifting away from its documentation.
  const search = MCP_TOOLS.find((t) => t.name === "misakanet_search");
  assert.ok(search, "misakanet_search is not in MCP_TOOLS");
  assert.match(search.description, /compact: \{[^}]*\bscore\b[^}]*\}/,
    "the tool description no longer lists `score` in the compact shape — if that was deliberate, drop "
    + "compactResult's score and this test together, and say why in the commit");
  assert.match(search.description, /omitted on the unranked fallback path/,
    "the description should still say when the score is absent, so a caller does not read a missing "
    + "field as a zero");
});
