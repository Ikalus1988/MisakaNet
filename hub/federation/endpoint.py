import requests
from auth import sign_request, verify_request

def send_request(node_id, url, data):
    """Send a request to a node with a signed header."""
    signature = sign_request(node_id, data)
    headers = {"X-HMAC-Signature": signature}
    response = requests.post(url, headers=headers, data=data)
    return response

def handle_request(node_id, request_data):
    """Handle an incoming request and verify its signature."""
    signature = request_data.headers.get("X-HMAC-Signature")
    if not verify_request(node_id, request_data.data, signature):
        return "Invalid signature", 401
    # Process the request
    return "Request processed", 200