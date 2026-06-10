"""Federation Sync Protocol — atomic & crash-safe cross-repo lesson sync.

Pure Python stdlib + PyYAML only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class LessonManifest:
    """Manifest of lessons published by a peer."""
    node_id: str
    repo_url: str
    timestamp: str
    lessons: dict[str, str] = field(default_factory=dict)  # lesson_id -> sha256
    signature: str | None = None  # Ed25519 signature (optional)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    peer_id: str
    lessons_added: int = 0
    lessons_updated: int = 0
    lessons_skipped: int = 0
    lessons_conflicted: int = 0
    errors: list[str] = field(default_factory=list)


def compute_sha256(content: str) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parse_lesson_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a lesson markdown file."""
    if not content.startswith("---"):
        return {}

    try:
        end = content.index("---", 3)
        frontmatter = content[3:end].strip()
        return yaml.safe_load(frontmatter) or {}
    except (ValueError, yaml.YAMLError):
        return {}


def generate_manifest(lessons_dir: Path, node_id: str, repo_url: str) -> LessonManifest:
    """Generate a manifest of all lessons in a directory."""
    manifest = LessonManifest(
        node_id=node_id,
        repo_url=repo_url,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    if not lessons_dir.exists():
        return manifest

    for lesson_file in lessons_dir.glob("*.md"):
        content = lesson_file.read_text(encoding="utf-8")
        frontmatter = parse_lesson_frontmatter(content)
        lesson_id = frontmatter.get("id", lesson_file.stem)

        manifest.lessons[lesson_id] = compute_sha256(content)

    logger.info("Generated manifest with %d lessons", len(manifest.lessons))
    return manifest


def save_manifest(manifest: LessonManifest, output_path: Path) -> None:
    """Save manifest to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(asdict(manifest), f, indent=2)


def load_manifest(manifest_path: Path) -> LessonManifest | None:
    """Load manifest from JSON file."""
    if not manifest_path.exists():
        return None

    with manifest_path.open() as f:
        data = json.load(f)

    return LessonManifest(**data)


class FederationSync:
    """Atomic & crash-safe cross-repo lesson sync."""

    def __init__(
        self,
        lessons_dir: Path,
        staging_dir: Path,
        manifest_path: Path,
        node_id: str,
        repo_url: str,
    ):
        self.lessons_dir = lessons_dir
        self.staging_dir = staging_dir
        self.manifest_path = manifest_path
        self.node_id = node_id
        self.repo_url = repo_url

    def publish_manifest(self) -> LessonManifest:
        """Publish manifest of local lessons."""
        manifest = generate_manifest(self.lessons_dir, self.node_id, self.repo_url)
        save_manifest(manifest, self.manifest_path)
        return manifest

    def sync_from_peer(
        self,
        peer_manifest: LessonManifest,
        peer_lessons_dir: Path,
        conflict_strategy: str = "last_writer_wins",
    ) -> SyncResult:
        """Sync lessons from a peer using atomic staging."""
        result = SyncResult(peer_id=peer_manifest.node_id)

        # Clean staging directory
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # Get local manifest for comparison
        local_manifest = load_manifest(self.manifest_path)

        for lesson_id, peer_hash in peer_manifest.lessons.items():
            # Check if lesson needs sync — check both manifest AND local file
            local_lesson_path = self.lessons_dir / f"{lesson_id}.md"
            
            # First check manifest (if available)
            if local_manifest and lesson_id in local_manifest.lessons:
                if local_manifest.lessons[lesson_id] == peer_hash:
                    result.lessons_skipped += 1
                    continue
            
            # Also check if local file exists and has same hash
            if local_lesson_path.exists():
                local_content = local_lesson_path.read_text(encoding="utf-8")
                local_hash = compute_sha256(local_content)
                if local_hash == peer_hash:
                    result.lessons_skipped += 1
                    continue

            # Find the lesson file in peer directory
            peer_lesson_path = self._find_lesson_file(peer_lessons_dir, lesson_id)
            if not peer_lesson_path:
                result.errors.append(f"Lesson {lesson_id} not found in peer directory")
                continue

            # Read and verify hash
            content = peer_lesson_path.read_text(encoding="utf-8")
            actual_hash = compute_sha256(content)
            if actual_hash != peer_hash:
                result.errors.append(f"Hash mismatch for {lesson_id}: expected {peer_hash}, got {actual_hash}")
                continue

            # Stage the lesson
            stage_path = self.staging_dir / f"{lesson_id}.md"
            stage_path.write_text(content, encoding="utf-8")

            # Check for conflicts
            if local_lesson_path.exists():
                local_content = local_lesson_path.read_text(encoding="utf-8")
                local_hash = compute_sha256(local_content)

                if local_hash != actual_hash:
                    # Conflict detected
                    if conflict_strategy == "last_writer_wins":
                        local_frontmatter = parse_lesson_frontmatter(local_content)
                        peer_frontmatter = parse_lesson_frontmatter(content)

                        local_updated = local_frontmatter.get("last_updated", "")
                        peer_updated = peer_frontmatter.get("last_updated", "")

                        if peer_updated > local_updated:
                            # Peer wins
                            self._atomic_move(stage_path, local_lesson_path)
                            result.lessons_updated += 1
                        elif peer_updated < local_updated:
                            # Local wins
                            result.lessons_skipped += 1
                        else:
                            # Same timestamp, higher node_id wins
                            if peer_manifest.node_id > self.node_id:
                                self._atomic_move(stage_path, local_lesson_path)
                                result.lessons_updated += 1
                            else:
                                # Keep both with conflict suffix
                                conflict_path = self.lessons_dir / f"{lesson_id}_conflict_{peer_manifest.node_id}.md"
                                self._atomic_move(stage_path, conflict_path)
                                result.lessons_conflicted += 1
                    else:
                        # Keep both
                        conflict_path = self.lessons_dir / f"{lesson_id}_conflict_{peer_manifest.node_id}.md"
                        self._atomic_move(stage_path, conflict_path)
                        result.lessons_conflicted += 1
            else:
                # New lesson
                self._atomic_move(stage_path, local_lesson_path)
                result.lessons_added += 1

        # Clean up staging
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir)

        logger.info(
            "Sync from %s: added=%d, updated=%d, skipped=%d, conflicted=%d, errors=%d",
            peer_manifest.node_id,
            result.lessons_added,
            result.lessons_updated,
            result.lessons_skipped,
            result.lessons_conflicted,
            len(result.errors),
        )

        return result

    def _find_lesson_file(self, directory: Path, lesson_id: str) -> Path | None:
        """Find a lesson file by ID."""
        # Try direct filename
        direct = directory / f"{lesson_id}.md"
        if direct.exists():
            return direct

        # Search by frontmatter ID
        for md_file in directory.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            frontmatter = parse_lesson_frontmatter(content)
            if frontmatter.get("id") == lesson_id:
                return md_file

        return None

    def _atomic_move(self, src: Path, dst: Path) -> None:
        """Atomically move a file from src to dst."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Use os.replace for atomic move on same filesystem
        os.replace(str(src), str(dst))
