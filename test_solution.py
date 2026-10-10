import unittest
import subprocess

def run_verification():
    command = "curl -s misakanet.org/api/fragment/liveness"
    expected_result = "<html>\n<head><title>301 Moved Permanently</title><script type=\"module\" src=\"http://misakanet.org/.webmcp/bridge.js\" data-packs=\"c2pa,mcp-server-client\"></script></head>\n<body>\n<center><h1>301 Moved Permanently</h1></center>\n<hr><center>cloudflare</center>\n</body>\n</html>"
    
    print(f"Running command: {command}")
    result = subprocess.check_output(["curl", "-s", "misakanet.org/api/fragment/liveness"], text=True).strip()
    
    if result == expected_result:
        print(f"Verification passed: {result}")
    else:
        print(f"Verification failed: Expected {expected_result}, got {result}")

class TestRunVerification(unittest.TestCase):
    def test_run_verification(self):
        expected_result = "<html>\n<head><title>301 Moved Permanently</title><script type=\"module\" src=\"http://misakanet.org/.webmcp/bridge.js\" data-packs=\"c2pa,mcp-server-client\"></script></head>\n<body>\n<center><h1>301 Moved Permanently</h1></center>\n<hr><center>cloudflare</center>\n</body>\n</html>"
        result = subprocess.check_output(["curl", "-s", "misakanet.org/api/fragment/liveness"], text=True).strip()
        
        self.assertEqual(result, expected_result)

if __name__ == "__main__":
    unittest.main()