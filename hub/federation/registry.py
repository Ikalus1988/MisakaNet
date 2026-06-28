"""Federation Registry — maintain a list of peer repos.

Pure Python stdlib + PyYAML only.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from . import secrets as secret_store

logger = logging.getLogger(__name__)


@dataclass
class PeerNode:
    """A registered peer in the federation."""
    node_id: str
    repo_url: str
    public_key_fingerprint: str | None = None
    last_sync: str | None = None
    status: str = "active"  # active | unreachable | disabled


@dataclass
class FederationRegistry:
    """Registry of peer repos for cross-repo lesson sync."""

    peers: dict[str, PeerNode] = field(default_factory=dict)
    _config_path: Path | None = None

    @classmethod
    def from_config(cls, config_path: str | Path) -> FederationRegistry:
        """Load registry from config.yaml."""
        path = Path(config_path)
        if not path.exists():
            logger.info("No federation config found at %s, starting empty", path)
            return cls(_config_path=path)

        with path.open() as f:
            config = yaml.safe_load(f) or {}

        registry = cls(_config_path=path)
        for peer_data in config.get("peers", []):
            peer = PeerNode(**peer_data)
            registry.peers[peer.node_id] = peer

        logger.info("Loaded %d peers from %s", len(registry.peers), path)
        return registry

    def save(self) -> None:
        """Save registry to config file."""
        if not self._config_path:
            return

        config = {
            "peers": [asdict(p) for p in self.peers.values()],
            "sync_interval_minutes": 15,
            "conflict_strategy": "last_writer_wins",
        }

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w") as f:
            yaml.dump(config, f, default_flow_style=False)

    def add_peer(self, node_id: str, repo_url: str, public_key_fingerprint: str | None = None) -> PeerNode:
        """Add a new peer to the registry and generate an HMAC shared secret."""
        peer = PeerNode(
            node_id=node_id,
            repo_url=repo_url,
            public_key_fingerprint=public_key_fingerprint,
        )
        self.peers[node_id] = peer
        self.save()

        # Generate shared secret for HMAC-SHA256 authentication
        secret_store.generate_shared_secret(node_id)
        logger.info("Added peer: %s (%s) with HMAC secret", node_id, repo_url)
        return peer

    def remove_peer(self, node_id: str) -> bool:
        """Remove a peer from the registry and revoke its HMAC secret."""
        if node_id in self.peers:
            del self.peers[node_id]
            self.save()
            secret_store.revoke_secret(node_id)
            logger.info("Removed peer: %s (HMAC secret revoked)", node_id)
            return True
        return False

    def get_peer(self, node_id: str) -> PeerNode | None:
        """Get a peer by node ID."""
        return self.peers.get(node_id)

    def get_active_peers(self) -> list[PeerNode]:
        """Get all active peers."""
        return [p for p in self.peers.values() if p.status == "active"]

    def update_peer_status(self, node_id: str, status: str) -> None:
        """Update a peer's status."""
        if node_id in self.peers:
            self.peers[node_id].status = status
            self.save()

    def update_last_sync(self, node_id: str, timestamp: str) -> None:
        """Update a peer's last sync timestamp."""
        if node_id in self.peers:
            self.peers[node_id].last_sync = timestamp
            self.save()
