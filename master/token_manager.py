"""
Token Manager - Master token generation and keyring storage
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
import json
import os


class TokenManager:
    """
    Manages Master mode tokens with keyring storage.
    Token TTL: 24 hours (configurable)
    """

    def __init__(self, keyring_service: str = "hermes-hub",
                 ttl_hours: int = 24):
        self.keyring_service = keyring_service
        self.ttl_hours = ttl_hours
        self._tokens: dict[str, dict] = {}
        self._load_tokens()

    def _load_tokens(self):
        """Load tokens from keyring storage"""
        token_path = os.path.expanduser(f"~/.hermes-tokens")
        try:
            with open(token_path, 'r') as f:
                self._tokens = json.load(f)
            # Filter expired tokens
            self._cleanup_expired()
        except FileNotFoundError:
            self._tokens = {}

    def _save_tokens(self):
        """Save tokens to keyring storage"""
        token_path = os.path.expanduser("~/.hermes-tokens")
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        # Use keyring in production for secure storage
        with open(token_path, 'w') as f:
            json.dump(self._tokens, f, default=str)

    def _cleanup_expired(self):
        """Remove expired tokens"""
        now = datetime.now()
        expired = [
            token for token, info in self._tokens.items()
            if datetime.fromisoformat(info["expires_at"]) < now
        ]
        for token in expired:
            del self._tokens[token]
        if expired:
            self._save_tokens()

    def generate_token(self, secret: str) -> Optional[str]:
        """
        Generate a new Master token.

        Args:
            secret: The shared secret (e.g., "贾恒龙")

        Returns:
            Token string if secret is valid, None otherwise
        """
        # Validate secret from config
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        try:
            import yaml
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f)
            expected_secret = cfg.get("master", {}).get("shared_secret", "")
        except Exception:
            expected_secret = ""
        if not expected_secret:
            raise ValueError("master.shared_secret not configured in config.yaml")
        if secret != expected_secret:
            return None

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=self.ttl_hours)

        self._tokens[token] = {
            "created_at": datetime.now().isoformat(),
            "expires_at": expires_at.isoformat(),
            "secret_hash": hashlib.sha256(secret.encode()).hexdigest()
        }

        self._save_tokens()
        print(f"Master token generated, expires at {expires_at}")
        return token

    def validate_token(self, token: str) -> bool:
        """
        Validate a Master token.

        Args:
            token: Token to validate

        Returns:
            True if valid and not expired
        """
        self._cleanup_expired()

        if token not in self._tokens:
            return False

        expires_at = datetime.fromisoformat(self._tokens[token]["expires_at"])
        return expires_at > datetime.now()

    def revoke_token(self, token: str) -> bool:
        """Revoke a token"""
        if token in self._tokens:
            del self._tokens[token]
            self._save_tokens()
            return True
        return False

    def revoke_all_tokens(self):
        """Revoke all Master tokens"""
        self._tokens = {}
        self._save_tokens()

    def get_token_info(self, token: str) -> Optional[dict]:
        """Get token metadata"""
        if token in self._tokens:
            info = self._tokens[token].copy()
            info["is_valid"] = self.validate_token(token)
            return info
        return None


class AuditLogger:
    """
    Audit logger for Master mode operations.
    Retention: 30 days
    """

    def __init__(self, log_path: str = "./storage/audit.jsonl",
                 retention_days: int = 30):
        self.log_path = log_path
        self.retention_days = retention_days
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(self, action: str, actor: str, details: dict):
        """
        Log a Master mode action.

        Args:
            action: Action type (UNLOCK, ADD_AGENT, REMOVE_AGENT, etc.)
            actor: Who performed the action (token prefix for security)
            details: Additional details
        """
        import keyring  # Optional dependency

        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "actor": actor[:8] + "...",  # Truncate for safety
            "details": details
        }

        with open(self.log_path, 'a') as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def get_recent_logs(self, days: int = 7) -> list[dict]:
        """Get logs from last N days"""
        cutoff = datetime.now() - timedelta(days=days)
        logs = []

        try:
            with open(self.log_path, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    if datetime.fromisoformat(entry["timestamp"]) > cutoff:
                        logs.append(entry)
        except FileNotFoundError:
            pass

        return logs

    def cleanup_old_logs(self):
        """Remove logs older than retention period"""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        valid_logs = []

        try:
            with open(self.log_path, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    if datetime.fromisoformat(entry["timestamp"]) > cutoff:
                        valid_logs.append(entry)

            with open(self.log_path, 'w') as f:
                for entry in valid_logs:
                    f.write(json.dumps(entry, default=str) + "\n")
        except FileNotFoundError:
            pass
