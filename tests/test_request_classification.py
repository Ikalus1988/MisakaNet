"""Tests for request classification logic (Issue #1347).

Mirrors the classifyRequest function in register-proxy-sw.js:
- MCP endpoints → "mcp"
- /llms*, /robots.txt → "agent"
- Crawler UA patterns → "crawler"
- Agent UA patterns → "agent"
- Everything else → "pageview"
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKER = REPO_ROOT / "workers" / "register-proxy-sw.js"

# JS regex patterns translated to Python (same logic)
CRAWLER_UA = re.compile(
    r"bot|crawl|spider|slurp|mediapartners|adsbot|googlebot|bingbot|baiduspider|"
    r"yandexbot|duckduckbot|facebookexternalhit|twitterbot|linkedinbot|pinterestbot|"
    r"discordbot|telegrambot|whatsapp|applebot|semrushbot|ahrefsbot|mj12bot|dotbot|"
    r"petalbot|bytespider|gptbot|chatgpt-user|ccbot|anthropic|claudebot|cohere-ai|"
    r"perplexitybot|deepseek|meta-externalagent|meta-externalfetcher",
    re.IGNORECASE,
)
AGENT_UA = re.compile(
    r"claude|cursor|copilot|openai|anthropic|misakanet|postman|insomnia|httpie|"
    r"curl|wget|python-requests|python-httpx|node-fetch|undici|deno|bun",
    re.IGNORECASE,
)


def classify(ua: str, pathname: str) -> str:
    """Mirror of classifyRequest from register-proxy-sw.js."""
    if pathname in ("/mcp", "/mcp/connect", "/mcp/pair"):
        return "mcp"
    if pathname.startswith("/llms") or pathname == "/robots.txt":
        return "agent"
    if CRAWLER_UA.search(ua):
        return "crawler"
    if AGENT_UA.search(ua):
        return "agent"
    return "pageview"


class TestClassifyRequest:

    # MCP endpoints
    @pytest.mark.parametrize("path", ["/mcp", "/mcp/connect", "/mcp/pair"])
    def test_mcp_endpoints(self, path):
        assert classify("Mozilla/5.0", path) == "mcp"

    # Agent paths
    @pytest.mark.parametrize("path", ["/llms.txt", "/llms-full.txt", "/llms-small.txt", "/robots.txt"])
    def test_agent_paths(self, path):
        assert classify("Mozilla/5.0", path) == "agent"

    # Crawlers
    @pytest.mark.parametrize("ua", [
        "Googlebot/2.1 (+http://www.google.com/bot.html)",
        "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
        "CCBot/2.0 (https://commoncrawl.org/faq/)",
        "GPTBot/1.0 (+https://openai.com/gptbot)",
        "ChatGPT-User/1.0 (+https://openai.com/chatgpt-user)",
        "ClaudeBot/1.0",
        "cohere-ai",
        "PerplexityBot/1.0",
        "DeepSeekBot/1.0",
        "facebookexternalhit/1.1",
        "Twitterbot/1.0",
        "Applebot/0.1",
        "Bytespider",
    ])
    def test_crawlers(self, ua):
        assert classify(ua, "/") == "crawler"

    # Agents
    @pytest.mark.parametrize("ua", [
        "curl/8.0",
        "python-requests/2.31.0",
        "python-httpx/0.27.0",
        "node-fetch/3.0",
        "Claude-Code/1.0",
        "Cursor/0.42.0",
        "PostmanRuntime/7.32.0",
        "MisakaNet-Worker",
        "Wget/1.21",
        "HTTPie/3.2",
    ])
    def test_agents(self, ua):
        assert classify(ua, "/") == "agent"

    # Page views
    @pytest.mark.parametrize("ua", [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ])
    def test_pageviews(self, ua):
        assert classify(ua, "/") == "pageview"
        assert classify(ua, "/start") == "pageview"
        assert classify(ua, "/connect") == "pageview"

    def test_agent_overrides_pageview_for_api(self):
        """Agent UA + API path = agent (not api)."""
        assert classify("curl/8.0", "/api/lessons") == "agent"

    def test_crawler_overrides_agent(self):
        """Crawler UA is checked before agent UA."""
        assert classify("ClaudeBot/1.0 (crawler)", "/") == "crawler"


class TestWorkerExportsClassification:

    def test_classify_request_exported(self):
        """classifyRequest must be in the export list."""
        src = WORKER.read_text(encoding="utf-8")
        assert "classifyRequest" in src.split("export {")[1]

    def test_classification_function_exists(self):
        """The classifyRequest function must be defined."""
        src = WORKER.read_text(encoding="utf-8")
        assert "function classifyRequest" in src

    def test_traffic_endpoint_exists(self):
        """/api/analytics/traffic endpoint must be registered."""
        src = WORKER.read_text(encoding="utf-8")
        assert '/api/analytics/traffic"' in src

    def test_console_log_classification(self):
        """Requests should be logged with classification."""
        src = WORKER.read_text(encoding="utf-8")
        assert "console.log" in src
        assert "cls:" in src
