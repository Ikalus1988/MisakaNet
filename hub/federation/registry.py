"""
Federation Registry — maintains list of peer repos for cross-repo sync.

Pure Python stdlib only — no third-party dependencies.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any


class PeerNode:
    """Represents a single peer repository in the federation."""

    def __init__(
        self,
        node_id: str,
        url: str,
        public_key_fingerprint: str = "",
        enabled: bool = True,
        priority: int = 0,
    ):
        self.node_id = node_id
        self.url = url
        self.public_key_fingerprint = public_key_fingerprint
        self.enabled = enabled
        self.priority = priority

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "url": self.url,
            "public_key_fingerprint": self.public_key_fingerprint,
            "enabled": self.enabled,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PeerNode:
        return cls(
            node_id=data["node_id"],
            url=data["url"],
            public_key_fingerprint=data.get("public_key_fingerprint", ""),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
        )

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"PeerNode({self.node_id}, {self.url}, {status})"


class FederationRegistry:
    """Manages the list of peer repos participating in federation sync.

    The registry is persisted as a JSON file. Peers are added/removed
    via the API and synced to disk on each mutation.

    Usage::

        registry = FederationRegistry("./hub/federation/registry.json")
        registry.add_peer(PeerNode(node_id="Misaka10048", url="https://github.com/..."))
        registry.save()
        for peer in registry.active_peers():
            print(peer.url)
    """

    def __init__(self, registry_path: str | Path):
        self._path = Path(registry_path)
        self._peers: dict[str, PeerNode] = {}
        self._local_node_id: str = ""
        if self._path.exists():
            self.load()

    @property
    def local_node_id(self) -> str:
        return self._local_node_id

    @local_node_id.setter
    def local_node_id(self, value: str) -> None:
        self._local_node_id = value

    def load(self) -> None:
        """Load registry from disk."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self._local_node_id = data.get("local_node_id", "")
        for peer_data in data.get("peers", []):
            peer = PeerNode.from_dict(peer_data)
            self._peers[peer.node_id] = peer

    def save(self) -> None:
        """Persist registry to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "local_node_id": self._local_node_id,
            "peers": [p.to_dict() for p in self._peers.values()],
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add_peer(self, peer: PeerNode) -> None:
        """Add or update a peer in the registry."""
        self._peers[peer.node_id] = peer

    def remove_peer(self, node_id: str) -> bool:
        """Remove a peer by node_id. Returns True if removed."""
        return self._peers.pop(node_id, None) is not None

    def get_peer(self, node_id: str) -> PeerNode | None:
        return self._peers.get(node_id)

    def active_peers(self) -> list[PeerNode]:
        """Return all enabled peers, sorted by priority (highest first)."""
        return sorted(
            [p for p in self._peers.values() if p.enabled],
            key=lambda p: p.priority,
            reverse=True,
        )

    def all_peers(self) -> list[PeerNode]:
        return list(self._peers.values())

    def peer_count(self) -> int:
        return len(self._peers)

    def fingerprint_for(self, data: str) -> str:
        """Generate SHA-256 fingerprint for given data."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]
