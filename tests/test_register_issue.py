#!/usr/bin/env python3
"""Tests for `scripts/register_issue.py` — the welcome comment for a registration issue.

What is pinned here, and why each one is a test rather than a comment:

* **The false positives are transcripts, not hypotheticals.** On 2026-09-22 the registration job
  fired three times on unrelated issues of mine, because the guard was `contains(title,
  'register')`. The three real titles are in `NOT_A_REGISTRATION` below; a future "let's be more
  generous with the keyword" edit fails here with the run numbers in the message.
* **The comment must not offer reads.** The old welcome text said "匿名 5 次读取/天" and framed
  registration as the way past a quota. The cap was removed on 2026-09-18 — reads have been
  unlimited since — so the workflow was, in the one place a new user actually reads, promising a
  restriction the service does not have and selling registration with a reason that had expired.
* **The comment must not carry a credential.** It is a public issue. `refuse_credentials` is
  exercised directly, and through `build_welcome`, because the realistic failure is not malice —
  it is a later edit passing the wrong field into the text.
* **The job writes nothing.** `main()` is driven against a fake API whose calls are recorded, so
  "posts once, labels once, closes once, and on a second run edits its own comment instead of
  adding a second one" is asserted rather than assumed.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import scripts.register_issue as ri  # noqa: E402


# ────────────────────────────── is_registration ──────────────────────────────


# The three issues the keyword guard actually fired on, 2026-09-22 (runs 35749203103,
# 35761772072, 35764549504) — each of which then failed at the push step and looked like a broken
# registration path.
NOT_A_REGISTRATION = [
    ("docs(site): registration copy still frames registration as the way in (and the node count as members)", ["area:ci"]),
    ("fix(api): `client_id` is a credential in practice — the register reuse path returns the stored token in plaintext", ["bug"]),
    ("[Intake] agent loses token after 24h silent period; misakanet_register returns a brand-new node", ["intake"]),
    ("[Ops] mcp_token 过期自动清理（30 天 TTL 无回收，已积累 42 个含测试注册）", ["area:ci"]),
]


@pytest.mark.parametrize("title,labels", NOT_A_REGISTRATION)
def test_an_issue_that_only_mentions_registration_is_not_one(title, labels):
    assert not ri.is_registration(title, labels), (
        "this title is one of the issues the old keyword guard fired on; matching it again is the "
        "defect #2106 records"
    )


@pytest.mark.parametrize("title", [
    "join: yashraj4",           # the template's title, and the shape of 70 real issues
    "join",
    "join: New node registration (Tianran_Yvchun, standard mode)",
    "[JOIN] Hermes Agent — MoneyKalle",
    "Join: my agent",
    "join：全角冒号",
])
def test_the_legacy_join_shapes_are_recognised(title):
    assert ri.is_registration(title, [])


def test_the_template_label_alone_is_enough():
    # `.github/ISSUE_TEMPLATE/register.yml` sets `labels: [registration]` itself, so this is the
    # mechanical signal and the one the workflow's `if:` keys on.
    assert ri.is_registration("anything at all", ["registration"])
    assert ri.is_registration("anything at all", ["Registration", "area:ci"])


def test_a_title_that_starts_with_a_different_word_is_not_a_registration():
    # `startsWith`, not `contains`: "Registerless" or a sentence that begins elsewhere must not
    # trigger, which is exactly what "contains" got wrong.
    assert not ri.is_registration("register my node", [])
    assert not ri.is_registration("Re: how do I register?", [])


# ────────────────────────────── the count ──────────────────────────────


def test_the_live_counter_is_shown_without_the_node_offset():
    # The endpoint serves the raw counter (live: 11777); every public surface shows current-10000,
    # and the offset comes from `sync_lesson_count.NODE_OFFSET` rather than a second literal.
    assert ri.display_count(11777) == 1777
    assert ri.NODE_OFFSET == 10000


@pytest.mark.parametrize("value", [None, "11777", 9999, True, 10000.5, {}])
def test_an_unusable_counter_is_none_rather_than_an_exception(value):
    # `/api/counter` is public and outside our control: a shape change must cost a display line,
    # never a registration.
    assert ri.display_count(value) is None


def test_the_next_node_id_is_the_number_the_worker_will_hand_out():
    # `allocateNodeCounter()` in the worker reads KV `node_counter`, writes `current + 1` and names
    # the node `Misaka{current + 1}` — so reading the public counter and adding one names the next
    # registration's node without allocating anything.
    assert ri.next_node_id(11777) == "Misaka11778"
    assert ri.next_node_id(10000) == "Misaka10001"
    assert ri.next_node_id(9999) is None


# ────────────────────────────── the comment ──────────────────────────────


def test_the_comment_starts_with_the_marker_so_a_rerun_edits_it():
    body = ri.build_welcome(node_count=1777)
    assert body.startswith(ri.MARKER)


def test_the_comment_says_how_to_register_and_what_the_fields_mean():
    body = ri.build_welcome(node_count=1777)
    assert "misakanet_register" in body
    assert "client_id" in body and "reused" in body
    assert "node_id" in body and "token" in body
    assert "Bearer" in body
    assert "1777" in body


def test_the_comment_still_matches_what_the_site_polls_for():
    """`docs/index.html` flips "⏳ 分配中" → "✅ 已分配" on this regex, in *this issue's comments*.

    Without it the browser polls for three minutes and then tells the user to refresh — a UX
    regression that no unit test of the workflow would notice, which is why the pattern is copied
    out of the page rather than described.
    """
    site_pattern = re.compile(r"节点代号.*?[*]{2}(Misaka\d+)[*]{2}")
    body = ri.build_welcome(node_count=1777, next_id="Misaka11778")
    found = site_pattern.search(body)
    assert found and found.group(1) == "Misaka11778"


def test_an_estimated_number_says_it_is_an_estimate():
    body = ri.build_welcome(node_count=1777, next_id="Misaka11778")
    assert "下一个号" in body
    assert "misakanet_register" in body and "node_id" in body, (
        "the authoritative id is the one the user's own register call returns; when the comment "
        "names an estimate it has to name that source too"
    )
    assert "只读不写" in body


def test_an_allocated_node_id_is_not_called_an_estimate():
    body = ri.build_welcome(node_id="Misaka10074", node_count=1777)
    assert "下一个号" not in body


def test_the_comment_never_promises_a_read_quota():
    body = ri.build_welcome(node_count=1777)
    assert "5 次" not in body, (
        "the 5-reads-a-day cap was removed on 2026-09-18; the welcome text was still selling "
        "registration as the way past it"
    )
    assert "不限次数" in body, "reads are unlimited, and a new user should be told so"
    # The word "配额" *is* allowed — but only to say a rate limit is not one.
    assert "不是配额" in body


def test_the_comment_does_not_imply_a_number_this_job_assigned():
    body = ri.build_welcome(node_count=1777)
    assert "你是第" not in body, (
        "the number used to come from `data/counter.json`, which counted issue-openers rather than "
        "registered nodes — and it was not the node id the user's own register call returned"
    )
    assert "worker" in body and "KV" in body


def test_the_comment_names_a_node_id_only_when_another_channel_allocated_one():
    assert "你的节点代号：**Misaka10074**" in ri.build_welcome(node_id="Misaka10074", node_count=1777)
    # Without one, the text may still show `Misaka10074` as the example in the field table — what
    # it must not do is claim that id for this issue.
    assert "你的节点代号：**Misaka10074**" not in ri.build_welcome(node_count=1777)


def test_the_comment_omits_the_count_when_it_could_not_be_read():
    body = ri.build_welcome(node_count=None)
    assert "当前网络" not in body
    assert "misakanet_register" in body, "the instructions are the point; the count is decoration"


def test_a_credential_in_the_text_is_refused():
    with pytest.raises(ri.RegisterError) as e:
        ri.refuse_credentials("here is your token: mcp_AbCdEf12345")
    assert "public" in str(e.value)


def test_the_refusal_reaches_the_comment_builder():
    # The realistic route to a leak is not malice: it is a later edit passing the wrong field in.
    with pytest.raises(ri.RegisterError):
        ri.build_welcome(node_id="mcp_AbCdEf12345")


def test_the_comment_does_not_contain_a_token_or_a_client_id_value():
    body = ri.build_welcome(node_id="Misaka10074", node_count=1777)
    assert not ri.TOKEN_RE.search(body)
    assert "<你自己生成的随机 UUID>" in body, "the client_id is described, never chosen here"


# ────────────────────────────── the run ──────────────────────────────


class FakeGitHub:
    """Records what the run does to the API, and answers the way GitHub would."""

    def __init__(self, *, issue: dict, existing_comment: dict | None = None):
        self.issue_payload = issue
        self.existing_comment = existing_comment
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and "/issues/" in path and path.endswith("/comments?per_page=100"):
            return [self.existing_comment] if self.existing_comment else []
        if method == "GET" and "/issues/" in path:
            return self.issue_payload
        if method == "POST" and path.endswith("/comments"):
            return {"id": 555}
        if method in ("POST", "PATCH"):
            return {}
        raise AssertionError(f"unexpected call: {method} {path}")


def issue_payload(*, title="join: someone", labels=("registration",), state="open"):
    return {"number": 1234, "title": title, "body": "hello",
            "labels": [{"name": l} for l in labels], "state": state}


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    # No network in tests: the counter read is the one call that leaves GitHub.
    monkeypatch.setattr(ri, "fetch_node_counter", lambda url=ri.COUNTER_URL: 11777)
    return monkeypatch


def install(monkeypatch, fake):
    monkeypatch.setattr(ri.GitHub, "request", fake.request)
    return fake


def test_a_registration_issue_gets_one_comment_the_label_and_a_close(wired, monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    fake = install(monkeypatch, FakeGitHub(issue=issue_payload()))
    assert ri.main(["--issue", "1234"]) == 0

    writes = [(m, p.split("/repos/o/r")[-1]) for m, p, _ in fake.calls if m in ("POST", "PATCH")]
    assert ("POST", "/issues/1234/comments") in writes
    assert ("POST", "/issues/1234/labels") in writes
    assert ("PATCH", "/issues/1234") in writes
    # And nothing that touches the repository: the job has no `contents: write` any more.
    assert not [p for _, p, _ in fake.calls if "/git/" in p or p.endswith("/contents")]
    assert "no commit" in summary.read_text(encoding="utf-8")


def test_a_second_run_edits_its_own_comment_and_does_not_close_twice(wired, monkeypatch):
    existing = {"id": 42, "body": f"{ri.MARKER}\nold text"}
    fake = install(monkeypatch, FakeGitHub(
        issue=issue_payload(labels=("registration", "registered"), state="closed"),
        existing_comment=existing,
    ))
    assert ri.main(["--issue", "1234"]) == 0

    writes = [(m, p) for m, p, _ in fake.calls if m in ("POST", "PATCH")]
    assert ("PATCH", "/repos/o/r/issues/comments/42") in writes
    assert not [p for m, p in writes if m == "POST" and p.endswith("/comments")]
    assert not [p for m, p in writes if p.endswith("/labels")], "the label is already there"
    assert not [p for m, p in writes if p == "/repos/o/r/issues/1234"], "already closed"


def test_an_unrelated_issue_is_left_completely_alone(wired, monkeypatch, capsys):
    fake = install(monkeypatch, FakeGitHub(issue=issue_payload(
        title="fix(api): the register reuse path returns the stored token", labels=("bug",))))
    assert ri.main(["--issue", "1234"]) == 0
    assert [c for c in fake.calls if c[0] in ("POST", "PATCH")] == []
    out = capsys.readouterr().out
    assert "not a registration" in out


def test_force_welcomes_an_issue_that_does_not_look_like_one(wired, monkeypatch):
    fake = install(monkeypatch, FakeGitHub(issue=issue_payload(title="some other title", labels=())))
    assert ri.main(["--issue", "1234", "--force"]) == 0
    assert [c for c in fake.calls if c[0] == "POST"]


def test_dry_run_prints_the_comment_and_writes_nothing(wired, monkeypatch, capsys):
    fake = install(monkeypatch, FakeGitHub(issue=issue_payload()))
    assert ri.main(["--issue", "1234", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert ri.MARKER in out and "misakanet_register" in out
    assert [c for c in fake.calls if c[0] in ("POST", "PATCH")] == []


def test_an_unreadable_issue_fails_loudly(wired, monkeypatch, capsys):
    class Boom(FakeGitHub):
        def request(self, method, path, payload=None):
            raise ri.RegisterError("GET /repos/o/r/issues/1234 -> HTTP 404: Not Found")

    install(monkeypatch, Boom(issue=issue_payload()))
    assert ri.main(["--issue", "1234"]) == 1
    assert "::error::" in capsys.readouterr().out


def test_a_missing_counter_is_a_warning_not_a_failure(wired, monkeypatch, capsys):
    monkeypatch.setattr(ri, "fetch_node_counter", lambda url=ri.COUNTER_URL: None)
    fake = install(monkeypatch, FakeGitHub(issue=issue_payload()))
    assert ri.main(["--issue", "1234"]) == 0
    assert ("POST", "/repos/o/r/issues/1234/comments") in [(m, p) for m, p, _ in fake.calls]


def test_the_node_id_is_taken_from_the_issue_when_another_channel_made_it(wired, monkeypatch, capsys):
    fake = install(monkeypatch, FakeGitHub(issue=issue_payload(title="join: Misaka10074", labels=())))
    assert ri.main(["--issue", "1234", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Misaka10074" in out
    assert [c for c in fake.calls if c[0] in ("POST", "PATCH")] == []
