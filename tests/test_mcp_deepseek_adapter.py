from scripts.mcp_deepseek_adapter import handle_deepseek_smoke


def test_deepseek_recovery_smoke_passes():
    result = handle_deepseek_smoke({})

    assert result["overall"] == "pass"
    assert result["tests"]["search"]["status"] == "ok"
    assert result["tests"]["search"]["result_count"] > 0
    assert result["tests"]["get_lesson"]["status"] == "ok"
    assert result["tests"]["get_lesson"]["content_length"] > 0
