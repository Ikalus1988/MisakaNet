import unittest
from auth import generate_shared_secret, sign_request, verify_request

class TestAuth(unittest.TestCase):
    def test_generate_shared_secret(self):
        node_id = "test_node"
        secret = generate_shared_secret(node_id)
        self.assertEqual(len(secret), 32)

    def test_sign_request(self):
        node_id = "test_node"
        request_data = "Hello, world!"
        signature = sign_request(node_id, request_data)
        self.assertIsInstance(signature, str)

    def test_verify_request(self):
        node_id = "test_node"
        request_data = "Hello, world!"
        signature = sign_request(node_id, request_data)
        self.assertTrue(verify_request(node_id, request_data, signature))

    def test_replay_protection(self):
        node_id = "test_node"
        request_data = "Hello, world!"
        signature = sign_request(node_id, request_data)
        self.assertFalse(verify_request(node_id, "Hello, world! ", signature))

    def test_key_rotation(self):
        node_id = "test_node"
        request_data = "Hello, world!"
        signature = sign_request(node_id, request_data)
        generate_shared_secret(node_id)
        self.assertFalse(verify_request(node_id, request_data, signature))

if __name__ == "__main__":
    unittest.main()