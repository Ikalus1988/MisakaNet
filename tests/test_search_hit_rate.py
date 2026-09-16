#!/usr/bin/env python3
"""命中率聚合的离线测试（issue #1779）。

`scripts/search_hit_rate.py` 的算术部分（`aggregate` / `solved_flag`）是纯函数，
所以这里用 fixture 行覆盖全命中、全未命中、混合、空、以及混入旧格式（没有
`solved`）的批次，并断言 CLI 的取数与输出契约。全程离线：网络调用在 CLI 测试里
被替换掉。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.search_hit_rate import (  # noqa: E402  (需要先插入仓库根目录)
    CAVEATS,
    DEFAULT_ENDPOINT,
    aggregate,
    main,
    solved_flag,
)

WORKER = REPO / "workers" / "register-proxy-sw.js"


def rows(*flags):
    """把一串 True/False/None 变成 worker 形状的行（None = 旧格式，没有 solved）。"""
    out = []
    for flag in flags:
        row = {"created_at": "2026-09-16 10:00:00"}
        if flag is not None:
            row["solved"] = flag
        out.append(row)
    return out


# ── 算术 ─────────────────────────────────────────────────────────────────────

def test_all_hits():
    stats = aggregate(rows(*[True] * 4))
    assert stats == {"total": 4, "hit": 4, "miss": 0, "hit_rate": 1.0, "legacy_rows": 0}


def test_all_misses():
    stats = aggregate(rows(*[False] * 5))
    assert stats == {"total": 5, "hit": 0, "miss": 5, "hit_rate": 0.0, "legacy_rows": 0}


def test_mixed_batch():
    stats = aggregate(rows(True, False, True, False, False))
    assert stats["total"] == 5
    assert stats["hit"] == 2
    assert stats["miss"] == 3
    assert stats["hit_rate"] == 0.4
    assert stats["legacy_rows"] == 0


def test_empty_window_has_no_hit_rate():
    """没有样本 ≠ 0%：算不出来就必须是 None，不能印成 0。"""
    stats = aggregate([])
    assert stats == {"total": 0, "hit": 0, "miss": 0, "hit_rate": None, "legacy_rows": 0}


def test_mixed_batch_with_legacy_rows():
    """旧格式行（没有 solved）算未命中，并单独计数。"""
    stats = aggregate(rows(True, None, False, None))
    assert stats["total"] == 4
    assert stats["hit"] == 1
    assert stats["miss"] == 3, "两条旧格式行必须落进 miss"
    assert stats["legacy_rows"] == 2
    assert stats["hit_rate"] == 0.25


def test_legacy_treatment_never_inflates_the_rate():
    """同样的 1 命中，混入旧格式行只能让命中率下降。"""
    clean = aggregate(rows(True, False))
    polluted = aggregate(rows(True, False, None, None))
    assert clean["hit_rate"] == 0.5
    assert polluted["hit_rate"] == 0.25
    assert polluted["hit"] == clean["hit"]


def test_d1_integers_and_booleans_are_both_understood():
    """D1 返回 0/1，JSON 里也可能是 true/false —— 两种都认。"""
    stats = aggregate([{"solved": 1}, {"solved": 0}, {"solved": True}, {"solved": False}])
    assert stats == {"total": 4, "hit": 2, "miss": 2, "hit_rate": 0.5, "legacy_rows": 0}


def test_null_solved_is_legacy_not_a_hit():
    stats = aggregate([{"solved": None}, {"solved": True}])
    assert stats["legacy_rows"] == 1
    assert stats["hit"] == 1
    assert stats["hit_rate"] == 0.5


def test_unknown_values_are_treated_as_misses_not_hits():
    """值不认识时方向必须保守：宁可算未命中，也不能凭空抬高命中率。"""
    stats = aggregate([{"solved": "yes"}, {"solved": 7}, {"solved": []}])
    assert stats["hit"] == 0
    assert stats["legacy_rows"] == 3


def test_non_object_rows_are_counted_not_dropped():
    """端点坏了/返回了乱七八糟的东西时，不能静默丢行。"""
    stats = aggregate([{"solved": True}, "garbage", None])
    assert stats["total"] == 3
    assert stats["legacy_rows"] == 2
    assert stats["hit"] == 1


def test_solved_flag_helper():
    assert solved_flag(True) is True
    assert solved_flag(False) is False
    assert solved_flag(1) is True
    assert solved_flag(0) is False
    assert solved_flag(None) is None
    assert solved_flag("true") is None
    assert solved_flag(2) is None


# ── CLI 契约（离线：网络被替换） ──────────────────────────────────────────────

def payload(solved_values, truncated=False, source="d1:search_signals"):
    return {"rows": rows(*solved_values), "truncated": truncated, "source": source, "days": 7}


def test_json_output_carries_the_five_numbers(capsys):
    with patch("scripts.search_hit_rate.fetch_payload", return_value=payload([True, False, None])) as fetch:
        code = main(["--json", "--since", "30"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    for key in ("total", "hit", "miss", "hit_rate", "legacy_rows"):
        assert key in out, f"{key} 必须在输出里"
    assert (out["total"], out["hit"], out["miss"], out["legacy_rows"]) == (3, 1, 2, 1)
    assert out["hit_rate"] == pytest.approx(1 / 3, abs=5e-5)
    assert out["days"] == 30
    assert out["source"] == "d1:search_signals"
    # 窗口由服务端过滤，脚本把它原样传下去
    assert fetch.call_args.args[1] == 30


def test_text_output_names_the_five_numbers_and_the_caveats(capsys):
    with patch("scripts.search_hit_rate.fetch_payload", return_value=payload([True, False])):
        code = main([])
    assert code == 0
    text = capsys.readouterr().out
    for key in ("total", "hit", "miss", "hit_rate", "legacy_rows"):
        assert key in text
    assert "50.0%" in text
    # “测不到的部分”必须跟着数字一起出现
    assert all(caveat[:12] in text for caveat in CAVEATS)


def test_empty_window_says_sample_too_small(capsys):
    with patch("scripts.search_hit_rate.fetch_payload", return_value=payload([])):
        code = main([])
    assert code == 0
    text = capsys.readouterr().out
    assert "n/a" in text
    assert "样本不足" in text


def test_truncated_window_is_flagged(capsys):
    with patch("scripts.search_hit_rate.fetch_payload", return_value=payload([True], truncated=True)):
        main([])
    assert "截断" in capsys.readouterr().out


def test_fetch_failure_exits_nonzero_and_says_what_it_could_not_measure(capsys):
    with patch("scripts.search_hit_rate.fetch_payload", side_effect=OSError("connection refused")):
        code = main([])
    assert code == 2, "取数失败不能退出 0（否则 CI 里会当成“命中率 0”）"
    captured = capsys.readouterr()
    assert "测不出" in captured.err
    assert captured.out == "", "没有数据时不要打印任何数字"


def test_default_window_and_endpoint():
    """默认 7 天，默认打线上端点 —— 与 worker 的路由保持一致。"""
    assert DEFAULT_ENDPOINT.endswith("/api/search-signals/stats")
    with patch("scripts.search_hit_rate.fetch_payload", return_value=payload([True])) as fetch:
        main([])
    assert fetch.call_args.args[1] == 7
    assert fetch.call_args.args[0] == DEFAULT_ENDPOINT


def test_default_endpoint_matches_the_worker_route():
    """脚本与 worker 的路由字符串漂移时必须在这里失败。"""
    worker = WORKER.read_text(encoding="utf-8")
    assert 'url.pathname === "/api/search-signals/stats"' in worker
    assert 'INSERT INTO search_signals' in worker
