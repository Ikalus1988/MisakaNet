"""Unit tests for multi-language section alias extraction in scripts/sync_lessons_to_d1.py (#1738).

Ensures localized lessons (pt-br, es, ru, hi, id, tr, vi) parse
problem, root_cause, solution, and verification sections accurately.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from scripts.sync_lessons_to_d1 import split_sections, parse_lesson, REPO


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
