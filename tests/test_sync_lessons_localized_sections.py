"""Unit tests for multi-language section alias extraction in scripts/sync_lessons_to_d1.py (#1738).

Ensures localized lessons (pt-br, es, ru, hi, id, tr, vi) parse
problem, root_cause, solution, and verification sections accurately.
"""

from __future__ import annotations

from pathlib import Path
import pytest
import scripts.sync_lessons_to_d1 as sync_lessons_to_d1
from scripts.sync_lessons_to_d1 import REPO, parse_lesson, split_sections


@pytest.mark.parametrize(
    "lang,body,expected_problem,expected_cause,expected_sol,expected_verif",
    [
        (
            "pt-br",
            "## Problema\nO pip dá timeout.\n## Causa raíz\nProxy corporativo.\n## Solução\nConfigure o proxy.\n## Verificação\nExecute pip install.",
            "O pip dá timeout.",
            "Proxy corporativo.",
            "Configure o proxy.",
            "Execute pip install.",
        ),
        (
            "es",
            "## Problema\ncurl falla con timeout.\n## Causa raíz\nFalta certificado.\n## Solución\nAgregar certificado.\n## Verificación\ncurl retorna 200.",
            "curl falla con timeout.",
            "Falta certificado.",
            "Agregar certificado.",
            "curl retorna 200.",
        ),
        (
            "ru",
            "## Проблема\nСкрипт падает.\n## Коренная причина\nНет set -e.\n## Решение\nДобавить set -e.\n## Проверка\nbash job.sh.",
            "Скрипт падает.",
            "Нет set -e.",
            "Добавить set -e.",
            "bash job.sh.",
        ),
        (
            "hi",
            "## समस्या\nशेल स्क्रिप्ट विफल.\n## मूल कारण\nचर अनुपलब्ध.\n## समाधान\nचर सेट करें.\n## सत्यापन\nसफल निष्पादन.",
            "शेल स्क्रिप्ट विफल.",
            "चर अनुपलब्ध.",
            "चर सेट करें.",
            "सफल निष्पादन.",
        ),
        (
            "id",
            "## Masalah\nSkrip bash error.\n## Akar Penyebab\nTidak ada set -euo pipefail.\n## Solusi\nTambahkan konfigurasi.\n## Verifikasi\nbash -n job.sh.",
            "Skrip bash error.",
            "Tidak ada set -euo pipefail.",
            "Tambahkan konfigurasi.",
            "bash -n job.sh.",
        ),
        (
            "tr",
            "## Sorun\nBetik hata veriyor.\n## Kök Neden\nEksik ayarlar.\n## Çözüm\nAyar dosyasını ekleyin.\n## Doğrulama\nBetik çalıştırın.",
            "Betik hata veriyor.",
            "Eksik ayarlar.",
            "Ayar dosyasını ekleyin.",
            "Betik çalıştırın.",
        ),
        (
            "vi",
            "## Vấn đề\nTập lệnh lỗi.\n## Nguyên nhân gốc rễ\nThiếu biến môi trường.\n## Giải pháp\nThiết lập biến.\n## Xác minh\nChạy thử.",
            "Tập lệnh lỗi.",
            "Thiếu biến môi trường.",
            "Thiết lập biến.",
            "Chạy thử.",
        ),
    ],
)
def test_split_sections_multilingual(
    lang, body, expected_problem, expected_cause, expected_sol, expected_verif
):
    sections = split_sections(body)
    assert sections["problem"] == expected_problem
    assert sections["root_cause"] == expected_cause
    assert sections["solution"] == expected_sol
    assert sections["verification"] == expected_verif


def test_existing_localized_lessons_parse_non_empty():
    """Assert existing localized lessons in the repository extract non-empty sections."""
    sample_files = [
        REPO / "lessons/contrib/pt-br/instalacao-pip-timeout-proxy.md",
        REPO / "lessons/contrib/es/proxy-corporativo-curl-timeout.md",
    ]
    for file_path in sample_files:
        assert file_path.exists(), f"Sample file {file_path} must exist"
        record = parse_lesson(file_path)
        assert record is not None, f"Failed to parse {file_path}"
        assert record["problem"], f"Problem empty for {file_path}"
        assert record["root_cause"], f"Root cause empty for {file_path}"
        assert record["solution"], f"Solution empty for {file_path}"
        assert record["verification"], f"Verification empty for {file_path}"


def test_the_synced_row_carries_the_derived_evidence_level(tmp_path, monkeypatch):
    """The served trust field has to match the published one (#2080).

    Most lessons do not declare `evidence_level`; they earn it from their content, and the
    public index derives it (`update_lessons_json.py`). The D1 sync stored the raw frontmatter
    only, so those rows reached the API with `evidence_level: ""` on every hit — the field
    looked *provided and blank*, while the GitHub-snapshot path answered correctly. Measured
    against the live database on 2026-09-23: the stored frontmatter of two libnss3 lessons did
    not contain the key at all, while the corpus said E2 and E0 for them.
    """
    import json as _json

    # `parse_lesson` records `path` relative to REPO, so the module's REPO points at the temp
    # tree instead of scratch lessons being written into the repository.
    monkeypatch.setattr(sync_lessons_to_d1, "REPO", tmp_path)
    lesson = tmp_path / "no-level-declared.md"
    lesson.write_text(
        "---\ntitle: a lesson that never declared a level\ndomain: devops\ntags: [ci]\n---\n\n"
        "## Problem\n\nA pipeline reported success while the artifact was missing.\n\n"
        "## Root Cause\n\nThe exit code was read after a pipe, so it was the pipe's.\n\n"
        "## Solution\n\nCapture the exit code before the pipe.\n\n"
        "## Verification\n\nRan it and the failure now surfaces.\n",
        encoding="utf-8",
    )
    record = parse_lesson(lesson)
    assert record is not None
    stored = _json.loads(record["frontmatter"])
    assert stored.get("evidence_level"), (
        "the synced frontmatter carries no evidence_level, so the API answers \"\" for a "
        "lesson whose level the corpus publishes")
    # …and the rest of the frontmatter is untouched: this adds the derived key, it does not rewrite.
    assert stored["title"] == "a lesson that never declared a level"
    assert stored["domain"] == "devops"


def test_a_declared_level_is_not_overwritten(tmp_path, monkeypatch):
    """A lesson that says E3 keeps E3 — the derivation never second-guesses an explicit value."""
    import json as _json

    monkeypatch.setattr(sync_lessons_to_d1, "REPO", tmp_path)
    lesson = tmp_path / "declared.md"
    lesson.write_text(
        "---\ntitle: explicit\ndomain: devops\nevidence_level: E3\ntags: [ci]\n---\n\n"
        "## Problem\n\nx is long enough to look like a section.\n\n"
        "## Root Cause\n\ny is also long enough.\n\n"
        "## Solution\n\nz is long enough too.\n\n"
        "## Verification\n\nw as well, and long enough.\n",
        encoding="utf-8",
    )
    record = parse_lesson(lesson)
    assert record is not None
    assert _json.loads(record["frontmatter"])["evidence_level"] == "E3"
