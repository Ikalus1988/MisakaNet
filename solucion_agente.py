import base64
import json
import os
import sys
import tempfile
import urllib.request
import subprocess

def load_config():
    # Check for config file
    config_paths = [
        "config.json",
        os.path.expanduser("~/.misakanet/config.json"),
        os.environ.get("MISAKANET_CONFIG", "")
    ]
    
    config = {}
    for path in config_paths:
        if path and os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        config.update(loaded)
                        break
            except Exception:
                pass
        
    # Check environment variables
    if 'GITHUB_API' not in config and os.environ.get('GITHUB_API'):
        config['GITHUB_API'] = os.environ['GITHUB_API']
    if 'REPO' not in config and os.environ.get('MISAKANET_REPO'):
        config['REPO'] = os.environ['MISAKANET_REPO']
    if 'PUBLIC_DATA_BASE' not in config and os.environ.get('MISAKANET_PUBLIC_DATA_BASE'):
        config['PUBLIC_DATA_BASE'] = os.environ['MISAKANET_PUBLIC_DATA_BASE']
        
    return config

def run_task(args):
    problem = args.get('problem')
    source = args.get('source', 'unknown')
    
    if not problem:
        return {
            "success": False,
            "error": "Missing required field: 'problem'"
        }
    
    config = load_config()
    
    # Defaults based on the issue description if not provided
    github_api = config.get('GITHUB_API', 'https://api.github.com')
    repo = config.get('REPO', 'Ikalus1988/MisakaNet')
    
    # Construct the issue body
    body = f"""## Failure Case Report

**Problem:**
{problem}

**Source:**
{source}

---
*Submitted via MisakaNet Intake (Python Client)*"""

    payload = {
        "title": f"[Intake] {problem[:50]}{'...' if len(problem) > 50 else ''}",
        "body": body
    }
    
    url = f"{github_api}/repos/{repo}/issues"
    
    request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'))
    request.add_header('Content-Type', 'application/json')
    request.add_header('Accept', 'application/vnd.github+json')
    request.add_header('User-Agent', 'MisakaNet-Intake-Python')
    
    # Add token if available
    token = config.get('GITHUB_TOKEN')
    if token:
        request.add_header('Authorization', f'token {token}')
        
    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            return {
                "submitted": True,
                "intake_id": f"issue-{result.get('number', 'unknown')}",
                "status": "pending_review",
                "issue_url": result.get('html_url', 'url not found'),
                "receipt": f"GitHub issue {result.get('number', '')} created."
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='ignore')
        try:
            error_data = json.loads(error_body)
            return {
                "submitted": False,
                "error": f"GitHub API Error: {e.code} - {error_data.get('message', 'Unknown error')}"
            }
        except json.JSONDecodeError:
            return {
                "submitted": False,
                "error": f"GitHub API Error: {e.code} - {error_body[:200]}"
            }
    except Exception as e:
        return {
            "submitted": False,
            "error": f"Connection Error: {str(e)}"
        }

def main():
    if len(sys.argv) > 1:
        # If args are passed as JSON string
        try:
            input_data = json.loads(sys.argv[1])
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON input"}))
            sys.exit(1)
    else:
        # Read from stdin
        try:
            raw_input = sys.stdin.read()
            if not raw_input.strip():
                print(json.dumps({"error": "No input provided"}))
                sys.exit(1)
            input_data = json.loads(raw_input)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON input: {str(e)}"}))
            sys.exit(1)
            
    result = run_task(input_data)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()