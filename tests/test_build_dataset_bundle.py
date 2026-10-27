#!/usr/bin/env python3
"""`scripts/build_dataset_bundle.py` — the arithmetic and the manifest, not the upload.

Why a test for a packaging script
---------------------------------
The bundle is the artifact the project will be *cited* by, and every failure mode here is quiet:

* a file copied under the wrong name still uploads, and the manifest still lists six entries;
* a stale `sha256` still parses — it just describes bytes nobody can verify;
* a missing license still renders, and the consumer finds out when they use it.

So the properties pinned here are the ones that make the bundle trustworthy: every listed file exists
with exactly the recorded size and hash, both licenses are named and attributable per file, the counts
match the files, and two runs over the same tree agree byte-for-byte apart from the timestamp.

The upload itself (wrangler, R2, DNS) is deliberately out of scope — it needs credentials and lives in
`.github/workflows/publish-dataset.yml`.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import build_dataset_bundle as bundle  # noqa: E402


def test_the_bundle_carries_every_declared_file_with_the_recorded_bytes(tmp_path):
    manifest = bundle.build(tmp_path, version="test")

    assert len(manifest["files"]) == len(bundle.FILES)
    for entry in manifest["files"]:
        path = tmp_path / entry["path"]
        assert path.exists(), entry["path"]
        assert path.stat().st_size == entry["bytes"], entry["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"], entry["path"]


def test_both_licenses_are_named_and_every_file_has_one(tmp_path):
    manifest = bundle.build(tmp_path, version="test")

    assert set(manifest["licenses"]) == {"Apache-2.0", "CC0-1.0"}
    for entry in manifest["files"]:
        assert entry["license"] in manifest["licenses"], entry["path"]
        assert manifest["licenses"][entry["license"]]["url"].startswith("https://")
    # The corpus is Apache-2.0 because that is what contributors submitted under; the benchmark
    # artifacts are the project's own and are dedicated to the public domain.
    assert {e["path"] for e in manifest["files"] if e["license"] == "Apache-2.0"} == {
        "lessons.jsonl", "lessons.json"}
    assert all(e["license"] == "CC0-1.0"
               for e in manifest["files"] if e["path"].startswith("benchmarks/"))


def test_license_texts_travel_with_the_data(tmp_path):
    bundle.build(tmp_path, version="test")

    assert "Apache License" in (tmp_path / "LICENSE").read_text(encoding="utf-8")[:2000]
    cc0 = (tmp_path / "LICENSE-CC0").read_text(encoding="utf-8")
    assert "CC0 1.0" in cc0 and "creativecommons.org/publicdomain/zero/1.0" in cc0


def test_counts_describe_the_files_not_a_hardcoded_number(tmp_path):
    manifest = bundle.build(tmp_path, version="test")

    assert manifest["counts"]["lessons"] == bundle.count_jsonl(REPO / "data/okf/lessons.jsonl")
    assert manifest["counts"]["queries"] == bundle.count_jsonl(
        REPO / "docs/benchmarks/retrieval-l1-267-queries.jsonl")
    assert manifest["counts"]["benchmarks"] == sum(
        1 for e in manifest["files"] if e["path"].startswith("benchmarks/"))


def test_two_runs_agree_except_for_the_timestamp(tmp_path):
    first = bundle.build(tmp_path / "a", version="test")
    second = bundle.build(tmp_path / "b", version="test")

    first.pop("generated_at"), second.pop("generated_at")
    assert first == second, "the same tree must produce the same bundle"
    assert first["source_commit"] == second["source_commit"]


def test_a_missing_source_file_is_an_error_rather_than_a_smaller_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "FILES", bundle.FILES + (
        ("docs/benchmarks/does-not-exist.json", "missing.json", "CC0-1.0", "application/json"),))
    with pytest.raises(SystemExit) as exc:
        bundle.build(tmp_path, version="test")
    assert "does-not-exist.json" in str(exc.value)


def test_check_mode_writes_nothing(tmp_path, capsys):
    out = tmp_path / "never"
    assert bundle.main(["--out", str(out), "--check"]) == 0
    assert not out.exists()
    printed = json.loads(capsys.readouterr().out.split("\n", 1)[1])
    assert printed["dataset"] == "misakanet-lessons"
    assert printed["citation"].startswith("MisakaNet contributors")


def test_every_file_declares_a_content_type_the_browser_will_not_sniff_wrong(tmp_path):
    manifest = bundle.build(tmp_path, version="test")
    allowed = {"application/json", "application/x-ndjson", "text/plain"}
    assert {e["content_type"] for e in manifest["files"]} <= allowed
