"""
Federation Sync Protocol — pull-based cross-repo lesson synchronization.

Each peer publishes a manifest of lesson IDs + SHA256 hashes.
Pull-based sync fetches manifests from known peers every N minutes.
Uses atomic staging area for crash-safe sync.

Pure Python stdlib only — no third-party dependencies.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from hub.federation.registry import FederationRegistry, PeerNode

# Lesson frontmatter fields added by federation
FEDERATION_FIELDS = ("origin_repo", "origin_node", "last_updated", "federation_ttl")

STAGING_DIR = "staging"
MANIFEST_FILE = "manifest.json"
DEFAULT_SYNC_INTERVAL_MINUTES = 15
DEFAULT_FEDERATION_TTL_SECONDS = 86400


def _sha256_file(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_content(content: str) -> str:
    """Compute SHA-256 hash of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_yaml_frontmatter(text: str) -> dict:
    """Parse simple YAML frontmatter from lesson markdown."""
    meta = {}
    import re
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split('\n'):
        line = line.strip()
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if val.startswith('[') and val.endswith(']'):
            try:
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',') if v.strip()]
            except Exception:
                pass
        meta[key] = val
    return meta


def _generate_manifest(lessons_dir: Path) -> dict[str, Any]:
    """Generate a manifest of all lessons with their IDs and SHA256 hashes."""
    entries = {}
    for md_file in sorted(lessons_dir.glob("**/*.md")):
        if md_file.name.startswith('.') or md_file.name == 'index.md':
            continue
        if md_file.name == 'README.md':
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta = _parse_yaml_frontmatter(content)
        lesson_id = meta.get("id", "")
        if not lesson_id:
            # Use relative path as fallback ID
            lesson_id = str(md_file.relative_to(lessons_dir.parent.parent))
        entries[lesson_id] = {
            "path": str(md_file.relative_to(lessons_dir.parent.parent)),
            "sha256": _sha256_content(content),
            "last_updated": meta.get("last_updated", ""),
            "lang": meta.get("lang", ""),
        }
    return {
        "node_id": "",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lessons": entries,
    }


def _conflict_resolve(local_meta: dict, remote_meta: dict) -> str:
    """Resolve conflict between two versions of the same lesson.

    Returns 'local' or 'remote' to indicate which version wins.
    Rule: later last_updated wins. If identical timestamps, higher node_id wins.
    """
    local_ts = local_meta.get("last_updated", "")
    remote_ts = remote_meta.get("last_updated", "")

    if remote_ts > local_ts:
        return "remote"
    elif local_ts > remote_ts:
        return "local"
    else:
        # Same timestamp — higher node_id wins
        local_node = local_meta.get("origin_node", "")
        remote_node = remote_meta.get("origin_node", "")
        return "remote" if remote_node > local_node else "local"


class SyncProtocol:
    """Pull-based federation sync with atomic staging.

    Usage::

        protocol = SyncProtocol(registry, lessons_dir, staging_dir)
        # Sync all peers
        results = await protocol.sync_all()
        # Or sync a single peer
        result = await protocol.sync_peer(peer)
    """

    def __init__(
        self,
        registry: FederationRegistry,
        lessons_dir: Path,
        staging_dir: Path | None = None,
        sync_interval_minutes: int = DEFAULT_SYNC_INTERVAL_MINUTES,
    ):
        self.registry = registry
        self.lessons_dir = lessons_dir
        self.staging_dir = staging_dir or lessons_dir.parent.parent / STAGING_DIR
        self.sync_interval = sync_interval_minutes
        self._last_sync: dict[str, float] = {}

    def generate_local_manifest(self) -> dict[str, Any]:
        """Generate manifest for this node's lessons."""
        manifest = _generate_manifest(self.lessons_dir)
        manifest["node_id"] = self.registry.local_node_id
        return manifest

    def save_local_manifest(self) -> Path:
        """Save local manifest to repo root."""
        manifest = self.generate_local_manifest()
        manifest_path = self.lessons_dir.parent.parent / MANIFEST_FILE
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return manifest_path

    def fetch_remote_manifest(self, peer: PeerNode) -> dict[str, Any] | None:
        """Fetch manifest from a peer repo via raw GitHub URL.

        This is a simplified implementation that reads the manifest
        from a known URL pattern. In production, this would use
        git fetch or HTTP to pull the manifest.
        """
        # For now, return None (no network fetching in pure stdlib)
        # Real implementation would use urllib.request to fetch
        # raw.githubusercontent.com/{owner}/{repo}/main/manifest.json
        import urllib.request
        import urllib.error

        # Parse owner/repo from URL
        url = peer.url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.split("/")
        if len(parts) < 2:
            return None
        owner, repo = parts[-2], parts[-1]

        manifest_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{MANIFEST_FILE}"
        try:
            req = urllib.request.Request(manifest_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            return None

    def sync_peer(self, peer: PeerNode) -> dict[str, Any]:
        """Sync lessons from a single peer. Returns sync result summary.

        Pull-based sync: fetch manifest → compare → download new/updated → atomic move.
        """
        result = {
            "peer": peer.node_id,
            "added": 0,
            "updated": 0,
            "unchanged": 0,
            "conflicts": 0,
            "errors": 0,
        }

        remote_manifest = self.fetch_remote_manifest(peer)
        if remote_manifest is None:
            result["errors"] = 1
            return result

        local_manifest = self.generate_local_manifest()
        local_lessons = local_manifest.get("lessons", {})
        remote_lessons = remote_manifest.get("lessons", {})

        # Find lessons to sync (new or updated)
        to_sync = []
        for lesson_id, remote_entry in remote_lessons.items():
            local_entry = local_lessons.get(lesson_id)
            if local_entry is None:
                to_sync.append((lesson_id, remote_entry, "new"))
            elif local_entry.get("sha256") != remote_entry.get("sha256"):
                to_sync.append((lesson_id, remote_entry, "updated"))

        if not to_sync:
            result["unchanged"] = len(remote_lessons)
            return result

        # Stage changes atomically
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        for lesson_id, remote_entry, change_type in to_sync:
            try:
                self._sync_lesson(peer, lesson_id, remote_entry, change_type)
                if change_type == "new":
                    result["added"] += 1
                else:
                    result["updated"] += 1
            except Exception as e:
                result["errors"] += 1

        # Atomically move staging → lessons
        self._atomic_promote()

        return result

    def _sync_lesson(
        self,
        peer: PeerNode,
        lesson_id: str,
        remote_entry: dict[str, Any],
        change_type: str,
    ) -> None:
        """Download a single lesson to staging area."""
        import urllib.request

        remote_path = remote_entry.get("path", "")
        if not remote_path:
            return

        # Parse owner/repo from peer URL
        url = peer.url.rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.split("/")
        owner, repo = parts[-2], parts[-1]

        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{remote_path}"
        try:
            req = urllib.request.Request(raw_url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError):
            return

        # Verify SHA256
        actual_hash = _sha256_content(content)
        expected_hash = remote_entry.get("sha256", "")
        if expected_hash and actual_hash != expected_hash:
            return  # Hash mismatch — skip

        # Inject federation metadata into frontmatter
        content = self._inject_federation_frontmatter(
            content, peer, remote_entry
        )

        # Write to staging
        staging_file = self.staging_dir / remote_path
        staging_file.parent.mkdir(parents=True, exist_ok=True)
        staging_file.write_text(content, encoding="utf-8")

    def _inject_federation_frontmatter(
        self,
        content: str,
        peer: PeerNode,
        remote_entry: dict[str, Any],
    ) -> str:
        """Add federation metadata to lesson frontmatter."""
        import re
        m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
        if not m:
            return content

        header, body, footer = m.group(1), m.group(2), m.group(3)

        # Add federation fields
        federation_fields = [
            f"origin_repo: {peer.url.split('/')[-2]}/{peer.url.split('/')[-1]}",
            f"origin_node: {peer.node_id}",
            f"last_updated: {remote_entry.get('last_updated', '')}",
            f"federation_ttl: {DEFAULT_FEDERATION_TTL_SECONDS}",
        ]

        new_body = body.rstrip('\n')
        for field in federation_fields:
            key = field.split(':')[0]
            if key not in new_body:
                new_body += f"\n{field}"

        return header + new_body + '\n' + footer + content[m.end():]

    def _atomic_promote(self) -> None:
        """Atomically move staged files into lessons directory.

        Uses staging area pattern: download to staging, verify SHA256,
        then move to lessons/. If process crashes mid-sync, staging
        files are orphaned but lessons/ is untouched.
        """
        if not self.staging_dir.exists():
            return

        for staged_file in self.staging_dir.glob("**/*.md"):
            rel_path = staged_file.relative_to(self.staging_dir)
            target = self.lessons_dir.parent.parent / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            # Atomic move (on same filesystem, this is atomic)
            shutil.move(str(staged_file), str(target))

        # Clean up empty staging dirs
        for dir_path in sorted(self.staging_dir.rglob("*"), reverse=True):
            if dir_path.is_dir():
                try:
                    dir_path.rmdir()
                except OSError:
                    pass
        try:
            self.staging_dir.rmdir()
        except OSError:
            pass

    def sync_all(self) -> list[dict[str, Any]]:
        """Sync from all active peers. Returns list of sync results."""
        results = []
        for peer in self.registry.active_peers():
            result = self.sync_peer(peer)
            results.append(result)
            self._last_sync[peer.node_id] = time.time()
        return results

    def needs_sync(self, peer: PeerNode) -> bool:
        """Check if a peer is due for sync based on interval."""
        last = self._last_sync.get(peer.node_id, 0)
        elapsed = time.time() - last
        return elapsed >= self.sync_interval * 60
