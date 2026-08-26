import json, urllib.request, urllib.error, sys

_ENDPOINT = "https://misakanet.org/mcp"


def _call_tool(name, arguments, token=None, req_id=1):
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(_ENDPOINT, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"HTTP error {e.code}: {e.read().decode()}\n")
        raise
    except urllib.error.URLError as e:
        sys.stderr.write(f"URL error: {e.reason}\n")
        raise


def register(agent_type="python-script"):
    resp = _call_tool("misakanet_register", {"agent_type": agent_type}, req_id=1)
    return resp["result"]["token"]


def search(token, query, limit=10):
    resp = _call_tool(
        "misakanet_search", {"query": query, "limit": limit}, token=token, req_id=2
    )
    return resp["result"]["lessons"]


def get_lesson(token, lesson_id):
    resp = _call_tool(
        "misakanet_get_lesson", {"lesson_id": lesson_id}, token=token, req_id=3
    )
    return resp["result"]["content"]


def main():
    token = register()
    print("Token:", token)

    query = "pip install timeout"
    lessons = search(token, query)
    if not lessons:
        print("No lessons found.")
        return

    print("\nTop lessons:")
    for lesson in lessons[:5]:
        print(f"- [{lesson['id']}] {lesson.get('title', 'Untitled')}")

    first_id = lessons[0]["id"]
    content = get_lesson(token, first_id)
    print(f"\nLesson {first_id} content:\n{content}")


if __name__ == "__main__":
    main()