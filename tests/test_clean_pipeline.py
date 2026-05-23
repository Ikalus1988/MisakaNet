import unittest
import sys
from pathlib import Path

# Add project script dir to sys.path so we can import clean_pipeline
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "misakanet" / "scripts"))

from clean_pipeline import DOMAIN_KEYWORDS, step_classify

class TestCleanPipeline(unittest.TestCase):
    def test_docker_keywords_present(self):
        # Verify docker domain exists and has expected keywords
        self.assertIn("docker", DOMAIN_KEYWORDS)
        self.assertIn("devops", DOMAIN_KEYWORDS)
        
        docker_kws = DOMAIN_KEYWORDS["docker"]
        self.assertIn("docker", docker_kws)
        self.assertIn("dockerfile", docker_kws)
        self.assertIn("docker-compose", docker_kws)
        self.assertIn("container", docker_kws)
        self.assertIn("image", docker_kws)
        self.assertIn("buildx", docker_kws)
        
        # Verify docker keyword is removed from devops
        self.assertNotIn("docker", DOMAIN_KEYWORDS["devops"])

    def test_step_classify_docker(self):
        # Input lesson with general domain and docker keywords
        lesson = {
            "content": "---\ntitle: Docker build error\ndomain: general\nstatus: draft\n---\n\nUsing docker-compose we hit an issue when downloading the base image.",
            "fm": {"title": "Docker build error", "domain": "general", "status": "draft"},
            "body": "Using docker-compose we hit an issue when downloading the base image.",
            "relpath": "staging/node2/test-docker.md"
        }
        
        lessons = [lesson]
        result = step_classify(lessons)
        
        # Verify that it got classified as 'docker'
        self.assertEqual(result[0]["fm"]["domain"], "docker")

    def test_step_classify_devops(self):
        # Input lesson with general domain and devops keywords
        lesson = {
            "content": "---\ntitle: WSL terminal setup\ndomain: general\nstatus: draft\n---\n\nConfiguring bash shell environment in wsl.",
            "fm": {"title": "WSL terminal setup", "domain": "general", "status": "draft"},
            "body": "Configuring bash shell environment in wsl.",
            "relpath": "staging/node2/test-devops.md"
        }
        
        lessons = [lesson]
        result = step_classify(lessons)
        
        # Verify that it got classified as 'devops'
        self.assertEqual(result[0]["fm"]["domain"], "devops")

if __name__ == "__main__":
    unittest.main()
