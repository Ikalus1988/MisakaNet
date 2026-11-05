// Answer-notification email: optional, opt-in, confirm-before-send, deleted after one notice.
//
// The contract this pins: a typed address is not proof it is the user's, so nothing is sent to it
// until the link in the confirmation mail is opened; the notice carries the issue URL and never the
// reporter's text, so the account cannot relay content to a third party; a failed send never fails
// the intake.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  queueAnswerNoticeImpl,
  confirmAnswerNoticeImpl,
  deliverAnswerNoticesImpl,
} from "./register-proxy-sw.js";

function fakeEnv() {
  const kv = new Map();
  const sent = [];
  return {
    sent,
    kv,
    MISAKANET_KV: {
      async put(k, v) { kv.set(k, String(v)); },
      async get(k) { return kv.has(k) ? kv.get(k) : null; },
      async delete(k) { kv.delete(k); },
    },
    EMAIL: {
      async send(message) { sent.push(message); return { messageId: `m${sent.length}` }; },
    },
  };
}

const QUESTION = { dedupHash: "h1", email: "user@example.com", issueUrl: "https://github.com/Ikalus1988/MisakaNet/issues/1" };

test("an invalid address is refused before anything is stored or sent", async () => {
  const env = fakeEnv();
  assert.equal(await queueAnswerNoticeImpl(env, { ...QUESTION, email: "not-an-address" }), false);
  assert.equal(env.sent.length, 0);
  assert.equal(env.kv.size, 0);
});

test("queueing sends exactly one confirmation and stores a pending record + token", async () => {
  const env = fakeEnv();
  assert.equal(await queueAnswerNoticeImpl(env, QUESTION), true);
  assert.equal(env.sent.length, 1);
  assert.equal(env.sent[0].to, "user@example.com");
  assert.equal(env.sent[0].from, "notify@misakanet.org");
  assert.ok(env.sent[0].text.includes("/api/notify/confirm?t="));
  const record = JSON.parse(env.kv.get("notify:h1"));
  assert.equal(record.state, "pending");
  assert.equal(record.email, "user@example.com");
  const tokenKey = [...env.kv.keys()].find((k) => k.startsWith("notify-token:"));
  assert.ok(tokenKey, "a confirmation token must be stored");
});

test("confirming flips the record to confirmed and burns the token", async () => {
  const env = fakeEnv();
  await queueAnswerNoticeImpl(env, QUESTION);
  const token = [...env.kv.keys()].find((k) => k.startsWith("notify-token:")).slice("notify-token:".length);
  assert.equal(await confirmAnswerNoticeImpl(env, token), true);
  assert.equal(JSON.parse(env.kv.get("notify:h1")).state, "confirmed");
  assert.equal(env.kv.has(`notify-token:${token}`), false);
  assert.equal(await confirmAnswerNoticeImpl(env, "unknown-token"), false);
});

test("delivery sends one notice for a confirmed answered row and deletes the address", async () => {
  const env = fakeEnv();
  await queueAnswerNoticeImpl(env, QUESTION);
  const token = [...env.kv.keys()].find((k) => k.startsWith("notify-token:")).slice("notify-token:".length);
  await confirmAnswerNoticeImpl(env, token);
  env.MISAKANET_D1 = {
    prepare() {
      return { async all() { return { results: [{ dedup_hash: "h1", issue_url: QUESTION.issueUrl }] }; } };
    },
  };
  const out = await deliverAnswerNoticesImpl(env);
  assert.deepEqual(out, { sent: 1 });
  assert.equal(env.sent.length, 2);
  const notice = env.sent[1];
  assert.equal(notice.to, "user@example.com");
  assert.ok(notice.text.includes(QUESTION.issueUrl), "the notice carries the issue URL");
  assert.ok(!notice.text.includes("install"), "the notice never carries the reporter's text");
  assert.equal(env.kv.has("notify:h1"), false, "the address is deleted after the notice");
});

test("an unconfirmed address is never sent an answer", async () => {
  const env = fakeEnv();
  await queueAnswerNoticeImpl(env, QUESTION);
  env.MISAKANET_D1 = {
    prepare() {
      return { async all() { return { results: [{ dedup_hash: "h1", issue_url: QUESTION.issueUrl }] }; } };
    },
  };
  assert.deepEqual(await deliverAnswerNoticesImpl(env), { sent: 0 });
  assert.equal(env.sent.length, 1, "only the confirmation was sent");
});

test("without the EMAIL binding the intake path is untouched", async () => {
  const env = fakeEnv();
  delete env.EMAIL;
  assert.equal(await queueAnswerNoticeImpl(env, QUESTION), false);
  assert.equal(env.sent.length, 0);
});
