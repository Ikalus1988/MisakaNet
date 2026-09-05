"""GraphQL playground for the MisakaNet CLI (--graphql).

Extracted from search_knowledge.py (audit 2026-09-05, T1.1 stage 3).
"""
import json


def run_graphql_repl(args: list[str]) -> None:
    """Interactive query playground, or single-query mode: --graphql [query]."""
    query = ""
    for i, arg in enumerate(args):
        if arg == "--graphql" and i + 1 < len(args) and not args[i + 1].startswith("--"):
            query = args[i + 1]
            break
    if not query:
        # Interactive mode
        print("MisakaNet GraphQL API (Issue #316)")
        print("Type queries or 'quit' to exit.\n")
        print("Example queries:")
        print('  { lessons(limit: 3) { title domain } }')
        print('  { search(q: "pip timeout") { score lesson { title } } }')
        print('  { lesson(id: "dco-auto-fix-workflow.md") { title tags } }')
        print()
        while True:
            try:
                query = input("graphql> ").strip()
                if query in ("quit", "exit", "q"):
                    break
                if not query:
                    continue
                from misakanet.graphql.schema import execute_query
                result = execute_query(query)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        # Single query mode
        from misakanet.graphql.schema import execute_query
        result = execute_query(query)
        print(json.dumps(result, indent=2, ensure_ascii=False))
