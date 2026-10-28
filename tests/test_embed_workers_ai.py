#!/usr/bin/env python3
"""`scripts/embed_workers_ai.py` — batching, resume and retry, without the network.

Why a test for a 120-line embedder
----------------------------------
This script's output became a published number: `bge-m3` pure cosine scores R@1 0.689 and 0.636 on
the cross-lingual bucket, against the live path's 0.455 — the measurement that decided "fix the
gate, not the model". A script that quietly drops a row, restarts from zero after a 400, or writes a
torn line would change that number without changing anything visible, which is the failure mode this
repository has a whole layer of lessons about.

So the three properties the number depends on are pinned here:

* **batching** cuts the input into the request size the endpoint accepts (50 x 6000 chars is a 400;
  10 is not) and never loses or duplicates an id across the cut;
* **resume** skips exactly the ids already written and re-embeds a torn last line instead of
  trusting it — an interrupted run must converge, not corrupt;
* **retry** absorbs 5xx/network failures and gives up loudly, because a silently short vector file
  scores as a recall regression.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import embed_workers_ai as embedder  # noqa: E402


def write_json(path: Path, items: list[dict]) -> Path:
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def test_batching_never_loses_or_duplicates_an_id(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake(account, token, texts, timeout):
        calls.append(list(texts))
        return [[float(len(t))] for t in texts]

    monkeypatch.setattr(embedder, "embed_batch", fake)
    items = [{"id": f"l{i}", "text": "x" * (i + 1)} for i in range(25)]
    out = tmp_path / "v.jsonl"
    written = embedder.run(items, out, "id", "text", "acc", "tok", batch=10, timeout=1)

    assert written == 25
    assert [len(c) for c in calls] == [10, 10, 5], "the batch size is the request cap"
    ids = [json.loads(line)["id"] for line in out.open(encoding="utf-8")]
    assert ids == [item["id"] for item in items], "order and identity survive the cut"


def test_resume_skips_written_ids_and_re_embeds_a_torn_line(tmp_path, monkeypatch):
    out = tmp_path / "v.jsonl"
    out.write_text('{"id": "a", "vector": [1.0]}\n{"id": "b", "vect', encoding="utf-8")

    seen: list[str] = []

    def fake(account, token, texts, timeout):
        seen.extend(texts)
        return [[2.0] for _ in texts]

    monkeypatch.setattr(embedder, "embed_batch", fake)
    items = [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}, {"id": "c", "text": "C"}]
    written = embedder.run(items, out, "id", "text", "acc", "tok", batch=10, timeout=1)

    assert written == 2
    assert seen == ["B", "C"], "a torn line's id is re-embedded, a complete one is skipped"


def test_retry_absorbs_a_transient_failure_then_succeeds(monkeypatch):
    attempts = {"n": 0}

    def flaky(account, token, texts, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("connection reset")
        return [[1.0] for _ in texts]

    monkeypatch.setattr(embedder, "embed_batch", flaky)
    monkeypatch.setattr(embedder.time, "sleep", lambda _s: None)
    assert embedder.embed_with_retry("a", "t", ["x"], 1.0) == [[1.0]]
    assert attempts["n"] == 3


def test_a_permanent_failure_is_loud_rather_than_a_short_file(monkeypatch):
    def always_fails(account, token, texts, timeout):
        raise ValueError("bad request")

    monkeypatch.setattr(embedder, "embed_batch", always_fails)
    monkeypatch.setattr(embedder.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError, match="failed after 5 attempts"):
        embedder.embed_with_retry("a", "t", ["x"], 1.0)


def test_a_mismatched_embedding_count_is_an_error_not_a_truncated_row(tmp_path, monkeypatch):
    def short(account, token, texts, timeout):
        return [[1.0] for _ in texts[:-1]]  # one short

    monkeypatch.setattr(embedder, "embed_batch", short)
    monkeypatch.setattr(embedder.time, "sleep", lambda _s: None)
    with pytest.raises(RuntimeError):
        embedder.run([{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                     tmp_path / "v.jsonl", "id", "text", "acc", "tok", batch=10, timeout=1)


def test_the_id_field_is_selectable_for_the_query_set(tmp_path, monkeypatch):
    monkeypatch.setattr(embedder, "embed_batch", lambda a, t, texts, timeout: [[1.0] for _ in texts])
    out = tmp_path / "q.jsonl"
    items = [{"lesson_id": "l1", "query": "why"}, {"lesson_id": "l2", "query": "how"}]
    embedder.run(items, out, "lesson_id", "query", "acc", "tok", batch=10, timeout=1)
    assert [json.loads(line)["id"] for line in out.open(encoding="utf-8")] == ["l1", "l2"]


def test_the_cli_reads_the_shape_it_documents(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(embedder, "embed_batch", lambda a, t, texts, timeout: [[1.0] for _ in texts])
    src = write_json(tmp_path / "in.json", [{"id": "x", "text": "hello"}])
    token = tmp_path / "tok"
    token.write_text("test-token", encoding="utf-8")
    rc = embedder.main(["--in", str(src), "--out", str(tmp_path / "out.jsonl"),
                        "--token-file", str(token)])
    assert rc == 0
    assert "wrote 1 vectors" in capsys.readouterr().out
