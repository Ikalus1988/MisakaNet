#!/usr/bin/env python3
"""`scripts/push_preflight.py` must catch a value revert and must not cry wolf at an edit.

Why the tool exists is in its own docstring: `gh_push_via_api.py` writes local bytes, so a working copy
that is one release behind silently reverts whatever main gained, and the branch looks internally
consistent while it does. This repository has paid for that twice — a release badge going backwards,
and an `x-release-please-version` line whose value was stale while every test stayed green because the
test asserted the annotation was *present*.

The tests here are mostly about the **negative** direction, because the failure mode of a preflight
check is not missing a revert; it is flagging a legitimate edit until somebody stops running it. A
count sentence that is *reworded* and re-registered in `sync_lesson_count.py` is the documented
workflow, and it necessarily removes the old sentence — so "a managed-shaped line disappeared" is not
evidence of anything. Only "the same wording, a different number" is.

The positive cases are read out of the repository's own files rather than written from imagination: if
the managed-line patterns stop matching the real sentences they are supposed to protect, these tests go
red instead of the gate going quiet.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts import push_preflight as pp  # noqa: E402


# ── the pure pieces ─────────────────────────────────────────────────────────

def test_classify_names_the_four_states():
    remote = {"a": "sha1", "b": "sha2", "c": "sha3"}
    local = {"a": "sha1", "b": "different", "c": None}
    assert pp.classify(remote, local) == {"a": "SAME", "b": "DIFF", "c": "ABSENT"}


def test_a_path_only_on_main_is_reported_as_absent_not_ignored():
    """The dangerous state: the checkout is behind. Silent absence is what makes a revert invisible."""
    state = pp.classify({"new-on-main": "sha"}, {})
    assert state == {"new-on-main": "ABSENT"}


def test_removals_is_a_multiset_not_a_set():
    """A line that appears twice on main and once locally is one line of loss, not zero."""
    remote = "x\ny\ny\n"
    local = "x\ny\n"
    assert pp.removals(remote, local) == ["y"]


def test_a_value_behind_main_is_a_revert():
    """main's number is larger, so pushing my copy would revert it — the loss the tool is for."""
    remote = "MisakaNet searches 414+ failure lessons so an agent skips the\n"
    local = "MisakaNet searches 411+ failure lessons so an agent skips the\n"
    lost = pp.removals(remote, local)
    assert _directions(lost, local) == {"behind": lost}


def test_a_value_ahead_of_main_is_not_called_a_revert():
    """The case that produced issue #2274: a legitimate bump, mislabelled as a revert.

    `docs/CI.md`'s section count went 22 -> 23 because a row was added. The first version of this tool
    called that `VALUE REVERTED — pushing this reverts main's value to your older one`, which is backwards:
    it also fires on every legitimate count bump, and the repo's documented workflow includes rewording and
    re-registering those sentences. Ahead is reported, not failed — whether it is safe depends on files the
    tool cannot see.
    """
    remote = "## 数据/索引（22）\n"
    local = "## 数据/索引（23）\n"
    lost = pp.removals(remote, local)
    assert _directions(lost, local) == {"ahead": lost}
    assert _reverts(lost, local) == [], "a count bump must not be reported as a revert"


def test_a_number_that_moves_without_a_wording_change_only_in_whitespace_is_ignored():
    """A line whose only difference is spacing has no number change to judge."""
    lost = ["the build takes 30 seconds   "]
    assert pp.value_changes(lost, "the build takes 30 seconds\n") == []


def test_a_reworded_sentence_is_not_a_value_revert():
    """The documented workflow: rewrite the sentence, re-register it in sync_lesson_count.py.

    The old sentence is *removed* by that edit, so a check that fails on managed-shaped removals would
    block the workflow it is supposed to protect. Wording differs -> not a revert.
    """
    remote = "MisakaNet searches 411+ failure lessons so an agent skips the\n"
    local = "MisakaNet searches 411+ indexed failure lessons so agents skip the\n"
    lost = pp.removals(remote, local)
    assert lost, "sanity: the old sentence really is removed by the rewording"
    assert _reverts(lost, local) == []


def test_a_line_without_numbers_is_never_a_value_revert():
    remote = "See docs/agents/repo-operations.md for the full manual.\n"
    local = "See docs/agents/repo-operations.md.\n"
    lost = pp.removals(remote, local)
    assert _reverts(lost, local) == []


def test_a_version_line_going_backwards_is_a_value_revert():
    """The second recorded incident, in the shape it actually occurred."""
    remote = '  version: env.MCP_VERSION || "2.35.0", // x-release-please-version\n'
    local = '  version: env.MCP_VERSION || "2.34.0", // x-release-please-version\n'
    lost = pp.removals(remote, local)
    assert _directions(lost, local)["behind"], "a stale annotated version must be reported"


def _directions(lost, local_text):
    """`{direction: [line, ...]}` — the tests are about which direction a change goes."""
    out: dict[str, list[str]] = {}
    for line, direction in pp.value_changes(lost, local_text):
        out.setdefault(direction, []).append(line)
    return out


def _reverts(lost, local_text):
    return _directions(lost, local_text).get("behind", [])


# ── the patterns must match the repository's real managed lines ─────────────

def _line_containing(path: str, pattern: str) -> str:
    """The first line of `path` matching `pattern` (a regex) — the fixture comes from the file."""
    text = (REPO / path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if re.search(pattern, line):
            return line
    pytest.fail(f"{path} has no line matching {pattern!r} — the fixture moved, fix this test")


def test_patterns_match_the_real_lesson_count_sentence():
    line = _line_containing("docs/llms.txt", r"^\s*[-*]?\s*\d[\d,]*\b.*\blessons?\b")
    assert pp.managed([line]), f"the lesson-count pattern does not match {line!r}"
    # And the value-revert rule must fire on that same real sentence with a different number, which is
    # the state this repository has actually been in (the local copy one count behind main).
    older = re.sub(r"\d[\d,]*", "1", line, count=1)
    assert _directions([older], line), (
        f"a count sentence whose number moved is not treated as a value revert: {older!r} vs {line!r}"
    )


def test_patterns_match_the_real_registered_node_sentence():
    line = _line_containing("docs/llms.txt", "registered nodes")
    assert pp.managed([line]), f"the node-count pattern does not match {line!r}"


def test_patterns_match_a_real_annotated_version_line():
    src = (REPO / "workers/register-proxy-sw.js").read_text(encoding="utf-8")
    annotated = [l for l in src.splitlines() if "x-release-please-version" in l]
    assert annotated, "workers/register-proxy-sw.js no longer carries an annotated version line"
    assert pp.managed(annotated), "the release-please pattern does not match the real annotated line"


def test_the_markdown_bold_sentence_also_matches():
    """README's count sentence has `**` inside it; a pattern that needs a plain space misses it.

    This is the exact line whose removal the tool failed to flag on its first run — the pattern was
    written against an imagined shape rather than the file.
    """
    line = _line_containing("README.md", "indexed failure-recovery lessons")
    assert pp.managed([line]), f"a bolded count sentence is not recognised: {line!r}"


# ── non-ASCII paths ─────────────────────────────────────────────────────────

def test_tracked_paths_are_not_octal_escaped():
    """`git ls-files` quotes non-ASCII paths unless `core.quotepath=false`.

    Without the flag every CJK lesson filename becomes a fabricated "only local" finding — a mistake
    made while writing the tool, so it is pinned here rather than remembered.
    """
    tracked = pp.tracked_paths()
    escaped = [p for p in tracked if p.startswith('"') or re.search(r"\\[0-7]{3}", p)]
    assert not escaped, f"{len(escaped)} path(s) came back quoted/escaped, e.g. {escaped[:3]}"
    # The corpus has non-ASCII filenames; if it ever stops, this test should be reconsidered rather
    # than silently passing for the wrong reason.
    non_ascii = [p for p in tracked if any(ord(c) > 0x2FFF for c in p)]
    assert non_ascii, "expected at least one non-ASCII tracked path to make this test meaningful"


# ── the network here is flaky, and a preflight that fails spuriously gets skipped ──

class _Response:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_a_truncated_body_is_retried(monkeypatch):
    """`IncompleteRead` on an otherwise successful response is what this network actually does.

    Measured while fetching this repository's own tree on the first run of this script — the failure is
    not a clean connection error, so a plain `except URLError` lets it escape as a traceback.
    """
    import http.client
    calls = {"n": 0}

    def flaky(request, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise http.client.IncompleteRead(b"partial", 100)
        return _Response(b"{}")

    monkeypatch.setattr(pp.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(pp.time, "sleep", lambda _s: None)
    assert pp._get("https://example.invalid", "t") == b"{}"
    assert calls["n"] == 3


def test_persistent_failure_is_a_clear_error_not_a_traceback(monkeypatch):
    monkeypatch.setattr(pp.urllib.request, "urlopen",
                        lambda request, timeout=None: (_ for _ in ()).throw(TimeoutError("nope")))
    monkeypatch.setattr(pp.time, "sleep", lambda _s: None)
    with pytest.raises(SystemExit) as exc:
        pp._get("https://example.invalid", "t")
    assert "unreachable" in str(exc.value)


def test_an_http_error_is_not_retried(monkeypatch):
    """A 404 is an answer. Retrying it just makes the preflight slow before printing the same thing."""
    import urllib.error
    calls = {"n": 0}

    def not_found(request, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(pp.urllib.request, "urlopen", not_found)
    monkeypatch.setattr(pp.time, "sleep", lambda _s: None)
    with pytest.raises(urllib.error.HTTPError):
        pp._get("https://example.invalid", "t")
    assert calls["n"] == 1


def test_main_reports_a_flaky_link_as_exit_2_not_a_crash(stubbed, monkeypatch):
    def dead(*_a, **_k):
        raise ConnectionResetError("connection reset by peer")

    monkeypatch.setattr(pp, "remote_tree", dead)
    assert pp.main(["--all"]) == 2

# ── which credential goes to which host ─────────────────────────────────────

def _creds(tmp_path, *lines):
    path = tmp_path / ".git-credentials"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_credential_for_another_host_is_not_used(tmp_path):
    """The reason CodeQL flagged the first version (`py/incomplete-url-substring-sanitization`, #285).

    `"github.com" in line` also accepts `notgithub.com` and `github.com.example.net`. A credential file
    is exactly where a second host is likely to appear, and this function decides which secret to send
    where — so the host is compared after parsing.
    """
    path = _creds(tmp_path,
                  "https://someone:pw-for-lookalike@notgithub.com",
                  "https://someone@github.com.example.net:pw-for-subdomain",
                  "https://someone:right-one@github.com")
    assert pp.credentials_token(path) == "right-one"


def test_lookalike_hosts_on_their_own_yield_nothing(tmp_path):
    for line in ("https://u:pw@notgithub.com",
                 "https://u:pw@github.com.example.net",
                 "https://u:pw@evil.example/github.com",
                 "https://u:pw@githubxcom"):
        assert pp.credentials_token(_creds(tmp_path, line)) is None, f"accepted {line!r}"


def test_the_ordinary_forms_still_resolve(tmp_path):
    assert pp.credentials_token(_creds(tmp_path, "https://u:tok@github.com")) == "tok"
    assert pp.credentials_token(_creds(tmp_path, "https://u:tok@github.com:443")) == "tok"
    assert pp.credentials_token(_creds(tmp_path, "https://u:tok@GITHUB.COM")) == "tok"
    # A token that was percent-encoded into the file comes back decoded, like git would read it.
    assert pp.credentials_token(_creds(tmp_path, "https://u:a%2Fb@github.com")) == "a/b"


def test_a_file_with_no_github_entry_yields_nothing(tmp_path):
    assert pp.credentials_token(_creds(tmp_path, "https://u:pw@gitlab.com", "")) is None


def test_the_environment_wins_over_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    assert pp.resolve_token() == "from-env"


def test_resolve_token_reads_a_real_working_tree_shape(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    path = _creds(tmp_path, "https://Ikalus1988:gho_example@github.com")
    monkeypatch.setattr(pp.pathlib.Path, "home", staticmethod(lambda: tmp_path))
    assert pp.resolve_token() == "gho_example"


# ── exit codes, with the network stubbed ────────────────────────────────────

@pytest.fixture
def stubbed(monkeypatch):
    """Feed the CLI a remote tree and file contents without touching the network."""
    state = {"remote": {}, "files": {}, "ref": "main", "sha": "deadbeef" * 5}

    def fake_tree(repo, ref, token):
        state["ref"] = ref
        return state["sha"], dict(state["remote"])

    def fake_bytes(repo, ref, path, token):
        return state["files"][path].encode("utf-8")

    monkeypatch.setattr(pp, "remote_tree", fake_tree)
    monkeypatch.setattr(pp, "remote_bytes", fake_bytes)
    monkeypatch.setattr(pp, "resolve_token", lambda: "stub-token")
    return state


def test_named_file_identical_to_main_fails(stubbed, tmp_path):
    path = "README.md"
    local = (REPO / path).read_bytes()
    import hashlib
    stubbed["remote"] = {path: hashlib.sha1(b"blob " + str(len(local)).encode() + b"\0" + local).hexdigest()}
    # A local blob hash and a remote tree hash are both git blob SHAs, so compute the local one the
    # same way the script does and put *that* in the remote tree to model "identical".
    local_sha = pp.local_blob_hashes([path])[path]
    stubbed["remote"] = {path: local_sha}
    assert pp.main([path]) == 1


def test_named_file_absent_locally_fails(stubbed):
    stubbed["remote"] = {"no/such/file.md": "0" * 40}
    assert pp.main(["no/such/file.md"]) == 1


def test_named_new_file_passes(stubbed):
    stubbed["remote"] = {}
    assert pp.main(["scripts/push_preflight.py"]) == 0


def test_named_file_with_a_value_revert_fails(stubbed):
    """End-to-end through `main()`: a locally older count must make the push refuse."""
    path = "docs/llms.txt"
    local_text = (REPO / path).read_text(encoding="utf-8")
    count = re.search(r"^\s*[-*]?\s*(\d[\d,]*)\b.*\blessons?\b", local_text, re.M)
    assert count, "docs/llms.txt no longer carries a lesson-count line"
    newer = local_text.replace(count.group(1), str(int(count.group(1).replace(",", "")) + 3), 1)
    stubbed["remote"] = {path: "f" * 40}
    stubbed["files"] = {path: newer}
    assert pp.main([path]) == 1, "a remote count ahead of the local one must stop the push"


def test_named_file_with_a_reworded_sentence_passes(stubbed):
    """The other direction, end to end: an edit that removes a managed-shaped line is not a revert."""
    path = "docs/llms.txt"
    local_text = (REPO / path).read_text(encoding="utf-8")
    remote_text = local_text.replace("indexed failure lessons", "indexed failure-recovery lessons", 1)
    stubbed["remote"] = {path: "f" * 40}
    stubbed["files"] = {path: remote_text}
    assert pp.main([path]) == 0, "rewording a count sentence must not be reported as a value revert"


def test_all_fails_when_the_checkout_is_behind(stubbed):
    stubbed["remote"] = {"only/on/main.md": "a" * 40}
    assert pp.main(["--all"]) == 1


def test_all_passes_when_the_checkout_is_complete(stubbed):
    stubbed["remote"] = {}
    assert pp.main(["--all"]) == 0


def test_a_path_that_is_not_a_string_is_a_usage_error():
    """`--all` with no paths is fine; neither is a usage error, and argparse exits 2."""
    with pytest.raises(SystemExit) as exc:
        pp.main([])
    assert exc.value.code == 2


def test_the_problem_advice_matches_the_problem_kind(stubbed, tmp_path, capsys):
    """An identical file is not a number problem, and saying it is sends the reader the wrong way.

    The first version printed the "same wording, larger number on main" explanation for every kind,
    including "identical to main" — found by running the tool on a file whose change had just been merged.
    """
    path = "docs/llms.txt"
    stubbed["remote"] = {path: pp.local_blob_hashes([path])[path]}
    assert pp.main([path]) == 1
    out = capsys.readouterr().out
    assert "(identical)" in out
    # Presence *and* absence. The first version asserted only the absence of the wrong advice, so an output
    # that printed no advice at all passed — which is what collapsing the per-kind loop does. Asserting
    # absence is not asserting the right thing happened; this is the third time in one session that a test
    # of mine was weak in exactly this direction.
    # A fragment unique to the *advice* line. "nothing to push" also appears in the per-file line above it,
    # so asserting that string proved nothing about the advice — the fourth assertion of mine in one session
    # to be satisfied by text that came from somewhere else.
    assert "re-check that you edited the file" in out, f"the identical-file advice is missing:\n{out}"
    assert "reverts it" not in out, f"the revert advice was printed for an identical file:\n{out}"


# ── the branch you are about to push to may already be merged ───────────────

def _pulls(monkeypatch, payload):
    monkeypatch.setattr(pp, "_get", lambda url, token, accept=None, attempts=3: json.dumps(payload).encode())


def test_pushing_to_an_already_merged_branch_is_refused(monkeypatch):
    """The trap that cost two PRs in one session: the commit lands on the branch and nowhere else.

    `gh_push_via_api.py --base <branch> --branch <branch>` is the documented way to add a commit to an open
    PR, and auto-merge here is fast — so the branch is often merged before the follow-up arrives. Nothing
    fails; the commit simply exists only on a branch nobody reads again.
    """
    _pulls(monkeypatch, [
        {"merged_at": None, "base": {"ref": "main"}, "merge_commit_sha": "0" * 40},
        {"merged_at": "2026-09-26T03:33:15Z", "base": {"ref": "main"}, "merge_commit_sha": "8ce336f613aa"},
    ])
    message = pp.merged_branch_problem("o/r", "my/branch", "t")
    assert message and "already merged" in message
    assert "8ce336f613" in message, "the message should name the merge commit so the reader can check"
    assert "new branch" in message


def test_an_unmerged_branch_is_fine(monkeypatch):
    _pulls(monkeypatch, [{"merged_at": None, "base": {"ref": "main"}, "merge_commit_sha": "0" * 40}])
    assert pp.merged_branch_problem("o/r", "my/branch", "t") is None


def test_a_closed_but_unmerged_pr_does_not_block_the_push(monkeypatch):
    """Closed without merging is the normal state of a branch being iterated on."""
    _pulls(monkeypatch, [{"merged_at": None, "state": "closed", "base": {"ref": "main"},
                          "merge_commit_sha": None}])
    assert pp.merged_branch_problem("o/r", "my/branch", "t") is None


def test_main_refuses_before_reporting_anything(monkeypatch, capsys, stubbed):
    monkeypatch.setattr(pp, "merged_branch_problem", lambda repo, branch, token: "already merged (test)")
    assert pp.main(["--branch", "my/branch", "docs/llms.txt"]) == 1
    assert "already merged" in capsys.readouterr().out
