"""Tests for the federation module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from hub.federation.registry import FederationRegistry, PeerNode
from hub.federation.sync_protocol import (
    FederationSync,
    LessonManifest,
    SyncResult,
    compute_sha256,
    generate_manifest,
    parse_lesson_frontmatter,
    save_manifest,
    load_manifest,
)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_lesson():
    return """---
id: test-lesson
title: Test Lesson
tags: [python, test]
last_updated: 2026-06-04
---

# Test Lesson

This is a test lesson content.
"""


class TestManifestGeneration:
    def test_generate_manifest(self, tmp_dir, sample_lesson):
        """Test manifest generation from lessons directory."""
        lessons_dir = tmp_dir / "lessons"
        lessons_dir.mkdir()
        (lessons_dir / "test.md").write_text(sample_lesson)

        manifest = generate_manifest(lessons_dir, "node1", "https://github.com/test/repo")

        assert manifest.node_id == "node1"
        assert manifest.repo_url == "https://github.com/test/repo"
        assert "test-lesson" in manifest.lessons
        assert len(manifest.lessons) == 1

    def test_save_and_load_manifest(self, tmp_dir):
        """Test manifest serialization round-trip."""
        manifest = LessonManifest(
            node_id="node1",
            repo_url="https://github.com/test/repo",
            timestamp="2026-06-04T00:00:00Z",
            lessons={"lesson1": "abc123"},
        )

        manifest_path = tmp_dir / "manifest.json"
        save_manifest(manifest, manifest_path)

        loaded = load_manifest(manifest_path)
        assert loaded is not None
        assert loaded.node_id == "node1"
        assert loaded.lessons == {"lesson1": "abc123"}


class TestIncrementalSync:
    def test_incremental_sync_detects_changes(self, tmp_dir, sample_lesson):
        """Test that incremental sync only syncs changed lessons."""
        # Setup peer directory
        peer_dir = tmp_dir / "peer_lessons"
        peer_dir.mkdir()
        (peer_dir / "lesson1.md").write_text(sample_lesson)

        # Setup local directory with same lesson
        local_dir = tmp_dir / "local_lessons"
        local_dir.mkdir()
        (local_dir / "lesson1.md").write_text(sample_lesson)

        # Create sync instance
        sync = FederationSync(
            lessons_dir=local_dir,
            staging_dir=tmp_dir / "staging",
            manifest_path=tmp_dir / "manifest.json",
            node_id="local",
            repo_url="https://github.com/local/repo",
        )

        # Generate peer manifest
        peer_manifest = generate_manifest(peer_dir, "peer", "https://github.com/peer/repo")

        # Sync should skip unchanged lesson
        result = sync.sync_from_peer(peer_manifest, peer_dir)
        assert result.lessons_skipped == 1
        assert result.lessons_added == 0

        # Now modify peer lesson
        modified_lesson = sample_lesson.replace("test lesson content", "modified content")
        (peer_dir / "lesson1.md").write_text(modified_lesson)
        peer_manifest = generate_manifest(peer_dir, "peer", "https://github.com/peer/repo")

        # Sync should update changed lesson
        result = sync.sync_from_peer(peer_manifest, peer_dir)
        assert result.lessons_updated == 1
        assert result.lessons_skipped == 0


class TestConflictResolution:
    def test_last_writer_wins(self, tmp_dir):
        """Test conflict resolution with last_writer_wins strategy."""
        # Create local lesson
        local_dir = tmp_dir / "local_lessons"
        local_dir.mkdir()
        local_lesson = """---
id: conflict-lesson
title: Local Version
last_updated: 2026-06-03
---
Local content
"""
        (local_dir / "conflict-lesson.md").write_text(local_lesson)

        # Create peer lesson with newer timestamp
        peer_dir = tmp_dir / "peer_lessons"
        peer_dir.mkdir()
        peer_lesson = """---
id: conflict-lesson
title: Peer Version
last_updated: 2026-06-04
---
Peer content
"""
        (peer_dir / "conflict-lesson.md").write_text(peer_lesson)

        # Sync
        sync = FederationSync(
            lessons_dir=local_dir,
            staging_dir=tmp_dir / "staging",
            manifest_path=tmp_dir / "manifest.json",
            node_id="local",
            repo_url="https://github.com/local/repo",
        )

        peer_manifest = generate_manifest(peer_dir, "peer", "https://github.com/peer/repo")
        result = sync.sync_from_peer(peer_manifest, peer_dir, conflict_strategy="last_writer_wins")

        # Peer should win (newer timestamp)
        assert result.lessons_updated == 1
        content = (local_dir / "conflict-lesson.md").read_text()
        assert "Peer Version" in content


class TestPeerUnreachable:
    def test_peer_unreachable_graceful_skip(self, tmp_dir):
        """Test that unreachable peer is handled gracefully."""
        # Create sync with empty peer directory
        sync = FederationSync(
            lessons_dir=tmp_dir / "lessons",
            staging_dir=tmp_dir / "staging",
            manifest_path=tmp_dir / "manifest.json",
            node_id="local",
            repo_url="https://github.com/local/repo",
        )

        # Create manifest with non-existent lessons
        peer_manifest = LessonManifest(
            node_id="unreachable",
            repo_url="https://github.com/unreachable/repo",
            timestamp="2026-06-04T00:00:00Z",
            lessons={"missing-lesson": "abc123"},
        )

        # Sync should handle gracefully
        result = sync.sync_from_peer(peer_manifest, tmp_dir / "empty_peer")
        assert result.lessons_added == 0
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()


class TestRegistry:
    def test_add_and_get_peer(self, tmp_dir):
        """Test adding and retrieving peers."""
        config_path = tmp_dir / "config.yaml"
        registry = FederationRegistry.from_config(config_path)

        peer = registry.add_peer("node1", "https://github.com/test/repo")
        assert peer.node_id == "node1"
        assert registry.get_peer("node1") is not None

    def test_remove_peer(self, tmp_dir):
        """Test removing peers."""
        config_path = tmp_dir / "config.yaml"
        registry = FederationRegistry.from_config(config_path)

        registry.add_peer("node1", "https://github.com/test/repo")
        assert registry.remove_peer("node1") is True
        assert registry.get_peer("node1") is None

    def test_get_active_peers(self, tmp_dir):
        """Test filtering active peers."""
        config_path = tmp_dir / "config.yaml"
        registry = FederationRegistry.from_config(config_path)

        registry.add_peer("node1", "https://github.com/test/repo1")
        registry.add_peer("node2", "https://github.com/test/repo2")
        registry.update_peer_status("node2", "disabled")

        active = registry.get_active_peers()
        assert len(active) == 1
        assert active[0].node_id == "node1"
