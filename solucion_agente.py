from workers.lib.handlers import GITHUB_API, REPO, PUBLIC_DATA_BASE

def misakanet_submit_intake(problem: str, source: str):
    """
    Submit a failure case to MCP intake.

    Args:
        problem (str): Description of the failure case.
        source (str): Identifier of the source (e.g., "your-agent").

    Returns:
        dict: JSON response from the MCP intake endpoint.
    """
    import json
    import requests

    # Build the payload expected by the intake service
    payload = {
        "problem": problem,
        "source": source,
        "repo": REPO,
        "public_data_base": PUBLIC_DATA_BASE,
    }

    # Authenticate using the GitHub token defined in handlers
    headers = {
        "Authorization": f"token {GITHUB_API}",
        "Content-Type": "application/json",
    }

    # Send the request to the intake endpoint
    intake_url = f"{PUBLIC_DATA_BASE}/intake"
    response = requests.post(intake_url, json=payload, headers=headers)
    response.raise_for_status()

    # Return the parsed JSON response
    return response.json()