import unittest
import json
from audit_metadata import audit_glama_registry, audit_mcp_registry, audit_pypi_package, audit_readme, audit_server_json, remove_stale_badges

class TestAuditMetadata(unittest.TestCase):

    def test_audit_glama_registry(self):
        server_json = {'glama_registry_url': 'https://example.com/glama-registry', 'tools': ['tool1', 'tool2']}
        self.assertTrue(audit_glama_registry(server_json))

    def test_audit_mcp_registry(self):
        self.assertTrue(audit_mcp_registry('2.14.0'))

    def test_audit_pypi_package(self):
        server_json = {'package_version': '1.0.0'}
        self.assertTrue(audit_pypi_package(server_json['package_version']))

    def test_audit_readme(self):
        server_json = {'lesson_count': 10, 'node_count': 20, 'tool_count': 30}
        readme_path = 'README.md'
        self.assertTrue(audit_readme(server_json, readme_path))

    def test_audit_server_json(self):
        server_json = {'description': 'Example description', 'version': '1.0.0', 'package_version': '1.0.0'}
        self.assertTrue(audit_server_json(server_json))

    def test_remove_stale_badges(self):
        docs_path = 'docs'
        remove_stale_badges(docs_path)
        # Check if stale badges are removed

if __name__ == '__main__':
    unittest.main()