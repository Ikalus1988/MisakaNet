from workers.lib.handlers import GITHUB_API, REPO, PUBLIC_DATA_BASE

def misakanet_submit_intake(problem: str, source: str):
    import json, urllib.request

    data = json.dumps({
        "problem": problem,
        "source": source,
        "github_api": GITHUB_API,
        "repo": REPO,
        "public_data_base": PUBLIC_DATA_BASE
    }).encode("utf-8")

    req = urllib.request.Request(
        url="https://misakanet.org/mcp",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)