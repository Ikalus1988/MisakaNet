#!/usr/bin/env python3
"""The IndexNow pipeline, tested end to end without a network call.

What this file pins, and why each piece needs a test rather than a review:

* **The key file.** IndexNow proves ownership by fetching `https://misakanet.org/<key>.txt` and
  checking that the file *contains* the key, so the name and the content have to be the same 32
  lowercase hex characters. Renaming one without the other publishes a URL whose body does not
  match the key the payload advertises — the endpoint answers 403 and nothing on this site notices.
* **The single source of truth.** The workflow names the key file, and the name is derived here by
  globbing `docs/*.txt` for the key pattern. That makes a half-done rename a test failure instead of
  a silent 403 on the next push.
* **The URL mapping.** The site does not serve `/foo.html`; it serves `/foo` (307 from the `.html`
  form) and `/lessons/<slug>/` (307 from the slashless form). The mapping lives in
  `scripts/indexnow_submit.py` so these tests drive the real function instead of grepping YAML.
* **The failure split.** A failed POST is logged and stays green (this workflow must never hold up a
  deploy); a run that never attempted a submission (missing key, empty URL list) exits 2, because a
  pipeline that looks alive and sends nothing is the failure mode worth catching.

Every test is offline: the sitemap is read from disk, git is never invoked, and the two POST tests
replace `urlopen` with a recorder.
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML reads the workflow's triggers and steps")

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
WORKFLOW = REPO / ".github" / "workflows" / "indexnow.yml"

sys.path.insert(0, str(REPO))

from scripts import indexnow_submit as ix  # noqa: E402

KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────

def key_files() -> list[Path]:
    """Every `docs/*.txt` whose stem is a 32-character lowercase hex key."""
    return sorted(path for path in DOCS.glob("*.txt") if KEY_PATTERN.fullmatch(path.stem))


def the_key_file() -> Path:
    files = key_files()
    assert len(files) == 1, (
        f"expected exactly one IndexNow key file at the docs root, found {[p.name for p in files]}")
    return files[0]


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def triggers() -> dict:
    data = workflow()
    # PyYAML resolves the bare key `on` to the boolean True (YAML 1.1), the same quirk
    # `tests/test_workflow_inventory.py` documents.
    return data.get("on") or data.get(True) or {}


def submit_step() -> dict:
    steps = workflow()["jobs"]["submit"]["steps"]
    matches = [step for step in steps if "scripts/indexnow_submit.py" in str(step.get("run", ""))]
    assert len(matches) == 1, "the workflow must call the mapping/submission script exactly once"
    return matches[0]


# ── the key file ────────────────────────────────────────────────────────────────────────────────

def test_exactly_one_key_file_sits_at_the_docs_root() -> None:
    files = key_files()
    assert len(files) == 1, (
        "the IndexNow key file is `docs/<32 lowercase hex>.txt`; found "
        f"{[p.name for p in files]} — a second one makes the keyLocation ambiguous")
    assert files[0].parent == DOCS


def test_the_key_file_is_named_after_its_content() -> None:
    path = the_key_file()
    content = path.read_text(encoding="utf-8")
    assert KEY_PATTERN.fullmatch(content), (
        f"{path.name} must contain 32 lowercase hex characters, found {content!r}")
    assert content == path.stem, (
        "IndexNow requires the file's content to be the key, and the keyLocation is built from the "
        f"file name: {path.name} contains {content!r}")
    assert len(content) == 32


def test_the_workflow_names_the_key_file_that_exists() -> None:
    path = the_key_file()
    text = WORKFLOW.read_text(encoding="utf-8")
    assert f"docs/{path.name}" in text, (
        f"the workflow does not mention docs/{path.name}. The key file name is derived from the "
        "docs/*.txt that matches the key pattern, so a rename has to land in both places — that is "
        "the point of this test")


# ── the workflow ───────────────────────────────────────────────────────────────────────────────

def test_the_workflow_runs_on_pushes_to_main_that_touch_docs() -> None:
    block = triggers()
    push = block["push"]
    assert push["branches"] == ["main"]
    assert "docs/**" in push["paths"], (
        "the trigger has to cover the whole site; the exclusion below narrows it deliberately")
    assert "!docs/data/**" in push["paths"], (
        "docs/data/** changes no page and would make every feed sync an empty-URL-list failure")
    assert "workflow_dispatch" in block, (
        "a manual entry point is how the sitemap fallback is exercised without waiting for a push")


def test_the_workflow_submits_with_the_mapping_script() -> None:
    step = submit_step()
    assert "python3 scripts/indexnow_submit.py" in step["run"]
    assert "--before" in step["run"] and "--after" in step["run"]
    assert "--wait-for-key" in step["run"], (
        "Workers Builds publishes docs/ asynchronously, so the key file can 404 at submission "
        "time; the wait is what keeps the first push from being validated against nothing")


def test_the_push_range_reaches_the_shell_through_env_not_script_text() -> None:
    step = submit_step()
    env = step["env"]
    assert env["BEFORE_SHA"].strip().endswith("github.event.before }}")
    assert env["AFTER_SHA"].strip().endswith("github.sha }}")
    assert "github.event.before" not in step["run"], (
        "an expression inside `run:` is substituted before bash parses the script; pass it via env")
    assert "github.sha" not in step["run"]


def test_a_never_attempted_submission_is_not_swallowed() -> None:
    """Exit 2 has to reach the job: `continue-on-error` would make a dead pipeline look green."""
    job = workflow()["jobs"]["submit"]
    assert "continue-on-error" not in job
    assert all("continue-on-error" not in step for step in job["steps"]), (
        "the step that submits may not be marked continue-on-error — the script's exit 2 is the "
        "only thing that reports a submission which never happened")


# ── the request the protocol defines ───────────────────────────────────────────────────────────

def test_the_endpoint_is_the_public_indexnow_api() -> None:
    assert ix.ENDPOINT == "https://api.indexnow.org/indexnow"


def test_the_payload_carries_the_four_fields_the_protocol_requires() -> None:
    key = the_key_file().stem
    payload = ix.build_payloads(["https://misakanet.org/"], key,
                                key_location=f"https://misakanet.org/{key}.txt")[0]
    assert set(payload) == {"host", "key", "keyLocation", "urlList"}
    assert payload["host"] == "misakanet.org"
    assert payload["key"] == key
    assert payload["keyLocation"] == f"https://misakanet.org/{key}.txt"
    assert payload["urlList"] == ["https://misakanet.org/"]


def test_urls_are_batched_at_ten_thousand_per_request() -> None:
    urls = [f"https://misakanet.org/page-{number}" for number in range(10_001)]
    payloads = ix.build_payloads(urls, "0" * 32, key_location="https://misakanet.org/0.txt")
    assert [len(payload["urlList"]) for payload in payloads] == [10_000, 1]
    assert payloads[0]["urlList"][0] == urls[0]
    assert payloads[1]["urlList"] == [urls[-1]]


class _Response:
    """The minimum of an `http.client.HTTPResponse` that `post_payload` reads."""

    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    def read(self, _size: int) -> bytes:
        return self._body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def test_the_post_is_json_to_the_indexnow_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.headers.get("Content-type")
        captured["timeout"] = timeout
        return _Response(202)

    monkeypatch.setattr(ix.urllib.request, "urlopen", fake_urlopen)
    payload = ix.build_payloads(["https://misakanet.org/"], "a" * 32,
                                key_location="https://misakanet.org/a.txt")[0]
    assert ix.post_payload(payload) == (202, "")
    assert captured["url"] == "https://api.indexnow.org/indexnow"
    assert captured["body"] == payload
    assert captured["content_type"] == "application/json; charset=utf-8"
    assert captured["timeout"] == ix.TIMEOUT_SECONDS


def test_the_key_live_probe_compares_the_body_with_the_key(monkeypatch) -> None:
    def fake_urlopen(url, timeout=None):
        return _Response(200, b"a" * 32 + b"\n")

    monkeypatch.setattr(ix.urllib.request, "urlopen", fake_urlopen)
    assert ix.key_is_live("https://misakanet.org/" + "a" * 32 + ".txt", "a" * 32) == (
        True, "HTTP 200")


def test_the_key_live_probe_reports_a_404_instead_of_raising(monkeypatch) -> None:
    def fake_urlopen(url, timeout=None):
        raise ix.urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))

    monkeypatch.setattr(ix.urllib.request, "urlopen", fake_urlopen)
    assert ix.key_is_live("https://misakanet.org/" + "a" * 32 + ".txt", "a" * 32) == (
        False, "HTTP 404")


def test_waiting_for_the_key_only_warns_when_it_never_arrives() -> None:
    messages: list[str] = []

    def live(_location: str, _key: str) -> tuple[bool, str]:
        return True, "HTTP 200"

    def down(_location: str, _key: str) -> tuple[bool, str]:
        return False, "HTTP 404"

    location = "https://misakanet.org/k.txt"
    assert ix.wait_for_key(location, "k" * 32, 0, log=messages.append, poll=live) is True
    assert ix.wait_for_key(location, "k" * 32, 0, log=messages.append, poll=down) is False
    assert any("not serving the key" in message for message in messages), messages


def test_an_http_error_is_an_answer_not_an_exception(monkeypatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise ix.urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b"key not found"))

    monkeypatch.setattr(ix.urllib.request, "urlopen", fake_urlopen)
    payload = ix.build_payloads(["https://misakanet.org/"], "b" * 32,
                                key_location="https://misakanet.org/b.txt")[0]
    assert ix.post_payload(payload) == (403, "key not found")


# ── docs/ path -> canonical URL ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("path", "url"), [
    ("docs/index.html", "https://misakanet.org/"),
    ("docs/start.html", "https://misakanet.org/start"),
    ("docs/lessons/auto-merge-ci-pipeline/index.html",
     "https://misakanet.org/lessons/auto-merge-ci-pipeline/"),
    ("docs/topics/security/index.html", "https://misakanet.org/topics/security/"),
    ("docs/troubleshooting.md", "https://misakanet.org/troubleshooting.md"),
])
def test_a_changed_page_maps_to_the_url_the_site_serves(path: str, url: str) -> None:
    assert ix.public_url_for_path(path) == url


@pytest.mark.parametrize("path", [
    "docs/_headers",
    "docs/_redirects",
    "docs/_routes.json",
    "docs/_lessons_count.txt",
    "docs/sitemap.xml",
    "docs/robots.txt",
    "docs/data/lessons.json",
    "docs/assets/og-card.jpg",
    "docs/.well-known/mcp.json",
    "lessons/auto-merge-ci-pipeline.md",
    "README.md",
])
def test_a_non_page_path_is_not_submitted(path: str) -> None:
    assert ix.public_url_for_path(path) is None


def test_the_key_file_itself_is_not_a_page() -> None:
    assert ix.public_url_for_path(f"docs/{the_key_file().name}") is None


def test_a_cjk_lesson_slug_is_percent_encoded() -> None:
    # Slugs are Chinese for a large part of the corpus (measured 2026-11-15); the protocol asks for
    # escaped RFC 3986 URLs, and an unescaped one is not a valid URI.
    slug = next(path.name for path in (DOCS / "lessons").iterdir()
                if any(ord(character) > 127 for character in path.name))
    urls = ix.canonical_urls_for_paths(REPO, [f"docs/lessons/{slug}/index.html"])
    assert len(urls) == 1
    assert "%" in urls[0]
    assert all(ord(character) < 128 for character in urls[0]), urls[0]
    assert ix.encode_url(urls[0]) == urls[0], "an already-encoded URL must not be encoded twice"


def test_the_google_verification_token_is_not_a_page() -> None:
    """It ends in `.html` but contains `google-site-verification: …`, not a document."""
    token = DOCS / "googled7bffcd986dade3f.html"
    assert token.exists(), "the Search Console verification file this rule exists for is gone"
    assert "google-site-verification" in token.read_text(encoding="utf-8")
    assert ix.canonical_urls_for_paths(REPO, ["docs/googled7bffcd986dade3f.html"]) == []


def test_a_deleted_page_is_still_reported_to_the_engines() -> None:
    """The file is gone, so its content cannot be read — and it must not be dropped for that."""
    url = "https://misakanet.org/lessons/a-page-that-was-just-deleted/"
    assert ix.canonical_urls_for_paths(
        REPO, ["docs/lessons/a-page-that-was-just-deleted/index.html"]) == [url]


def test_changed_paths_answers_none_without_a_usable_range() -> None:
    assert ix.changed_paths("", "a" * 40) is None
    assert ix.changed_paths("0" * 40, "a" * 40) is None
    assert ix.changed_paths("a" * 40, "") is None


def test_without_a_range_the_sitemap_is_the_fallback() -> None:
    urls, source = ix.urls_for_run("", "", root=REPO, log=lambda _message: None)
    assert source == "sitemap"
    assert len(urls) > 900, "the fallback is the site's own advertised set, not a handful of pages"
    # Parse rather than `startswith`: a prefix check on a URL is the shape CodeQL reports as
    # incomplete sanitization (`https://misakanet.org.example/` would pass it), and the host is what
    # this asserts anyway.
    hosts = {urllib.parse.urlsplit(url).netloc for url in urls}
    assert hosts == {"misakanet.org"}, f"the fallback submitted another host: {hosts}"
    assert any(url == "https://misakanet.org/" for url in urls), "the homepage is in the set"


# ── exit codes: attempted vs never attempted ──────────────────────────────────────────────────

def test_a_missing_key_file_is_a_hard_failure() -> None:
    missing = "docs/" + "0" * 32 + ".txt"
    assert ix.run(["--key-file", missing, "--dry-run"], log=lambda _message: None) == 2


def test_an_empty_url_list_is_a_hard_failure(monkeypatch) -> None:
    monkeypatch.setattr(ix, "changed_paths", lambda *_args, **_kwargs: [])
    code = ix.run(
        ["--key-file", f"docs/{the_key_file().name}", "--before", "a" * 40, "--after", "b" * 40,
         "--dry-run"],
        log=lambda _message: None)
    assert code == 2, "a run that never attempted a submission must not exit 0"


def test_a_changed_page_is_submitted_with_the_real_key(monkeypatch) -> None:
    sent: list[dict] = []
    monkeypatch.setattr(ix, "changed_paths", lambda *_args, **_kwargs: ["docs/index.html"])
    code = ix.run(
        ["--key-file", f"docs/{the_key_file().name}", "--before", "a" * 40, "--after", "b" * 40],
        poster=lambda payload: (sent.append(payload) or (200, "OK")),
        log=lambda _message: None)
    assert code == 0
    assert len(sent) == 1
    key = the_key_file().stem
    assert sent[0] == {
        "host": "misakanet.org",
        "key": key,
        "keyLocation": f"https://misakanet.org/{key}.txt",
        "urlList": ["https://misakanet.org/"],
    }


def test_a_failed_post_is_logged_and_the_run_stays_green(monkeypatch) -> None:
    monkeypatch.setattr(ix, "changed_paths", lambda *_args, **_kwargs: ["docs/index.html"])
    messages: list[str] = []

    def broken(payload: dict) -> tuple[int, str]:
        raise OSError("network is unreachable")

    code = ix.run(
        ["--key-file", f"docs/{the_key_file().name}", "--before", "a" * 40, "--after", "b" * 40],
        poster=broken, log=messages.append)
    assert code == 0, "a failed POST must not fail the workflow"
    assert any("warning" in message and "network is unreachable" in message
               for message in messages), messages


def test_a_rejected_submission_is_logged_and_the_run_stays_green(monkeypatch) -> None:
    monkeypatch.setattr(ix, "changed_paths", lambda *_args, **_kwargs: ["docs/index.html"])
    messages: list[str] = []
    code = ix.run(
        ["--key-file", f"docs/{the_key_file().name}", "--before", "a" * 40, "--after", "b" * 40],
        poster=lambda _payload: (403, "key not found"), log=messages.append)
    assert code == 0
    assert any("403" in message for message in messages), messages
