import hmac
import hashlib
import os

def generate_shared_secret(node_id):
    """Generate a shared secret for a node."""
    secret = os.urandom(32)
    with open(f"hub/federation/secrets/{node_id}.key", "wb") as f:
        f.write(secret)
    return secret

def sign_request(node_id, request_data):
    """Sign a request with the shared secret."""
    secret = open(f"hub/federation/secrets/{node_id}.key", "rb").read()
    signature = hmac.new(secret, request_data.encode(), hashlib.sha256).hexdigest()
    return signature

def verify_request(node_id, request_data, signature):
    """Verify a request signature."""
    secret = open(f"hub/federation/secrets/{node_id}.key", "rb").read()
    expected_signature = hmac.new(secret, request_data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected_signature)