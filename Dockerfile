FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
COPY search_knowledge.py .
COPY misakanet/ misakanet/
COPY scripts/mcp_server.py scripts/mcp_server.py
COPY lessons/ lessons/
COPY reference/ reference/

RUN pip install --no-cache-dir .

# MCP server runs on stdio
CMD ["python3", "scripts/mcp_server.py"]
