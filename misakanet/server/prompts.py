"""MCP Prompts for MisakaNet server."""
from __future__ import annotations

PROMPTS = [
    {
        "name": "search_lesson",
        "title": "Search Lessons",
        "description": "Search MisakaNet for lessons matching an error or topic",
        "arguments": [
            {
                "name": "query",
                "description": "Error message or topic to search for",
                "required": True,
            },
            {
                "name": "domain",
                "description": (
                    "Optional domain filter (devops, python, rag, etc.)"
                ),
                "required": False,
            },
        ],
    },
    {
        "name": "triage_failure",
        "title": "Triage Failure",
        "description": (
            "Structured failure triage — find root cause"
            " and matching rescue cards"
        ),
        "arguments": [
            {
                "name": "error",
                "description": "The error message or stack trace",
                "required": True,
            },
            {
                "name": "context",
                "description": (
                    "What were you doing when the error occurred"
                ),
                "required": False,
            },
        ],
    },
    {
        "name": "release_audit",
        "title": "Release Audit",
        "description": (
            "Check release readiness against MisakaNet quality gates"
        ),
        "arguments": [
            {
                "name": "version",
                "description": "Version to audit (e.g., v2.12.0)",
                "required": True,
            },
        ],
    },
]


def handle_prompts_get(name: str, arguments: dict) -> dict:
    """Return a prompt with arguments filled in."""
    if name == "search_lesson":
        query = arguments.get("query", "")
        domain = arguments.get("domain", "")
        domain_hint = f" in the '{domain}' domain" if domain else ""
        return {
            "description": f"Search for lessons about: {query}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f'Search MisakaNet lessons for solutions'
                            f' to: "{query}"{domain_hint}.\n\n'
                            f'Use the misakanet_search tool'
                            f' with query="{query}"'
                            + (
                                f' and domain="{domain}"'
                                if domain
                                else ""
                            )
                            + ".\n\nReport the top 3 matches with"
                            " their relevance score and"
                            " actionable summary."
                        ),
                    },
                }
            ],
        }

    elif name == "triage_failure":
        error = arguments.get("error", "")
        context = arguments.get("context", "unknown context")
        return {
            "description": f"Triage failure: {error[:80]}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"I encountered this error while"
                            f" {context}:\n\n"
                            f"```\n{error}\n```\n\n"
                            "Please:\n"
                            "1. Search MisakaNet for matching lessons"
                            " using misakanet_search\n"
                            "2. If a rescue card exists,"
                            " apply its fix\n"
                            "3. If no match, suggest the root cause"
                            " and next diagnostic steps"
                        ),
                    },
                }
            ],
        }

    elif name == "release_audit":
        version = arguments.get("version", "latest")
        return {
            "description": f"Audit release {version}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Audit MisakaNet release {version}"
                            " for readiness.\n\n"
                            "Check:\n"
                            "1. Read misaka://docs/changelog for"
                            " this version's changes\n"
                            "2. Verify all lessons in"
                            " misaka://lessons/index have valid"
                            " frontmatter\n"
                            "3. Check protocol version matches in"
                            " misaka://protocol/overview\n"
                            "4. Report any gaps or blockers"
                            " for release"
                        ),
                    },
                }
            ],
        }

    return {"error": f"Unknown prompt: {name}"}
