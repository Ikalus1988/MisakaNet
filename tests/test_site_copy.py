from pathlib import Path


SITE = Path(__file__).parents[1] / "docs" / "index.html"
HTML = SITE.read_text(encoding="utf-8")


def test_registration_copy_describes_read_access_and_write_unlocks():
    assert "Read without registration" in HTML
    assert "Registration only unlocks writing tools" in HTML
    assert "🌐 没有 GitHub？直接注册" not in HTML


def test_recent_node_count_has_honest_annotation():
    assert "Recently created nodes" in HTML
    assert "self-declared, not identity, reading needs no registration" in HTML
    assert "最近创建的 node" in HTML
    assert "自声明、非身份信息；阅读无需注册" in HTML


def test_agent_type_is_optional_statistics_only_in_both_languages():
    assert "Agent type (optional · statistics only)" in HTML
    assert "Agent 类型（可选·仅统计）" in HTML
    assert "Why ask?" in HTML
    assert "为什么询问？" in HTML


def test_protocol_marker_is_unchanged_and_occurs_twice():
    # One occurrence is the issue-body builder and one is the parser regex.
    assert HTML.count("Agent 类型: **") == 2
    assert "return `Agent 类型: **${agentType}**`;" in HTML
    assert r"body.match(/^Agent 类型: \*\*(.+)\*\*$/m)" in HTML


def test_i18n_dictionary_contains_distinct_english_and_chinese_values():
    assert 'registrationTitle: "Read without registration"' in HTML
    assert 'registrationTitle: "无需注册即可读取"' in HTML
    assert 'recentNodesNote: "self-declared, not identity, reading needs no registration"' in HTML
    assert 'recentNodesNote: "自声明、非身份信息；阅读无需注册"' in HTML
