"""Tests for the demand board insights module."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from misakanet.insights import DemandBoard, classify_task_family, TASK_FAMILIES


class TestClassifyTaskFamily:
    def test_github_auth(self):
        assert classify_task_family("github token expired", "") == "github-auth"
        assert classify_task_family("OAuth flow broken", "lesson-5") == "github-auth"

    def test_npm_publish(self):
        assert classify_task_family("npm publish failed", "") == "npm-publish"
        assert classify_task_family("package.json error", "") == "npm-publish"

    def test_cloudflare_worker(self):
        assert classify_task_family("cloudflare worker deploy error", "") == "cloudflare-worker"
        assert classify_task_family("wrangler build failed", "") == "cloudflare-worker"

    def test_python_env(self):
        assert classify_task_family("pip install error", "") == "python-env"
        assert classify_task_family("virtualenv activation bug", "") == "python-env"

    def test_database_lock(self):
        assert classify_task_family("mysql transaction deadlock", "") == "database-lock"

    def test_crawler_block(self):
        assert classify_task_family("scraper got 403", "") == "crawler-block"
        assert classify_task_family("crawl problem bot detect", "") == "crawler-block"

    def test_agent_tooling(self):
        assert classify_task_family("langchain not found", "") == "agent-tooling"
        assert classify_task_family("skill plugin error", "") == "agent-tooling"

    def test_unclassified(self):
        assert classify_task_family("something completely random", "") == "unclassified"
        assert classify_task_family("", "") == "unclassified"

    def test_lesson_id_used(self):
        assert classify_task_family("error", "github-oauth-lesson") == "github-auth"


class TestDemandBoard:
    @pytest.fixture
    def board(self, tmp_path):
        return DemandBoard(data_dir=str(tmp_path))

    def test_empty_board(self, board):
        result = board.get_demand_board()
        assert result["success"] is True
        assert result["available"] is False
        assert result["summary"] == []
        assert result["meta"]["r_level"] == "R1_descriptive"
        assert result["meta"]["privacy"] == "aggregate-only"
        assert result["meta"]["pii"] is False

    def test_record_and_retrieve_feedback(self, board):
        board.record_feedback("github auth error", "lesson-1", "irrelevant")
        board.record_feedback("npm publish crash", "lesson-2", "too_basic")
        board.record_feedback("github token 401", "lesson-3", "irrelevant")

        result = board.get_demand_board()

        assert result["available"] is True
        families = {s["taskFamily"]: s for s in result["summary"]}

        assert "github-auth" in families
        assert families["github-auth"]["unsolved30d"] == 2

        assert "npm-publish" in families
        assert families["npm-publish"]["unsolved30d"] == 1

    def test_helpful_feedback_excluded(self, board):
        board.record_feedback("github help", "lesson-1", "helpful")
        board.record_feedback("bad result", "lesson-2", "irrelevant")

        result = board.get_demand_board()
        assert result["available"] is True
        # Only the "irrelevant" one should count
        total = sum(s["unsolved30d"] for s in result["summary"])
        assert total == 1

    def test_intake_records(self, board):
        board.record_intake("search", "cloudflare worker deploy timeout")
        board.record_intake("mcp", "mcp registry connection refused")

        result = board.get_demand_board()

        assert result["available"] is True
        families = {s["taskFamily"]: s for s in result["summary"]}
        assert "cloudflare-worker" in families
        assert "mcp-registry" in families

    def test_demand_map_requires_key(self, board):
        # No key set in env
        result = board.get_demand_map("wrong-key")
        assert "error" in result

    def test_demand_map_with_valid_key(self, board, monkeypatch):
        monkeypatch.setenv("MAINTAINER_KEY", "secret123")
        board.record_feedback("github auth broke", "lesson-1", "irrelevant")

        result = board.get_demand_map("secret123")
        assert "buckets" in result
        assert len(result["buckets"]) >= 1

    def test_demand_map_wrong_key(self, board, monkeypatch):
        monkeypatch.setenv("MAINTAINER_KEY", "secret123")
        result = board.get_demand_map("wrong")
        assert "error" in result

    def test_no_raw_queries_in_output(self, board):
        board.record_feedback("secret password 12345", "lesson-1", "irrelevant")
        result = board.get_demand_board()
        output = json.dumps(result)
        # No raw query text should appear
        assert "secret password 12345" not in output
        # No PII markers
        assert result["meta"]["pii"] is False
        assert result["meta"]["raw_query"] is False

    def test_window_days_parameter(self, board):
        board.record_feedback("test query", "lesson-1", "irrelevant")
        result = board.get_demand_board(window_days=7)
        assert result["windowDays"] == 7

    def test_task_family_whitelist(self):
        # All task families should be in the whitelist
        assert "github-auth" in TASK_FAMILIES
        assert "unclassified" in TASK_FAMILIES
        assert len(TASK_FAMILIES) == 10
