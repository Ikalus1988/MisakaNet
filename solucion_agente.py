import json
import uuid
import urllib.request
import urllib.error
import sys
import argparse

ENDPOINT = "https://misakanet.org/mcp"
JSONRPC_VERSION = "2.0"


def _rpc_call(method: str, params: dict, token: str | None = None):
    payload = {
        "jsonrpc": JSONRPC_VERSION,
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": method,
            "arguments": params,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req) as resp:
            resp_data = resp.read().decode("utf-8")
            result = json.loads(resp_data)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP error {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}") from e

    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")
    return result.get("result")


def register(agent_type: str = "cli"):
    """Obtain a free token. No auth required."""
    return _rpc_call("misakanet_register", {"agent_type": agent_type})


def search(query: str, token: str):
    """Search lessons by query string."""
    return _rpc_call("misakanet_search", {"query": query}, token=token)


def get_lesson(lesson_id: str | int, token: str):
    """Fetch full lesson content by ID."""
    return _rpc_call("misakanet_get_lesson", {"lesson_id": lesson_id}, token=token)


def submit_intake(case: dict):
    """
    Report a new failure case.
    `case` should be a dict containing at least:
        - title
        - description
        - steps (list)
    """
    return _rpc_call("misakanet_submit_intake", {"case": case})


def write_lesson(lesson: dict, token: str):
    """
    Submit a structured lesson.
    Expected keys: title, error_text, solution, tags (list), source (optional)
    """
    return _rpc_call("misakanet_write_lesson", {"lesson": lesson}, token=token)


def preflight(operation: str, token: str):
    """
    Perform a risk check before a high‑risk operation.
    `operation` is a short description of what you plan to do.
    """
    return _rpc_call("misakanet_preflight", {"operation": operation}, token=token)


def _print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="CLI for MisakaNet MCP Server (zero‑dependency)."
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    reg = subparsers.add_parser("register", help="Obtain a free token")
    reg.add_argument("--agent", default="cli", help="Agent type identifier")

    srch = subparsers.add_parser("search", help="Search lessons")
    srch.add_argument("query", help="Search query")
    srch.add_argument("--token", required=True, help="Bearer token")

    get = subparsers.add_parser("get", help="Get lesson by ID")
    get.add_argument("lesson_id", help="Lesson identifier")
    get.add_argument("--token", required=True, help="Bearer token")

    sub = subparsers.add_parser("submit-intake", help="Report a new failure case")
    sub.add_argument("--json", help="Path to JSON file with case data")
    sub.add_argument("--title", help="Title of the case")
    sub.add_argument("--desc", help="Description")
    sub.add_argument("--steps", nargs="*", help="Steps (space‑separated)")

    write = subparsers.add_parser("write", help="Submit a new lesson")
    write.add_argument("--json", help="Path to JSON file with lesson data")
    write.add_argument("--token", required=True, help="Bearer token")
    write.add_argument("--title", help="Lesson title")
    write.add_argument("--error", help="Error text")
    write.add_argument("--solution", help="Solution description")
    write.add_argument("--tags", nargs="*", help="Tags")

    pre = subparsers.add_parser("preflight", help="Risk check before operation")
    pre.add_argument("operation", help="Operation description")
    pre.add_argument("--token", required=True, help="Bearer token")

    args = parser.parse_args()

    try:
        if args.cmd == "register":
            token = register(agent_type=args.agent)
            _print_json(token)

        elif args.cmd == "search":
            res = search(args.query, token=args.token)
            _print_json(res)

        elif args.cmd == "get":
            res = get_lesson(args.lesson_id, token=args.token)
            _print_json(res)

        elif args.cmd == "submit-intake":
            if args.json:
                with open(args.json, "r", encoding="utf-8") as f:
                    case = json.load(f)
            else:
                if not args.title or not args.desc or not args.steps:
                    parser.error(
                        "When not using --json, --title, --desc and --steps are required."
                    )
                case = {
                    "title": args.title,
                    "description": args.desc,
                    "steps": args.steps,
                }
            res = submit_intake(case)
            _print_json(res)

        elif args.cmd == "write":
            if args.json:
                with open(args.json, "r", encoding="utf-8") as f:
                    lesson = json.load(f)
            else:
                missing = [k for k in ("title", "error", "solution") if getattr(args, k) is None]
                if missing:
                    parser.error(f"Missing arguments for lesson: {', '.join(missing)}")
                lesson = {
                    "title": args.title,
                    "error_text": args.error,
                    "solution": args.solution,
                    "tags": args.tags or [],
                }
            res = write_lesson(lesson, token=args.token)
            _print_json(res)

        elif args.cmd == "preflight":
            res = preflight(args.operation, token=args.token)
            _print_json(res)

    except RuntimeError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()