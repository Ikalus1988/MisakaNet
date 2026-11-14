import unittest
from solution import ServiceValidator

class TestServiceValidator(unittest.TestCase):
    def test_valid_payload(self):
        self.assertTrue(ServiceValidator.validate_payload({"id": "101", "status": "active"}))

    def test_invalid_payload(self):
        self.assertFalse(ServiceValidator.validate_payload({"status": "active"}))
        self.assertFalse(ServiceValidator.validate_payload({"id": "102", "status": "unknown"}))

if __name__ == "__main__":
    unittest.main()
