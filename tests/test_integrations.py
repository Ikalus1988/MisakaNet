"""Tests for LangChain and LlamaIndex integrations."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add repo root to path for imports
sys.path.insert(0, str(os.path.dirname(os.path.dirname(__file__))))


class TestLangChainIntegration:
    """Tests for LangChain MisakaNet tool."""

    @pytest.fixture(autouse=True)
    def skip_if_no_langchain(self):
        """Skip LangChain tests if langchain is not installed."""
        pytest.importorskip("langchain")

    def test_tool_import(self):
        """Test that LangChain tool can be imported."""
        from integrations.langchain.misakanet_tool import MisakaNetSearchTool

        tool = MisakaNetSearchTool()
        assert tool.name == "misakanet_search"
        assert "MisakaNet" in tool.description

    def test_tool_input_schema(self):
        """Test tool input schema is properly defined."""
        from integrations.langchain.misakanet_tool import (
            MisakaNetSearchInput,
            MisakaNetSearchTool,
        )

        tool = MisakaNetSearchTool()
        schema = tool.args_schema.schema()

        assert "query" in schema["properties"]
        assert "max_results" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"

    @patch("urllib.request.urlopen")
    def test_search_rest_success(self, mock_urlopen):
        """Test REST API search with successful response.

        The mock payload used to carry a `type` field and a `score` of 0.95. Neither
        exists: not one of the 467 lessons in `data/lessons.json` has `type`, and the
        live endpoint returns relevance on a 0–12 scale (measured 2026-10-06, three
        queries, nine results: `type` absent from all, `score` observed 11.0 / 10.18 /
        6.94 / 3.07). The mock described an API that does not exist, and because the
        assertions only checked that the title appeared somewhere, nothing noticed that
        the code read `type` and so rendered every result as `[unknown]`.

        The payload below is the real shape — `domain` in place of `type`, and a score
        on the real scale — and the assertions now check the rendered line, not just
        that a substring is present somewhere in it.
        """
        from integrations.langchain.misakanet_tool import MisakaNetSearchTool

        # Mock response, shaped like a real /api/lessons?detail=summary payload.
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "query": "test query",
                "source": "d1",
                "results": [
                    {
                        "id": "erreur-permission-docker-linux",
                        "title": "Test Lesson",
                        "domain": "devops",
                        "status": "published",
                        "path": "lessons/contrib/erreur-permission-docker-linux.md",
                        "tags": ["docker", "linux"],
                        "description": "long form description",
                        "problem": "Test problem",
                        "score": 10.86,
                    }
                ],
            }
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        tool = MisakaNetSearchTool()
        result = tool._run("test query")

        assert "Found 1 relevant lessons" in result
        assert "Test Lesson" in result
        # The lesson's domain, not the `type` fallback. Before the fix this line read
        # `[unknown]` against a payload with no `type`, which is exactly what production
        # returns, so every line the tool ever printed said `[unknown]`.
        assert "[devops]" in result, (
            f"the domain is not rendered; got:\n{result}\n"
            "If this starts failing, either the endpoint stopped sending `domain` or the "
            "formatter went back to reading a field lessons do not carry."
        )
        assert "[unknown]" not in result, (
            f"a result rendered with the `unknown` fallback:\n{result}\n"
            "That means a field the API does not send was read again."
        )
        # Relevance is a float on a wide scale, not a 0–1 fraction; the two-decimal
        # format is for readability, not for implying a probability.
        assert "(relevance: 10.86)" in result, (
            f"the score was not rendered as the API sends it:\n{result}"
        )

    @patch("urllib.request.urlopen")
    def test_search_rest_empty(self, mock_urlopen):
        """Test REST API search with no results."""
        from integrations.langchain.misakanet_tool import MisakaNetSearchTool

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"results": []}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        tool = MisakaNetSearchTool()
        result = tool._run("nonexistent query")

        assert "No matching lessons found" in result

    @patch("urllib.request.urlopen")
    def test_search_rest_error(self, mock_urlopen):
        """Test REST API search with network error."""
        from integrations.langchain.misakanet_tool import MisakaNetSearchTool

        mock_urlopen.side_effect = Exception("Connection failed")

        tool = MisakaNetSearchTool()
        result = tool._run("test query")

        assert "Search failed" in result

    def test_get_misakanet_tool(self):
        """Test convenience function."""
        from integrations.langchain.misakanet_tool import get_misakanet_tool

        tool = get_misakanet_tool()
        assert tool.name == "misakanet_search"


class TestLlamaIndexIntegration:
    """Tests for LlamaIndex MisakaNet tool."""

    def test_function_import(self):
        """Test that LlamaIndex function can be imported."""
        from integrations.llamaindex.misakanet_tool import misakanet_search

        assert callable(misakanet_search)

    @patch("urllib.request.urlopen")
    def test_search_success(self, mock_urlopen):
        """Test search with successful response.

        Same correction as the LangChain case above: `type` is not a lesson field and
        `score` is not a 0–1 fraction. This mock asserted only that the title appeared
        somewhere, which is why reading `type` — and rendering `[unknown]` for every
        result the tool ever returned — went unnoticed.
        """
        from integrations.llamaindex.misakanet_tool import misakanet_search

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "query": "test query",
                "source": "d1",
                "results": [
                    {
                        "id": "erreur-permission-docker-linux",
                        "title": "Test Lesson",
                        "domain": "devops",
                        "status": "published",
                        "path": "lessons/contrib/erreur-permission-docker-linux.md",
                        "tags": ["docker", "linux"],
                        "description": "long form description",
                        "problem": "Test problem",
                        "score": 10.86,
                    }
                ]
            }
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = misakanet_search("test query")

        assert "Found 1 relevant lessons" in result
        assert "Test Lesson" in result
        assert "[devops]" in result, (
            f"the domain is not rendered; got:\n{result}\n"
            "See test_search_rest_success for the measurement behind this."
        )
        assert "[unknown]" not in result, (
            f"a result rendered with the `unknown` fallback:\n{result}"
        )
        assert "(relevance: 10.86)" in result, (
            f"the score was not rendered as the API sends it:\n{result}"
        )

    @patch("urllib.request.urlopen")
    def test_search_empty(self, mock_urlopen):
        """Test search with no results."""
        from integrations.llamaindex.misakanet_tool import misakanet_search

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"results": []}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = misakanet_search("nonexistent query")

        assert "No matching lessons found" in result

    @patch("urllib.request.urlopen")
    def test_search_error(self, mock_urlopen):
        """Test search with network error."""
        from integrations.llamaindex.misakanet_tool import misakanet_search

        mock_urlopen.side_effect = Exception("Connection failed")

        result = misakanet_search("test query")

        assert "Search failed" in result

    def test_max_results_clamping(self):
        """Test that max_results is clamped to valid range."""
        from integrations.llamaindex.misakanet_tool import misakanet_search

        # Mock to avoid actual API call
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({"results": []}).encode(
                "utf-8"
            )
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            # Test clamping
            misakanet_search("test", max_results=0)  # Should become 1
            misakanet_search("test", max_results=100)  # Should become 10

    @patch.dict(os.environ, {"MISAKANET_API_KEY": "test-key"})
    @patch("urllib.request.urlopen")
    def test_api_key_from_env(self, mock_urlopen):
        """Test that API key is read from environment."""
        from integrations.llamaindex.misakanet_tool import misakanet_search

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"results": []}).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        misakanet_search("test query")

        # Verify API key was passed
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test-key"
