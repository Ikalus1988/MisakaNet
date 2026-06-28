"""
Federation key management.

Stores per-node shared secrets in hub/federation/secrets/<node_id>.key.
Keys are generated on node registration and rotated on demand.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

# Default secrets directory: hub/federation/secrets/
_SECRETS_DIR = Path(__file__).parent / "secrets"

# Key metadata file per node
_KEY_FILE = "key.json"


def _secrets_dir() -> Path:
    """Return the secrets directory, creating it if needed."""
    d = _get_secrets_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_secrets_dir() -> Path:
    """Return the configured secrets directory."""
    env = os.environ.get("MISAKA_SECRETS_DIR")
    return Path(env) if env else _SECRETS_DIR


def generate_shared_secret(node_id: str, *, rotate: bool = False) -> str:
    """
    Generate (or rotate) a shared secret for a federated node.

    Returns the hex-encoded secret string.
    Metadata (node_id, created_at, rotated_at) is persisted alongside.
    """
    node_dir = _secrets_dir() / _safe_filename(node_id)
    node_dir.mkdir(parents=True, exist_ok=True)
    key_path = node_dir / _KEY_FILE

    now = time.time()
    hex_secret = secrets.token_hex(32)  # 256-bit key

    meta: dict = {
        "node_id": node_id,
        "created_at": now,
        "rotated_at": now if rotate else None,
        "key_version": 1,
    }

    # If rotating, bump version and preserve original creation time
    if rotate and key_path.exists():
        try:
            old = json.loads(key_path.read_text())
            meta["created_at"] = old.get("created_at", now)
            meta["key_version"] = old.get("key_version", 1) + 1
            meta["rotated_at"] = now
        except (json.JSONDecodeError, OSError):
            pass

    record = {"secret": hex_secret, **meta}
    key_path.write_text(json.dumps(record, indent=2))
    return hex_secret


def get_shared_secret(node_id: str) -> Optional[str]:
    """
    Retrieve the shared secret for a node.

    Returns None if no key exists (node not registered).
    """
    key_path = _secrets_dir() / _safe_filename(node_id) / _KEY_FILE
    if not key_path.exists():
        return None
    try:
        data = json.loads(key_path.read_text())
        return data.get("secret")
    except (json.JSONDecodeError, OSError):
        return None


def get_key_version(node_id: str) -> int:
    """Return the current key version for a node (0 if not found)."""
    key_path = _secrets_dir() / _safe_filename(node_id) / _KEY_FILE
    if not key_path.exists():
        return 0
    try:
        data = json.loads(key_path.read_text())
        return data.get("key_version", 1)
    except (json.JSONDecodeError, OSError):
        return 0


def revoke_secret(node_id: str) -> bool:
    """Delete the shared secret for a node. Returns True if deleted."""
    key_path = _secrets_dir() / _safe_filename(node_id) / _KEY_FILE
    if key_path.exists():
        key_path.unlink()
        return True
    return False


def _safe_filename(node_id: str) -> str:
    """Sanitize node_id for use as a directory name."""
    # Allow alphanumeric, hyphens, underscores, dots
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in node_id)
    return safe[:128]  # cap length
