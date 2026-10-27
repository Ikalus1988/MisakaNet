#!/usr/bin/env python3
"""`scripts/embed_vertex.py` — the parts that can be checked without a Vertex AI call.

Why a test for a vector-producing script
----------------------------------------
The script's output is the input to the offline retrieval A/B: 649 lesson vectors and 267 query
vectors, joined back to ids by a harness that never sees the request. Every failure mode here is
silent and expensive in exactly the way an A/B cannot survive — a dropped prediction shifts every
later vector onto the wrong lesson, a duplicate id makes a resumed run skip real work, a wrong id
field names a query after the wrong row, and a batch that is retried when it should not be turns one
bad payload into six. None of those crash; they all produce a confident, wrong number.

So the network is the one thing not tested (the call itself is verified by running the script, and a
live test in CI would need credentials and a proxy). The batch arithmetic, the resume contract, the
line shape, the id-field and dims mapping, and the retry classification are, with a fake transport.

Dims are 256 rather than the default 3072 below: it is a real allowed size, and a 40 KB fixture per
vector would hide the assertions in the diff. `main()` is the only place that rejects sizes outside
`ALLOWED_DIMS`, and that is tested directly.
"""

from __future__ import annotations

import http.client
import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import embed_vertex as embed  # noqa: E402

PLACEHOLDER_CREDENTIAL = "secret-token"
DIMS = 256


# ── fixtures and fakes ─────────────────────────────────────────────────────────────────────────────


def fake_embeddings(texts, *, dims: int = DIMS) -> list[embed.Embedding]:
    """Vectors whose first element encodes text length, so ids and vectors can be cross-checked."""
    return [
        embed.Embedding(values=[float(len(text))] + [0.0] * (dims - 1), tokens=len(text) // 4)
        for text in texts
    ]


def predictions(count: int, *, dims: int = DIMS, tokens: int = 3) -> dict:
    return {
        "predictions": [
            {
                "embeddings": {
                    "statistics": {"token_count": tokens, "truncated": False},
                    "values": [0.25] * dims,
                }
            }
            for _ in range(count)
        ]
    }


def http_error(status: int, message: str) -> urllib.error.HTTPError:
    body = json.dumps({"error": {"code": status, "message": message}}).encode("utf-8")
    return urllib.error.HTTPError(
        "https://example.invalid/predict", status, message, None, io.BytesIO(body)
    )


class FakeResponse:
    def __init__(self, payload: dict | bytes) -> None:
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


def write_rows(tmp_path: Path, rows: list[dict], name: str = "input.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_ids(path: Path) -> list[str]:
    return [record["id"] for record in read_records(path)]


def run_cli(tmp_path: Path, rows: list[dict], *arguments: str):
    """An input file, an output path, a call recorder, and a fake `request_embeddings`."""
    input_path = write_rows(tmp_path, rows)
    out_path = tmp_path / "vectors.jsonl"
    calls: list[tuple[list[str], dict]] = []

    def fake_request(texts, **kwargs):
        calls.append((list(texts), kwargs))
        return fake_embeddings(texts, dims=kwargs["dims"])

    return input_path, out_path, calls, fake_request


# ── batching arithmetic ────────────────────────────────────────────────────────────────────────────


def test_batches_cover_every_row_once_in_order():
    rows = [{"id": f"id-{i}", "text": f"text {i}"} for i in range(649)]

    batches = list(embed.chunked(rows, 50))

    assert len(batches) == 13
    assert [len(batch) for batch in batches] == [50] * 12 + [49]
    # Flattening the batches has to reproduce the input: the API joins vectors to ids by position.
    assert [row["id"] for batch in batches for row in batch] == [row["id"] for row in rows]
    assert batches[-1][-1]["id"] == "id-648"


def test_chunking_edges_and_a_zero_batch_size():
    rows = [{"id": f"id-{i}"} for i in range(100)]

    assert list(embed.chunked([], 50)) == []
    assert [len(batch) for batch in embed.chunked(rows[:1], 50)] == [1]
    assert [len(batch) for batch in embed.chunked(rows, 50)] == [50, 50]

    with pytest.raises(ValueError, match="batch size"):
        list(embed.chunked(rows, 0))


# ── dims -> parameters ────────────────────────────────────────────────────────────────────────────


def test_the_default_size_is_omitted_and_other_sizes_become_a_parameter():
    assert embed.output_parameters(3072) == {}
    for dims in (2048, 1536, 1024, 768, 512, 256):
        assert embed.output_parameters(dims) == {"outputDimensionality": dims}


@pytest.mark.parametrize("dims", [0, -256, 1000, 3071, 4096])
def test_a_size_the_model_cannot_emit_is_refused_before_the_request(dims):
    with pytest.raises(ValueError, match="dims must be one of"):
        embed.output_parameters(dims)


def test_the_payload_is_one_instance_per_text_in_order():
    payload = embed.build_payload(["first", "second"], 768)

    assert payload["instances"] == [{"content": "first"}, {"content": "second"}]
    assert payload["parameters"] == {"autoTruncate": True, "outputDimensionality": 768}
    assert embed.build_payload(["only"], 3072)["parameters"] == {"autoTruncate": True}


# ── output shape and id-field selection ───────────────────────────────────────────────────────────


def test_output_is_one_line_per_row_with_the_selected_id_field(tmp_path):
    rows = [{"slug": "lesson-a", "body": "alpha"}, {"slug": "lesson-b", "body": "bravo"}]
    out = tmp_path / "vectors.jsonl"

    stats = embed.embed_file(
        rows=rows,
        out_path=out,
        id_field="slug",
        field="body",
        dims=DIMS,
        batch_size=1,
        embed=fake_embeddings,
        log=io.StringIO(),
    )

    records = read_records(out)
    assert [record["id"] for record in records] == ["lesson-a", "lesson-b"]
    assert all(set(record) == {"id", "vector", "tokens"} for record in records)
    assert [len(record["vector"]) for record in records] == [DIMS, DIMS]
    assert records[0]["vector"][0] == len("alpha")
    assert all(isinstance(value, float) for value in records[0]["vector"])
    assert stats == embed.RunStats(
        total=2, skipped=0, written=2, failed_ids=[], tokens=2, truncated=0
    )


def test_cli_defaults_read_id_and_text_and_use_the_default_dims(tmp_path, monkeypatch, capsys):
    input_path, out, calls, fake_request = run_cli(
        tmp_path, [{"id": "a", "text": "alpha"}, {"id": "b", "text": "bravo"}]
    )
    monkeypatch.setattr(embed, "request_embeddings", fake_request)
    monkeypatch.setattr(embed, "access_token", lambda **kwargs: "test-token")

    assert embed.main(["--in", str(input_path), "--out", str(out)]) == 0

    assert read_ids(out) == ["a", "b"]
    assert [texts for texts, _ in calls] == [["alpha", "bravo"]]
    assert calls[0][1]["dims"] == 3072
    assert "test-token" not in capsys.readouterr().err


def test_cli_honours_field_id_field_dims_and_batch_size(tmp_path, monkeypatch):
    rows = [{"lesson_id": f"q{i}", "query": f"query {i}"} for i in range(3)]
    input_path, out, calls, fake_request = run_cli(tmp_path, rows)
    monkeypatch.setattr(embed, "request_embeddings", fake_request)
    monkeypatch.setattr(embed, "access_token", lambda **kwargs: "test-token")

    exit_code = embed.main(
        [
            "--in",
            str(input_path),
            "--out",
            str(out),
            "--field",
            "query",
            "--id-field",
            "lesson_id",
            "--dims",
            "768",
            "--batch-size",
            "2",
        ]
    )

    assert exit_code == 0
    assert read_ids(out) == ["q0", "q1", "q2"]
    assert [len(texts) for texts, _ in calls] == [2, 1]
    assert {kwargs["dims"] for _, kwargs in calls} == {768}
    assert [len(record["vector"]) for record in read_records(out)] == [768, 768, 768]


# ── resume ────────────────────────────────────────────────────────────────────────────────────────


def test_a_second_run_skips_every_id_already_in_the_output(tmp_path):
    rows = [{"id": f"id-{i}", "text": f"text {i}"} for i in range(3)]
    out = tmp_path / "vectors.jsonl"
    log = io.StringIO()
    first = embed.embed_file(
        rows=rows,
        out_path=out,
        id_field="id",
        field="text",
        dims=DIMS,
        batch_size=50,
        embed=fake_embeddings,
        log=log,
    )
    assert first.written == 3

    calls: list[list[str]] = []

    def must_not_call(texts):
        calls.append(list(texts))
        return fake_embeddings(texts)

    second = embed.embed_file(
        rows=rows,
        out_path=out,
        id_field="id",
        field="text",
        dims=DIMS,
        batch_size=50,
        embed=must_not_call,
        log=log,
    )

    assert calls == []
    assert second == embed.RunStats(
        total=3, skipped=3, written=0, failed_ids=[], tokens=0, truncated=0
    )
    assert read_ids(out) == ["id-0", "id-1", "id-2"]
    assert "resume: 3 of 3 ids already in" in log.getvalue()


def test_a_partial_output_only_embeds_the_missing_ids(tmp_path):
    rows = [
        {"id": "a", "text": "alpha"},
        {"id": "b", "text": "bravo"},
        {"id": "c", "text": "charlie"},
    ]
    out = tmp_path / "vectors.jsonl"
    out.write_text(json.dumps({"id": "b", "vector": [0.0] * DIMS}) + "\n", encoding="utf-8")
    seen: list[str] = []

    stats = embed.embed_file(
        rows=rows,
        out_path=out,
        id_field="id",
        field="text",
        dims=DIMS,
        batch_size=50,
        embed=lambda texts: fake_embeddings(seen.extend(texts) or texts),
        log=io.StringIO(),
    )

    assert seen == ["alpha", "charlie"]
    assert stats.skipped == 1
    assert stats.written == 2
    assert read_ids(out) == ["b", "a", "c"]
    assert len(read_ids(out)) == len(set(read_ids(out)))


def test_a_torn_final_line_is_dropped_before_appending(tmp_path, capsys):
    out = tmp_path / "vectors.jsonl"
    out.write_text(
        '{"id": "a", "vector": [0.0]}\n{"id": "b", "vector": [1.0, 2.0', encoding="utf-8"
    )
    rows = [{"id": "a", "text": "alpha"}, {"id": "b", "text": "bravo"}]
    seen: list[str] = []

    stats = embed.embed_file(
        rows=rows,
        out_path=out,
        id_field="id",
        field="text",
        dims=DIMS,
        batch_size=50,
        embed=lambda texts: fake_embeddings(seen.extend(texts) or texts),
    )

    # "a" was complete and is kept; the half-written "b" is dropped and re-embedded.
    assert seen == ["bravo"]
    assert stats.skipped == 1
    assert stats.written == 1
    assert read_ids(out) == ["a", "b"]
    assert len(read_records(out)) == 2
    assert "repaired" in capsys.readouterr().err


# ── input validation ─────────────────────────────────────────────────────────────────────────────


def test_duplicate_ids_are_refused_before_any_request(tmp_path):
    rows = [{"id": "a", "text": "one"}, {"id": "a", "text": "two"}]

    with pytest.raises(ValueError, match="duplicate id 'a'"):
        embed.prepare_rows(rows, id_field="id", field="text")

    calls: list[list[str]] = []

    def must_not_call(texts):
        calls.append(list(texts))
        return fake_embeddings(texts)

    out = tmp_path / "vectors.jsonl"
    with pytest.raises(ValueError, match="duplicate id"):
        embed.embed_file(
            rows=rows,
            out_path=out,
            id_field="id",
            field="text",
            dims=DIMS,
            batch_size=2,
            embed=must_not_call,
            log=io.StringIO(),
        )
    assert calls == []
    assert not out.exists()


@pytest.mark.parametrize(
    "row",
    [
        {"id": "a"},  # no text field
        {"id": "a", "text": "   "},  # blank text embeds nothing meaningful
        {"id": "a", "text": 7},  # not a string
        {"text": "hello"},  # no id field
        {"id": "", "text": "hello"},  # blank id
        {"id": 7, "text": "hello"},  # non-string id
    ],
    ids=["missing-text", "blank-text", "nonstring-text", "missing-id", "blank-id", "nonstring-id"],
)
def test_rows_that_cannot_be_embedded_are_refused(row):
    with pytest.raises(ValueError):
        embed.prepare_rows([row], id_field="id", field="text")


# ── response shape ───────────────────────────────────────────────────────────────────────────────


def test_a_short_response_is_an_error_not_a_silent_misalignment():
    payload = {"predictions": [{"embeddings": {"values": [0.0] * DIMS}}]}

    with pytest.raises(embed.PredictError, match="expected 2 predictions, got 1"):
        embed.parse_predictions(payload, expected=2, dims=DIMS)


def test_a_vector_of_the_wrong_width_is_an_error():
    payload = {"predictions": [{"embeddings": {"values": [0.0] * 8}}]}

    with pytest.raises(embed.PredictError, match=f"expected {DIMS}"):
        embed.parse_predictions(payload, expected=1, dims=DIMS)


def test_a_non_finite_value_is_an_error():
    values = [0.0] * DIMS
    values[3] = float("nan")
    payload = {"predictions": [{"embeddings": {"values": values}}]}

    with pytest.raises(embed.PredictError, match="non-finite"):
        embed.parse_predictions(payload, expected=1, dims=DIMS)


# ── retry classification ─────────────────────────────────────────────────────────────────────────

TRANSIENT_FAILURES = [
    pytest.param(lambda: http_error(503, "The service is currently unavailable."), id="503"),
    pytest.param(lambda: http_error(429, "Quota exceeded."), id="429"),
    pytest.param(lambda: urllib.error.URLError("connection refused"), id="network-error"),
    pytest.param(lambda: TimeoutError("timed out"), id="timeout"),
    pytest.param(lambda: http.client.IncompleteRead(b"partial", 4096), id="truncated-body"),
    pytest.param(lambda: http.client.BadStatusLine(""), id="bad-status-line"),
]


@pytest.mark.parametrize("failure", TRANSIENT_FAILURES)
def test_a_transient_failure_is_retried_and_the_next_attempt_wins(failure):
    calls: list[object] = []
    outcomes: list[object] = [failure(), FakeResponse(predictions(1))]

    def fake_urlopen(request, timeout):
        calls.append(request)
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    sleeps: list[float] = []
    embeddings = embed.request_embeddings(
        ["one"],
        token=PLACEHOLDER_CREDENTIAL,
        project="bench-project",
        region="us-central1",
        model="gemini-embedding-001",
        dims=DIMS,
        sleep=sleeps.append,
        urlopen=fake_urlopen,
        log=io.StringIO(),
    )

    assert len(calls) == 2
    assert sleeps == [embed.BASE_DELAY]
    assert embeddings[0].values == [0.25] * DIMS
    assert embeddings[0].tokens == 3
    body = json.loads(calls[0].data)
    assert body["instances"] == [{"content": "one"}]
    assert body["parameters"] == {"autoTruncate": True, "outputDimensionality": DIMS}


def test_a_truncated_json_body_is_retried_instead_of_becoming_a_vector():
    calls: list[object] = []
    outcomes: list[object] = [
        FakeResponse(b'{"predictions": [{"embeddings": {"values": [1.0'),
        FakeResponse(predictions(1)),
    ]

    def fake_urlopen(request, timeout):
        calls.append(request)
        return outcomes.pop(0)

    sleeps: list[float] = []
    embeddings = embed.request_embeddings(
        ["one"],
        token=PLACEHOLDER_CREDENTIAL,
        project="bench-project",
        region="us-central1",
        model="gemini-embedding-001",
        dims=DIMS,
        sleep=sleeps.append,
        urlopen=fake_urlopen,
        log=io.StringIO(),
    )

    assert len(calls) == 2
    assert sleeps == [embed.BASE_DELAY]
    assert embeddings[0].values == [0.25] * DIMS


def test_retries_stop_at_six_attempts():
    calls: list[object] = []

    def always_fail(request, timeout):
        calls.append(request)
        raise http_error(503, "overloaded")

    sleeps: list[float] = []
    with pytest.raises(embed.PredictError, match="gave up after 6 attempts"):
        embed.request_embeddings(
            ["one"],
            token=PLACEHOLDER_CREDENTIAL,
            project="bench-project",
            region="us-central1",
            model="gemini-embedding-001",
            dims=DIMS,
            sleep=sleeps.append,
            urlopen=always_fail,
            log=io.StringIO(),
        )

    assert len(calls) == 6
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0]


def test_a_bad_request_is_not_retried():
    calls: list[object] = []

    def bad_request(request, timeout):
        calls.append(request)
        raise http_error(400, "Request contains an invalid argument.")

    sleeps: list[float] = []
    with pytest.raises(embed.PredictError, match="HTTP 400"):
        embed.request_embeddings(
            ["one"],
            token=PLACEHOLDER_CREDENTIAL,
            project="bench-project",
            region="us-central1",
            model="gemini-embedding-001",
            dims=DIMS,
            sleep=sleeps.append,
            urlopen=bad_request,
            log=io.StringIO(),
        )

    assert len(calls) == 1
    assert sleeps == []


def test_retry_logs_and_errors_never_carry_the_token():
    log = io.StringIO()
    outcomes: list[object] = [http_error(503, "overloaded"), http_error(400, "invalid argument")]

    def flaky(request, timeout):
        outcome = outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    with pytest.raises(embed.PredictError) as excinfo:
        embed.request_embeddings(
            ["one"],
            token=PLACEHOLDER_CREDENTIAL,
            project="bench-project",
            region="us-central1",
            model="gemini-embedding-001",
            dims=DIMS,
            sleep=lambda seconds: None,
            urlopen=flaky,
            log=log,
        )

    assert "attempt 1/6" in log.getvalue()
    assert "secret-token" not in log.getvalue()
    assert "secret-token" not in str(excinfo.value)


# ── exit status ──────────────────────────────────────────────────────────────────────────────────


def test_a_failed_batch_exits_non_zero_and_lists_the_missing_ids(tmp_path, monkeypatch, capsys):
    rows = [{"id": f"id-{i}", "text": f"text {i}"} for i in range(3)]
    input_path = write_rows(tmp_path, rows)
    out = tmp_path / "vectors.jsonl"
    calls: list[list[str]] = []

    def flaky(texts, **kwargs):
        calls.append(list(texts))
        if len(calls) == 2:
            raise embed.PredictError("HTTP 500: overloaded")
        return fake_embeddings(texts, dims=kwargs["dims"])

    monkeypatch.setattr(embed, "request_embeddings", flaky)
    monkeypatch.setattr(embed, "access_token", lambda **kwargs: "test-token")

    exit_code = embed.main(["--in", str(input_path), "--out", str(out), "--batch-size", "1"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing ids (1):" in captured.err
    assert "id-1" in captured.err
    # The other two batches are still on disk: a failed batch costs that batch, not the run.
    assert read_ids(out) == ["id-0", "id-2"]
    assert "test-token" not in captured.err


# ── credentials ──────────────────────────────────────────────────────────────────────────────────


def test_a_token_in_the_environment_is_used_without_calling_gcloud():
    token = embed.access_token(
        gcloud="/definitely/not/a/binary", environ={"VERTEX_ACCESS_TOKEN": "from-env"}
    )
    assert token == "from-env"


def test_a_missing_token_is_a_clear_error_not_a_traceback(tmp_path, monkeypatch):
    monkeypatch.delenv("VERTEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GCLOUD", raising=False)

    with pytest.raises(SystemExit, match="VERTEX_ACCESS_TOKEN"):
        embed.access_token(gcloud=str(tmp_path / "missing-gcloud"), environ={})
