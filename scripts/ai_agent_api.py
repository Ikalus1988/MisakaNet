#!/usr/bin/env python3
"""MisakaNet AI Agent API — Simple REST API for AI agents.

Provides optimized endpoints for AI agents to search and access failure lessons.

Usage:
    # Start API server
    python3 scripts/ai_agent_api.py

    # Custom port
    python3 scripts/ai_agent_api.py --port 9090

    # Endpoints:
    # GET /api/search?q=<query>&format=json|markdown
    # GET /api/summary
    # GET /api/content-signals
    # GET /api/schema
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Import search engine
try:
    from misakanet.search.engine import MisakaNetSearchEngine
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

try:
    from scripts.build_sag_index import search as sag_search
    SAG_DB = REPO_ROOT / "data" / "sag.db"
    HAS_SAG = SAG_DB.exists()
except ImportError:
    HAS_SAG = False

# Import lessons
LESSONS_DIR = REPO_ROOT / "lessons"


class AIAgentHandler(BaseHTTPRequestHandler):
    """HTTP handler for AI Agent API."""

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Route to appropriate handler
        if path == "/api/search":
            self.handle_search(params)
        elif path == "/api/summary":
            self.handle_summary(params)
        elif path == "/api/content-signals":
            self.handle_content_signals(params)
        elif path == "/api/schema":
            self.handle_schema(params)
        elif path == "/api/robots-txt":
            self.handle_robots_txt(params)
        else:
            self.send_error(404, "Endpoint not found")

    def handle_search(self, params):
        """Search failure lessons."""
        query = params.get("q", [""])[0]
        fmt = params.get("format", ["json"])[0]
        top = int(params.get("top", ["5"])[0])

        if not query:
            self.send_json(400, {"error": "q parameter is required"})
            return

        # Search using available engine
        results = []
        if HAS_SAG:
            results = sag_search(SAG_DB, query, top=top)
        elif HAS_BM25:
            engine = MisakaNetSearchEngine()
            results = engine.search(query, top=top)

        # Format response
        if fmt == "markdown":
            response = self.format_markdown(results, query)
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.end_headers()
            self.wfile.write(response.encode())
        else:
            response = {
                "query": query,
                "results": results,
                "metadata": {
                    "totalResults": len(results),
                    "format": "json",
                    "source": "misakanet"
                }
            }
            self.send_json(200, response)

    def handle_summary(self, params):
        """Get summary of available lessons."""
        # Count lessons by domain
        domains = {}
        total_lessons = 0

        if LESSONS_DIR.exists():
            for lesson_file in LESSONS_DIR.glob("**/*.md"):
                total_lessons += 1
                # Extract domain from path
                rel_path = lesson_file.relative_to(LESSONS_DIR)
                domain = rel_path.parts[0] if len(rel_path.parts) > 1 else "general"
                domains[domain] = domains.get(domain, 0) + 1

        response = {
            "summary": {
                "totalLessons": total_lessons,
                "domains": domains,
                "version": "1.0.0",
                "timestamp": "2026-08-24T00:00:00Z"
            },
            "links": {
                "search": "/api/search?q={query}",
                "contentSignals": "/api/content-signals",
                "schema": "/api/schema"
            }
        }
        self.send_json(200, response)

    def handle_content_signals(self, params):
        """Return content signals policy."""
        response = {
            "version": "1.0",
            "policy": "allow",
            "supportedUseCases": ["training", "search", "agent"],
            "attributionRequired": False,
            "allowedPaths": [
                "/public/",
                "/open/",
                "/docs/",
                "/api/search",
                "/api/summary"
            ],
            "disallowedPaths": [
                "/api/private/",
                "/private/",
                "/member-only/"
            ]
        }
        self.send_json(200, response)

    def handle_schema(self, params):
        """Return JSON-LD schema."""
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "name": "MisakaNet",
                    "url": "https://misakanet.org",
                    "description": "Git-backed failure-memory for AI coding agents",
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": {
                            "@type": "EntryPoint",
                            "urlTemplate": "https://misakanet.org/api/search?q={search_term_string}"
                        },
                        "query-input": "required name=search_term_string"
                    }
                },
                {
                    "@type": "Dataset",
                    "name": "Failure Lessons Knowledge Base",
                    "description": "Structured dataset of failure-recovery lessons for AI agents",
                    "distribution": {
                        "@type": "DataDownload",
                        "contentUrl": "https://misakanet.org/api/summary",
                        "encodingFormat": "application/json"
                    },
                    "license": "https://misakanet.org/license"
                }
            ]
        }
        self.send_json(200, schema)

    def handle_robots_txt(self, params):
        """Return robots.txt content."""
        robots_txt = """User-agent: *
Allow: /public/
Allow: /open/
Allow: /docs/
Allow: /api/search
Allow: /api/summary
Disallow: /api/private/
Disallow: /private/
Crawl-delay: 1

User-agent: GPTBot
Allow: /open/
Allow: /docs/
Allow: /api/

User-agent: ClaudeBot
Allow: /open/
Allow: /docs/
Allow: /api/

Sitemap: https://misakanet.org/sitemap.xml
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(robots_txt.encode())

    def format_markdown(self, results, query):
        """Format results as markdown."""
        if not results:
            return f"# Search Results for: {query}\n\nNo results found.\n"

        lines = [f"# Search Results for: {query}\n"]
        for i, result in enumerate(results, 1):
            title = result.get("title", "Untitled")
            score = result.get("score", 0)
            snippet = result.get("snippet", result.get("content", "")[:200])
            lines.append(f"## {i}. {title} (score: {score:.2f})\n")
            lines.append(f"{snippet}\n")

        return "\n".join(lines)

    def send_json(self, code, data):
        """Send JSON response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Signals-Policy", "allow")
        self.send_header("X-AI-Agent-Support", "true")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def main():
    """Start the AI Agent API server."""
    parser = argparse.ArgumentParser(description="MisakaNet AI Agent API")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), AIAgentHandler)
    print(f"🤖 MisakaNet AI Agent API running on http://{args.host}:{args.port}")
    print(f"   Endpoints:")
    print(f"   - GET /api/search?q=<query>&format=json|markdown")
    print(f"   - GET /api/summary")
    print(f"   - GET /api/content-signals")
    print(f"   - GET /api/schema")
    print(f"   - GET /api/robots-txt")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
