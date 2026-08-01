import json
import requests
from pathlib import Path

def audit_glama_registry(server_json):
    # Assuming Glama registry URL is stored in server.json
    glama_registry_url = server_json['glama_registry_url']
    response = requests.get(glama_registry_url)
    if response.status_code == 200:
        glama_registry_data = response.json()
        # Verify tools visibility and sync with server.json
        for tool in server_json['tools']:
            if tool not in glama_registry_data['tools']:
                return False
    else:
        return False
    return True

def audit_mcp_registry(version):
    mcp_registry_url = 'https://mcp-registry.example.com/version'
    response = requests.get(mcp_registry_url)
    if response.status_code == 200:
        mcp_registry_version = response.json()['version']
        return mcp_registry_version == version
    else:
        return False

def audit_pypi_package(version):
    pypi_url = 'https://pypi.org/pypi/misakanet/json'
    response = requests.get(pypi_url)
    if response.status_code == 200:
        pypi_data = response.json()
        return pypi_data['info']['version'] == version
    else:
        return False

def audit_readme(server_json, readme_path):
    with open(readme_path, 'r') as f:
        readme_content = f.read()
    lesson_count = readme_content.count('lesson')
    node_count = readme_content.count('node')
    tool_count = readme_content.count('tool')
    return (lesson_count == server_json['lesson_count'] and
            node_count == server_json['node_count'] and
            tool_count == server_json['tool_count'])

def audit_server_json(server_json):
    description = server_json['description']
    version = server_json['version']
    package_version = server_json['package_version']
    return description and version and package_version and version == package_version

def remove_stale_badges(docs_path):
    for file in Path(docs_path).glob('**/*'):
        if file.is_file() and file.suffix == '.md':
            with open(file, 'r+') as f:
                content = f.read()
                # Remove stale badges
                content = content.replace('[![Stale](https://example.com/stale-badge.svg)]', '')
                f.seek(0)
                f.write(content)
                f.truncate()

def main():
    server_json_path = 'server.json'
    readme_path = 'README.md'
    docs_path = 'docs'
    with open(server_json_path, 'r') as f:
        server_json = json.load(f)
    
    glama_registry_sync = audit_glama_registry(server_json)
    mcp_registry_version_match = audit_mcp_registry('2.14.0')
    pypi_version_match = audit_pypi_package(server_json['package_version'])
    readme_accuracy = audit_readme(server_json, readme_path)
    server_json_consistency = audit_server_json(server_json)
    
    print('Audit Findings:')
    print(f'Glama Registry Sync: {glama_registry_sync}')
    print(f'MCP Registry Version Match: {mcp_registry_version_match}')
    print(f'PyPI Version Match: {pypi_version_match}')
    print(f'README Accuracy: {readme_accuracy}')
    print(f'Server JSON Consistency: {server_json_consistency}')
    
    remove_stale_badges(docs_path)

if __name__ == '__main__':
    main()