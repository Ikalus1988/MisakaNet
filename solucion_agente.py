import json
import requests

def submit_intake(problem: str, source: str = "cli") -> dict:
    """
    Submit a failure case to the Misakanet MCP Intake service.

    Args:
        problem: Description of the issue you encountered.
        source: Identifier for the submitter (default: "cli").

    Returns:
        Response from the MCP server as a dictionary.
    """
    url = "https://misakanet.org/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "misakanet_submit_intake",
            "arguments": {
                "problem": problem,
                "source": source
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    # Example usage
    issue = "I encountered an unexpected error when uploading a file."
    result = submit_intake(problem=issue, source="my-agent")
    print(json.dumps(result, indent=2))