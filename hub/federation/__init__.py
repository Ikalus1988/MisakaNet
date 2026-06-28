"""Federation module for cross-repo lesson sync."""

from .registry import FederationRegistry, PeerNode
from .sync_protocol import FederationSync, LessonManifest, SyncResult
from .hmac_auth import (
    sign_request,
    verify_request,
    build_auth_headers,
    extract_auth_headers,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    HEADER_KEY_VERSION,
)
from .secrets import (
    generate_shared_secret,
    get_shared_secret,
    get_key_version,
    revoke_secret,
)

__all__ = [
    "FederationRegistry",
    "PeerNode",
    "FederationSync",
    "LessonManifest",
    "SyncResult",
    # HMAC auth
    "sign_request",
    "verify_request",
    "build_auth_headers",
    "extract_auth_headers",
    "HEADER_SIGNATURE",
    "HEADER_TIMESTAMP",
    "HEADER_KEY_VERSION",
    # Secrets
    "generate_shared_secret",
    "get_shared_secret",
    "get_key_version",
    "revoke_secret",
]
